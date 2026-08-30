package main

import (
	"net/http"
	"sync/atomic"
	"testing"

	"github.com/stretchr/testify/require"
)

// TestParallelUpstreamRetriedInPlace 验证原地重试:同一上游失败后重试 retry_times 次,
// 重试成功即胜出。
func TestParallelUpstreamRetriedInPlace(t *testing.T) {
	var calls atomic.Int32
	flakyCfg, _, _ := fakeUpstream(t, "flaky", func(w http.ResponseWriter, r *http.Request) {
		// 前 2 次返回 500,第 3 次成功
		if calls.Add(1) < 3 {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"flaky"}`))
			return
		}
		w.Write([]byte(`{"choices":[{"message":{"content":"recovered"}}]}`))
	})
	slowCfg, _, _ := fakeUpstream(t, "slow", func(w http.ResponseWriter, r *http.Request) {
		// 永远 500,占位
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"error":"slow down"}`))
	})

	cfg := &Config{
		Upstreams:      []UpstreamConfig{flakyCfg, slowCfg},
		RetryTimes:     3,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  2,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "recovered", "原地重试第 3 次成功应胜出")
	require.GreaterOrEqual(t, calls.Load(), int32(3), "同一上游应被原地重试至少 3 次")
}

// TestSequentialUpstreamRetriedInPlace 验证顺序模式原地重试:同一上游失败后重试,
// 重试耗尽才换下一个上游。
func TestSequentialUpstreamRetriedInPlace(t *testing.T) {
	var calls atomic.Int32
	flakyCfg, _, _ := fakeUpstream(t, "flaky", func(w http.ResponseWriter, r *http.Request) {
		if calls.Add(1) < 2 {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"flaky"}`))
			return
		}
		w.Write([]byte(`{"choices":[{"message":{"content":"seq-recovered"}}]}`))
	})
	flakyCfg.Weight = 100 // 确保先选到 flaky
	goodCfg, _, goodCalls := fakeUpstream(t, "good", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"choices":[{"message":{"content":"should-not-win"}}]}`))
	})
	goodCfg.Weight = 1

	cfg := &Config{
		Upstreams:      []UpstreamConfig{flakyCfg, goodCfg},
		RetryTimes:     3,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  1,
	}
	gw := NewGateway(cfg)

	body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)

	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, respBody, "seq-recovered", "原地重试成功应胜出")
	require.GreaterOrEqual(t, calls.Load(), int32(2), "同一上游应被原地重试")
	require.Zero(t, goodCalls.Load(), "flaky 重试成功前不应换上游")
}
