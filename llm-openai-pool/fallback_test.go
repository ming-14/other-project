package main

import (
	"bytes"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// TestParallelAllNoThinkingError 验证并行模式:所有上游重试耗尽都无思考内容时,
// 返回 502 错误(不兜底透传)。
func TestParallelAllNoThinkingError(t *testing.T) {
	noThink1Cfg, _, _ := fakeUpstream(t, "n1", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"a1"}}]}`, `[DONE]`)))
	})
	noThink2Cfg, _, _ := fakeUpstream(t, "n2", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"a2"}}]}`, `[DONE]`)))
	})

	cfg := &Config{
		Upstreams:             []UpstreamConfig{noThink1Cfg, noThink2Cfg},
		RetryTimes:            1,
		MaxBodySize:           1 << 20,
		Circuit:               CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL:        60,
		ParallelFetch:         2,
		StreamCompletionCheck: true,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}],"stream":true,"reasoning_effort":"high"}`
	resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusBadGateway, resp.StatusCode, "全部无思考内容重试耗尽应返回 502")
}

// TestSequentialAllNoThinkingError 验证顺序模式:所有上游重试耗尽都无思考内容时返回 502。
func TestSequentialAllNoThinkingError(t *testing.T) {
	noThink1Cfg, _, _ := fakeUpstream(t, "n1", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"b1"}}]}`, `[DONE]`)))
	})
	noThink2Cfg, _, _ := fakeUpstream(t, "n2", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"b2"}}]}`, `[DONE]`)))
	})

	cfg := &Config{
		Upstreams:             []UpstreamConfig{noThink1Cfg, noThink2Cfg},
		RetryTimes:            2,
		MaxBodySize:           1 << 20,
		Circuit:               CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL:        60,
		ParallelFetch:         1,
		StreamCompletionCheck: true,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}],"stream":true,"reasoning_effort":"high"}`
	resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusBadGateway, resp.StatusCode, "顺序模式全部无思考内容重试耗尽应返回 502")
}

// TestStreamCompletionRepair 验证 SSE 完整性检查:不完整流自动补发终止事件。
func TestStreamCompletionRepair(t *testing.T) {
	gw := NewGateway(&Config{StreamCompletionCheck: true})

	// 不完整流:有内容但缺 finish_reason 和 [DONE]
	stream := `data: {"choices":[{"delta":{"content":"hi"}}]}` + "\n\n"
	var out bytes.Buffer
	body := io.NopCloser(strings.NewReader(stream))
	err := gw.copyStreamToClient(&out, body, body, 0, false)
	require.ErrorIs(t, err, errStreamIncomplete, "不完整流应返回 errStreamIncomplete")
	require.Contains(t, out.String(), "hi", "原始内容应透传")
	require.Contains(t, out.String(), "finish_reason", "应补发 finish_reason 终止事件")
	require.Contains(t, out.String(), "[DONE]", "应补发 [DONE]")
}

// TestStreamCompletionComplete 验证 SSE 完整性检查:完整流不补发。
func TestStreamCompletionComplete(t *testing.T) {
	gw := NewGateway(&Config{StreamCompletionCheck: true})

	stream := sseBody(
		`{"choices":[{"delta":{"content":"hi"},"finish_reason":"stop"}]}`,
		`[DONE]`,
	)
	var out bytes.Buffer
	body := io.NopCloser(strings.NewReader(stream))
	err := gw.copyStreamToClient(&out, body, body, 0, false)
	require.NoError(t, err, "完整流应正常透传")
	require.Equal(t, stream, out.String(), "完整流不应补发任何内容")
}

// TestStreamCompletionDoneWithoutFinish 验证只有 [DONE] 没有 finish_reason 的流
// 会在 [DONE] 前补发 finish_reason(客户端严格要求 finish_reason)。
func TestStreamCompletionDoneWithoutFinish(t *testing.T) {
	gw := NewGateway(&Config{StreamCompletionCheck: true})

	// 上游只发 [DONE],没有 finish_reason
	stream := sseBody(`{"choices":[{"delta":{"content":"hi"}}]}`, `[DONE]`)
	var out bytes.Buffer
	body := io.NopCloser(strings.NewReader(stream))
	err := gw.copyStreamToClient(&out, body, body, 0, false)
	require.NoError(t, err)
	// 补发的 finish_reason 必须在 [DONE] 之前
	finishIdx := strings.Index(out.String(), "finish_reason")
	doneIdx := strings.Index(out.String(), "[DONE]")
	require.Greater(t, doneIdx, finishIdx, "finish_reason 应出现在 [DONE] 之前")
	require.Contains(t, out.String(), "hi", "原始内容应透传")
}

// TestStreamCompletionCheckDisabled 验证关闭检查时原样透传。
func TestStreamCompletionCheckDisabled(t *testing.T) {
	gw := NewGateway(&Config{StreamCompletionCheck: false})

	stream := `data: {"choices":[{"delta":{"content":"hi"}}]}` + "\n\n"
	var out bytes.Buffer
	body := io.NopCloser(strings.NewReader(stream))
	err := gw.copyStreamToClient(&out, body, body, 0, false)
	require.NoError(t, err)
	require.Equal(t, stream, out.String())
}

// TestStreamCompletionTimeoutNoRepair 验证空闲超时导致的截断**不补发**终止事件
// (数据不完整,补发会掩盖损坏;让客户端报错重试)。
func TestStreamCompletionTimeoutNoRepair(t *testing.T) {
	gw := NewGateway(&Config{StreamCompletionCheck: true})

	// 卡住的 reader:永远不返回数据,模拟上游流式响应中途停顿
	br := newBlockingReader()
	var out bytes.Buffer
	err := gw.copyStreamToClient(&out, br, br, 100*time.Millisecond, false)
	require.Error(t, err, "空闲超时应返回错误")
	require.NotContains(t, err.Error(), "repaired")
	require.NotContains(t, out.String(), "finish_reason", "数据不完整时不应补发 finish_reason")
	require.NotContains(t, out.String(), "[DONE]", "数据不完整时不应补发 [DONE]")
}
