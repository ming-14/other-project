package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
)

// TestRequestHasThinking 验证思考字段检测。
func TestRequestHasThinking(t *testing.T) {
	cases := []struct {
		name string
		body string
		want bool
	}{
		{"reasoning_effort", `{"model":"m","reasoning_effort":"high"}`, true},
		{"reasoning_effort empty", `{"model":"m","reasoning_effort":""}`, false},
		{"thinking enabled", `{"model":"m","thinking":{"type":"enabled"}}`, true},
		{"reasoning object", `{"model":"m","reasoning":{"effort":"high"}}`, true},
		{"no thinking", `{"model":"m","messages":[]}`, false},
		{"invalid json", `not-json`, false},
		{"null thinking", `{"model":"m","thinking":null}`, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			require.Equal(t, c.want, requestHasThinking([]byte(c.body)))
		})
	}
}

func sseBody(events ...string) string {
	var sb strings.Builder
	for _, e := range events {
		sb.WriteString("data: ")
		sb.WriteString(e)
		sb.WriteString("\n\n")
	}
	return sb.String()
}

// TestStreamingThinkingCheckPass 验证 SSE 流含思考内容时正常透传。
func TestStreamingThinkingCheckPass(t *testing.T) {
	body := sseBody(
		`{"choices":[{"delta":{"reasoning_content":"思考中..."}}]}`,
		`{"choices":[{"delta":{"content":"答案"}}]}`,
		`[DONE]`,
	)
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"text/event-stream"}},
		Body:       io.NopCloser(strings.NewReader(body)),
	}
	rec := httptest.NewRecorder()
	err := copyStreamingWithThinkingCheck(rec, resp)
	require.NoError(t, err)
	require.Equal(t, http.StatusOK, rec.Code)
	require.Contains(t, rec.Body.String(), "reasoning_content")
	require.Contains(t, rec.Body.String(), "思考中")
	require.Contains(t, rec.Body.String(), "答案")
}

// TestStreamingThinkingCheckFail 验证 SSE 流无思考内容时报错且不写任何响应。
func TestStreamingThinkingCheckFail(t *testing.T) {
	body := sseBody(
		`{"choices":[{"delta":{"content":"直接回答"}}]}`,
		`{"choices":[{"delta":{"content":"没有思考"}}]}`,
		`[DONE]`,
	)
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"text/event-stream"}},
		Body:       io.NopCloser(strings.NewReader(body)),
	}
	rec := httptest.NewRecorder()
	err := copyStreamingWithThinkingCheck(rec, resp)
	require.ErrorIs(t, err, errNoThinkingContent)
	require.Equal(t, 0, rec.Body.Len(), "切换失败时不得向客户端写入任何字节")
}

// TestStreamingThinkingCheckLate 验证思考内容在第 8 个事件之后出现也算失败(超限)。
func TestStreamingThinkingCheckLate(t *testing.T) {
	var events []string
	for i := 0; i < 10; i++ {
		events = append(events, `{"choices":[{"delta":{"content":"x"}}]}`)
	}
	events = append(events, `{"choices":[{"delta":{"reasoning_content":"太晚了"}}]}`)
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"text/event-stream"}},
		Body:       io.NopCloser(strings.NewReader(sseBody(events...))),
	}
	rec := httptest.NewRecorder()
	err := copyStreamingWithThinkingCheck(rec, resp)
	require.ErrorIs(t, err, errNoThinkingContent)
	require.Equal(t, 0, rec.Body.Len())
}

// TestNonStreamingThinkingCheck 验证非流式响应含/不含思考内容的两种路径。
func TestNonStreamingThinkingCheck(t *testing.T) {
	// 含思考内容 → 正常返回
	withThinking := `{"choices":[{"message":{"reasoning_content":"think","content":"ans"}}]}`
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"application/json"}},
		Body:       io.NopCloser(strings.NewReader(withThinking)),
	}
	rec := httptest.NewRecorder()
	require.NoError(t, copyNonStreamingWithThinkingCheck(rec, resp))
	require.Contains(t, rec.Body.String(), "think")

	// 不含思考内容 → 报错且不写响应
	noThinking := `{"choices":[{"message":{"content":"ans"}}]}`
	resp = &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"application/json"}},
		Body:       io.NopCloser(strings.NewReader(noThinking)),
	}
	rec = httptest.NewRecorder()
	err := copyNonStreamingWithThinkingCheck(rec, resp)
	require.ErrorIs(t, err, errNoThinkingContent)
	require.Equal(t, 0, rec.Body.Len())
}

// TestGatewaySwitchesUpstreamOnNoThinking 集成验证:请求要求思考,
// 第一个上游的流无思考内容,自动切换到第二个上游成功。
func TestGatewaySwitchesUpstreamOnNoThinking(t *testing.T) {
	noThinkCfg, _, noThinkCalls := fakeUpstream(t, "nothink", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"no thinking here"}}]}`, `[DONE]`)))
	})
	noThinkCfg.Weight = 100 // 确保先选中它
	withThinkCfg, _, withThinkCalls := fakeUpstream(t, "withthink", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(
			`{"choices":[{"delta":{"reasoning_content":"thinking..."}}]}`,
			`{"choices":[{"delta":{"content":"real answer"}}]}`,
			`[DONE]`,
		)))
	})
	withThinkCfg.Weight = 1
	gw := testGateway(t, []UpstreamConfig{noThinkCfg, withThinkCfg}, nil, 3)

	body := `{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"stream":true,"reasoning_effort":"high"}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode, "切换后应成功返回")
	require.Contains(t, respBody, "thinking...", "客户端应收到思考内容")
	require.Contains(t, respBody, "real answer")
	require.GreaterOrEqual(t, noThinkCalls.Load(), int32(1), "无思考上游应被尝试过")
	require.GreaterOrEqual(t, withThinkCalls.Load(), int32(1), "有思考上游应被切换到")
}

// TestGatewayNoSwitchWithoutThinkingField 验证请求不带思考字段时,
// 即使上游流无思考内容也不切换(原样透传)。
func TestGatewayNoSwitchWithoutThinkingField(t *testing.T) {
	plainCfg, _, plainCalls := fakeUpstream(t, "plain", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"normal reply"}}]}`, `[DONE]`)))
	})
	gw := testGateway(t, []UpstreamConfig{plainCfg}, nil, 0)

	body := `{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"stream":true}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "normal reply")
	require.Equal(t, int32(1), plainCalls.Load())
}
