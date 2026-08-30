package main

import (
	"net/http"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// TestParallelReleaseAllSems 验证并发抢答完成后所有上游的 sem 都被释放
// (防止落选成功者的 busy 永久占用)。
func TestParallelReleaseAllSems(t *testing.T) {
	// 10 个上游,都立即返回成功(几乎同时,模拟"多个同时成功"场景)
	upstreams := make([]UpstreamConfig, 0, 10)
	for i := 0; i < 10; i++ {
		name := "u" + string(rune('a'+i))
		upCfg, _, _ := fakeUpstream(t, name, func(w http.ResponseWriter, r *http.Request) {
			w.Write([]byte(`{"choices":[{"message":{"content":"ok"}}]}`))
		})
		upstreams = append(upstreams, upCfg)
	}

	cfg := &Config{
		Upstreams:      upstreams,
		RetryTimes:     1,
		MaxBodySize:    1 << 20,
		Circuit:        CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL: 60,
		ParallelFetch:  10,
	}
	gw := NewGateway(cfg)

	// 连续发多个请求,每个请求都会抢 10 个上游
	for i := 0; i < 20; i++ {
		body := `{"model":"m","messages":[{"role":"user","content":"hi"}]}`
		resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
		require.Equal(t, http.StatusOK, resp.StatusCode)
	}

	// 等待异步释放完成
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		allFree := true
		for _, up := range gw.pool.upstreams {
			if len(up.sem) > 0 {
				allFree = false
				break
			}
		}
		if allFree {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}

	// 检查哪些上游还占着
	var busy []string
	for _, up := range gw.pool.upstreams {
		if len(up.sem) > 0 {
			busy = append(busy, up.name)
		}
	}
	require.Empty(t, busy, "请求完成后不应有任何上游 busy 残留(有 sem 泄漏)")
	_ = sync.Once{}
}
