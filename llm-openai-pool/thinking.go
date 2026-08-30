package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// requestModel 提取请求体中的 model 字段,用于按上游 models 配置路由。
func requestModel(body []byte) string {
	var m struct {
		Model string `json:"model"`
	}
	if err := json.Unmarshal(body, &m); err != nil {
		return ""
	}
	return m.Model
}

// requestHasThinking 检查请求体是否包含思考字段(reasoning_effort / thinking / reasoning)。
// 若请求要求思考,而上游实际没有返回思考内容,则认为该上游不合格,切换重试。
func requestHasThinking(body []byte) bool {
	var m map[string]any
	if err := json.Unmarshal(body, &m); err != nil {
		return false
	}
	if v, ok := m["reasoning_effort"]; ok && v != nil {
		if s, ok := v.(string); ok && s != "" {
			return true
		}
	}
	if v, ok := m["thinking"]; ok && v != nil {
		return true
	}
	if v, ok := m["reasoning"]; ok && v != nil {
		return true
	}
	return false
}

// isStreamingResponse 判断上游响应是否为 SSE 流。
func isStreamingResponse(resp *http.Response) bool {
	ct := resp.Header.Get("Content-Type")
	return strings.Contains(ct, "text/event-stream")
}

var errNoThinkingContent = errors.New("上游未返回思考内容")

// errStreamCheckFailed 流式思考校验阶段失败(尚未写任何字节,可安全切换)。
var errStreamCheckFailed = errors.New("stream check failed, no bytes written")

// copyResponseWithThinkingCheck 拷贝 2xx 响应,但请求要求思考时,
// 校验响应中确实包含思考内容;不包含则返回 errNoThinkingContent 触发上游切换。
// 注意:检测期间尚未向客户端写入任何字节,切换重试是安全的。
func (g *Gateway) copyResponseWithThinkingCheck(w http.ResponseWriter, resp *http.Response, requireThinking bool) error {
	if !requireThinking {
		return g.copyResponse(w, resp, nil)
	}
	if isStreamingResponse(resp) {
		return g.copyStreamingWithThinkingCheck(w, resp)
	}
	return g.copyNonStreamingWithThinkingCheck(w, resp)
}

// checkStreamingThinking 读取 SSE 流前若干个事件,检查是否出现思考内容。
// 校验阶段受 stream_idle_timeout 空闲超时约束,不向客户端写入任何字节。
// 返回是否找到思考内容,以及已缓冲的数据和 bufio.Reader(调用方可在校验通过后
// 先取消其他在途请求,再透传 buf 内容 + br 剩余流)。
func (g *Gateway) checkStreamingThinking(resp *http.Response) (bool, *bytes.Buffer, *bufio.Reader, error) {
	const maxCheckEvents = 8 // 前 8 个 SSE 事件内必须出现思考内容
	idleTimeout := time.Duration(g.cfg.StreamIdleTimeout) * time.Second

	var body io.Reader = resp.Body
	if idleTimeout > 0 {
		body = newStreamIdleReader(resp.Body, resp.Body, idleTimeout)
	}
	br := bufio.NewReaderSize(body, 16*1024)
	var buf bytes.Buffer
	events := 0
	found := false

	for events < maxCheckEvents {
		line, err := br.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				break
			}
			return false, nil, nil, fmt.Errorf("%w: read upstream stream: %v", errStreamCheckFailed, err)
		}
		buf.WriteString(line)
		line = strings.TrimRight(line, "\r\n")
		if strings.HasPrefix(line, "data: ") {
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				break
			}
			if strings.Contains(data, "reasoning_content") || strings.Contains(data, "thinking_content") {
				found = true
			}
		}
		if line == "" {
			events++
		}
	}
	return found, &buf, br, nil
}

// copyStreamingWithThinkingCheck 校验 + 透传 SSE 流(顺序模式用)。
// 校验通过后立即透传缓冲内容+剩余流,透传阶段带 SSE 完整性检查。
func (g *Gateway) copyStreamingWithThinkingCheck(w http.ResponseWriter, resp *http.Response) error {
	found, buf, br, err := g.checkStreamingThinking(resp)
	if err != nil {
		return err
	}
	if !found {
		return errNoThinkingContent
	}
	copyResponseHeaders(w, resp.Header)
	w.WriteHeader(resp.StatusCode)
	w.Write(buf.Bytes())
	idleTimeout := time.Duration(g.cfg.StreamIdleTimeout) * time.Second
	return g.copyStreamToClient(w, br, resp.Body, idleTimeout, scanSSECompletion(buf.Bytes()))
}

// checkNonStreamingThinking 读取完整 body 检查思考内容,不向客户端写入任何字节。
// 整体读取受 upstream_timeout 超时约束。无思考内容时返回 (body, errNoThinkingContent),
// body 仍可用于兜底透传。
func (g *Gateway) checkNonStreamingThinking(resp *http.Response) ([]byte, error) {
	timeout := time.Duration(g.cfg.UpstreamTimeout) * time.Second
	body, err := readAllWithTimeout(resp.Body, 1<<20, timeout)
	if err != nil {
		return nil, err
	}
	if !bytes.Contains(body, []byte("reasoning_content")) && !bytes.Contains(body, []byte("thinking_content")) {
		return body, errNoThinkingContent
	}
	return body, nil
}

// copyNonStreamingWithThinkingCheck 非流式响应:读完整 body 后检查
// reasoning_content / thinking_content 字段,存在则写回客户端(顺序模式用)。
func (g *Gateway) copyNonStreamingWithThinkingCheck(w http.ResponseWriter, resp *http.Response) error {
	body, err := g.checkNonStreamingThinking(resp)
	if err != nil {
		return err
	}
	copyResponseHeaders(w, resp.Header)
	w.WriteHeader(resp.StatusCode)
	w.Write(body)
	return nil
}

// copyResponseHeaders 复制非逐跳响应头。
func copyResponseHeaders(w http.ResponseWriter, header http.Header) {
	for k, vs := range header {
		if hopByHop(k) {
			continue
		}
		for _, v := range vs {
			w.Header().Add(k, v)
		}
	}
}
