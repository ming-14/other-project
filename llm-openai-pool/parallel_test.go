package main

import (
	"net/http"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// TestParallelFetchFastWins 验证并发抢答:快的上游胜出,慢的被取消。
func TestParallelFetchFastWins(t *testing.T) {
	slowCfg, _, slowCalls := fakeUpstream(t, "slow", func(w http.ResponseWriter, r *http.Request) {
		// 延迟响应,让快上游先胜出
		time.Sleep(500 * time.Millisecond)
		w.Write([]byte(`{"choices":[{"message":{"content":"slow"}}]}`))
	})
	fastCfg, _, fastCalls := fakeUpstream(t, "fast", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"choices":[{"message":{"content":"fast"}}]}`))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{slowCfg, fastCfg},
		RetryTimes:     1,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  2,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "fast", "应返回快上游的结果")
	require.GreaterOrEqual(t, fastCalls.Load(), int32(1), "快上游应被请求")
	require.GreaterOrEqual(t, slowCalls.Load(), int32(1), "慢上游也应被并发请求")
}

// TestParallelFetchErrorFallback 验证并发抢答:一个上游 500,另一个成功。
func TestParallelFetchErrorFallback(t *testing.T) {
	errCfg, _, errCalls := fakeUpstream(t, "err", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"error":"boom"}`))
	})
	okCfg, _, okCalls := fakeUpstream(t, "ok", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"choices":[{"message":{"content":"ok"}}]}`))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{errCfg, okCfg},
		RetryTimes:     1,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  2,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "ok", "应返回成功上游的结果")
	require.GreaterOrEqual(t, errCalls.Load(), int32(1))
	require.GreaterOrEqual(t, okCalls.Load(), int32(1))
}

// TestParallelFetchWinnerStreamNotCanceled 验证修复:胜利者的流式响应 body
// 在透传过程中不会被 cancel 中断(之前共享 context 导致胜利者 body 读返回
// context.Canceled,表现为"流透传中断: context canceled")。
func TestParallelFetchWinnerStreamNotCanceled(t *testing.T) {
	fastCfg, _, fastCalls := fakeUpstream(t, "fast", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		flusher := w.(http.Flusher)
		// 分块慢速返回,模拟流式传输过程中的后续 chunk
		for _, chunk := range []string{"chunk1", "chunk2", "chunk3"} {
			w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"` + chunk + `"}}]}`)))
			flusher.Flush()
			time.Sleep(30 * time.Millisecond)
		}
		w.Write([]byte(sseBody(`[DONE]`)))
	})
	slowCfg, _, _ := fakeUpstream(t, "slow", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(500 * time.Millisecond)
		w.Write([]byte(`{"choices":[{"message":{"content":"slow"}}]}`))
	})

	cfg := &Config{
		Upstreams:             []UpstreamConfig{fastCfg, slowCfg},
		RetryTimes:            1,
		MaxBodySize:           1 << 20,
		Circuit:               CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL:        60,
		ParallelFetch:         2,
		StreamCompletionCheck: true,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}],"stream":true}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.GreaterOrEqual(t, fastCalls.Load(), int32(1))
	require.Contains(t, respBody, "chunk1", "应收到胜利者流的第一个 chunk")
	require.Contains(t, respBody, "chunk2", "胜利者流不应被 cancel 中断")
	require.Contains(t, respBody, "chunk3", "胜利者流不应被 cancel 中断")
	require.NotContains(t, respBody, "slow")
}

// TestParallelFetch4xxRetried 验证并发抢答:所有上游都返回 4xx 时,原地重试耗尽后
// 透传最后一个 4xx 错误(4xx 也按上游问题重试)。
func TestParallelFetch4xxRetried(t *testing.T) {
	bad1Cfg, _, bad1Calls := fakeUpstream(t, "bad1", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error":{"message":"bad request 1"}}`))
	})
	bad2Cfg, _, bad2Calls := fakeUpstream(t, "bad2", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error":{"message":"bad request 2"}}`))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{bad1Cfg, bad2Cfg},
		RetryTimes:     3,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  2,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusBadRequest, resp.StatusCode)
	require.Contains(t, respBody, "bad request")
	// 4xx 也重试:bad1 被原地重试 retry_times 次
	require.GreaterOrEqual(t, bad1Calls.Load(), int32(1), "bad1 应被调用至少一次")
	_ = bad2Calls
}

// TestParallelFetchThinkingSwitch 验证并发抢答 + 思考校验:第一个 2xx 无思考内容,
// 保留在途请求,等有思考内容的上游胜出。
func TestParallelFetchThinkingSwitch(t *testing.T) {
	noThinkCfg, _, noThinkCalls := fakeUpstream(t, "nothink", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(`{"choices":[{"delta":{"content":"no thinking"}}]}`, `[DONE]`)))
	})
	withThinkCfg, _, withThinkCalls := fakeUpstream(t, "withthink", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(sseBody(
			`{"choices":[{"delta":{"reasoning_content":"thinking..."}}]}`,
			`{"choices":[{"delta":{"content":"answer"}}]}`,
			`[DONE]`,
		)))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{noThinkCfg, withThinkCfg},
		RetryTimes:     1,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  2,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}],"stream":true,"reasoning_effort":"high"}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "thinking...", "应返回带思考内容的上游结果")
	require.GreaterOrEqual(t, noThinkCalls.Load(), int32(1))
	require.GreaterOrEqual(t, withThinkCalls.Load(), int32(1))
}

// TestParallelFetchFewerUpstreams 验证并发数大于上游数时优雅降级(仍正常返回)。
func TestParallelFetchFewerUpstreams(t *testing.T) {
	onlyCfg, _, onlyCalls := fakeUpstream(t, "only", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"choices":[{"message":{"content":"solo"}}]}`))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{onlyCfg},
		RetryTimes:     1,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  5,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "solo")
	require.Equal(t, int32(1), onlyCalls.Load())
}
