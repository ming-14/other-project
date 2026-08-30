package main

import (
	"net/http"
	"testing"

	"github.com/stretchr/testify/require"
)

// TestParallelAllFailConcurrent 验证并发模式全部上游同时失败(模拟网络断开)
// 不会崩溃(修复:之前多个 goroutine 并发写 blacklist map 导致
// "concurrent map writes" 闪退)。
func TestParallelAllFailConcurrent(t *testing.T) {
	// 10 个上游全部返回 500,模拟网络断开时全部失败
	upstreams := make([]UpstreamConfig, 0, 10)
	for i := 0; i < 10; i++ {
		name := "fail" + string(rune('a'+i))
		upCfg, _, _ := fakeUpstream(t, name, func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"boom"}`))
		})
		upstreams = append(upstreams, upCfg)
	}

	cfg := &Config{
		Upstreams:      upstreams,
		RetryTimes:     3,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  10,
	}
	gw := NewGateway(cfg)

	// 连续发多个请求,每个请求 10 个上游同时失败(并发写 blacklist 的场景)
	for i := 0; i < 5; i++ {
		body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
		resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
		require.Equal(t, http.StatusInternalServerError, resp.StatusCode,
			"全部上游失败应透传 500,且程序不应崩溃")
	}
}

// TestParallelPartialFailConcurrent 验证部分成功部分失败不崩溃。
func TestParallelPartialFailConcurrent(t *testing.T) {
	// 5 个失败 + 5 个成功,交替
	upstreams := make([]UpstreamConfig, 0, 10)
	for i := 0; i < 10; i++ {
		name := "mix" + string(rune('a'+i))
		fail := i%2 == 0
		upCfg, _, _ := fakeUpstream(t, name, func(w http.ResponseWriter, r *http.Request) {
			if fail {
				w.WriteHeader(http.StatusInternalServerError)
				w.Write([]byte(`{"error":"boom"}`))
				return
			}
			w.Write([]byte(`{"choices":[{"message":{"content":"ok"}}]}`))
		})
		upstreams = append(upstreams, upCfg)
	}

	cfg := &Config{
		Upstreams:      upstreams,
		RetryTimes:     2,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  10,
	}
	gw := NewGateway(cfg)

	for i := 0; i < 5; i++ {
		body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
		resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
		require.Equal(t, http.StatusOK, resp.StatusCode, "部分成功时应有上游胜出")
	}
}
