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

// copyResponseWithThinkingCheck 拷贝 2xx 响应,但请求要求思考时,
// 校验响应中确实包含思考内容;不包含则返回 errNoThinkingContent 触发上游切换。
// 注意:检测期间尚未向客户端写入任何字节,切换重试是安全的。
func (g *Gateway) copyResponseWithThinkingCheck(w http.ResponseWriter, resp *http.Response, requireThinking bool) error {
	if !requireThinking {
		copyResponse(w, resp)
		return nil
	}
	if isStreamingResponse(resp) {
		return copyStreamingWithThinkingCheck(w, resp)
	}
	return copyNonStreamingWithThinkingCheck(w, resp)
}

// copyStreamingWithThinkingCheck 缓冲 SSE 流的前若干个事件,检查是否出现
// reasoning_content;出现则把缓冲内容+剩余流原样交给客户端,否则报错。
// 使用 bufio.Reader 保持缓冲,检测完成后剩余数据仍可继续读。
func copyStreamingWithThinkingCheck(w http.ResponseWriter, resp *http.Response) error {
	const maxCheckEvents = 8 // 前 8 个 SSE 事件内必须出现思考内容
	br := bufio.NewReaderSize(resp.Body, 16*1024)
	var buf bytes.Buffer
	events := 0
	found := false

	for events < maxCheckEvents {
		line, err := br.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				break
			}
			return fmt.Errorf("read upstream stream: %w", err)
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

	if !found {
		return errNoThinkingContent
	}

	copyResponseHeaders(w, resp.Header)
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, &buf)
	io.Copy(w, br)
	return nil
}

// copyNonStreamingWithThinkingCheck 非流式响应:读完整 body 后检查
// reasoning_content / thinking_content 字段,存在则写回客户端。
func copyNonStreamingWithThinkingCheck(w http.ResponseWriter, resp *http.Response) error {
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return fmt.Errorf("read upstream response: %w", err)
	}
	if !bytes.Contains(body, []byte("reasoning_content")) && !bytes.Contains(body, []byte("thinking_content")) {
		return errNoThinkingContent
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
