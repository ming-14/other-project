package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

// fakeUpstream 起一个可编程假上游,记录调用次数、收到的路径与 Authorization。
func fakeUpstream(t *testing.T, name string, handler http.HandlerFunc) (UpstreamConfig, *httptest.Server, *atomic.Int32) {
	t.Helper()
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		handler(w, r)
	}))
	t.Cleanup(srv.Close)
	return UpstreamConfig{Name: name, BaseURL: srv.URL, APIKey: "sk-up-" + name, Weight: 1, MaxConcurrency: 1}, srv, &calls
}

func testGateway(t *testing.T, ups []UpstreamConfig, keys []string, retry int) *Gateway {
	t.Helper()
	cfg := &Config{
		Upstreams:       ups,
		LocalKeys:       keys,
		RetryTimes:      retry,
		MaxBodySize:     1 << 20,
		Circuit:         CircuitConfig{FailThreshold: 100, CooldownSeconds: 1},
		ModelsCacheTTL:  60,
	}
	return NewGateway(cfg)
}

func doRelay(t *testing.T, gw *Gateway, method, path, auth, body string) (*http.Response, string) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(gw.handleRelay))
	t.Cleanup(srv.Close)
	req, err := http.NewRequest(method, srv.URL+path, strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	if auth != "" {
		req.Header.Set("Authorization", auth)
	}
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	return resp, string(respBody)
}

func okCompletion(id string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"id":"` + id + `","object":"chat.completion","model":"m1","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`))
	}
}

// TestPassthrough 验证请求字节级透传:model/reasoning_effort 等参数原样到上游,
// 响应原样返回,Authorization 替换为上游 key。请求带 reasoning_effort,
// 因此上游响应需含思考内容以通过思考检查。
func TestPassthrough(t *testing.T) {
	var gotPath, gotAuth, gotBody string
	upCfg, _, _ := fakeUpstream(t, "u1", func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotAuth = r.Header.Get("Authorization")
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"id":"upstream-ok","object":"chat.completion","model":"m1","choices":[{"index":0,"message":{"role":"assistant","reasoning_content":"think","content":"ok"},"finish_reason":"stop"}]}`))
	})
	gw := testGateway(t, []UpstreamConfig{upCfg}, nil, 0)

	body := `{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"reasoning_effort":"high","max_tokens":16}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "Bearer sk-local", body)

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, body = %s", resp.StatusCode, respBody)
	}
	if gotPath != "/v1/chat/completions" {
		t.Errorf("path = %q", gotPath)
	}
	if gotAuth != "Bearer sk-up-u1" {
		t.Errorf("auth = %q", gotAuth)
	}
	var sent map[string]any
	if err := json.Unmarshal([]byte(gotBody), &sent); err != nil {
		t.Fatal(err)
	}
	if sent["model"] != "deepseek-v4-flash" {
		t.Errorf("model not passthrough: %v", sent["model"])
	}
	if sent["reasoning_effort"] != "high" {
		t.Errorf("reasoning_effort not passthrough: %v", sent["reasoning_effort"])
	}
	if !strings.Contains(respBody, "upstream-ok") {
		t.Errorf("response not passthrough: %s", respBody)
	}
}

// TestFailoverOn5xx 验证上游 5xx 时自动切换到下一个上游。
// 选上游是加权随机的,单次请求不一定命中坏上游,因此循环直到坏上游被选中。
func TestFailoverOn5xx(t *testing.T) {
	badCfg, _, badCalls := fakeUpstream(t, "bad", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"error":{"message":"boom","type":"server_error"}}`))
	})
	goodCfg, _, goodCalls := fakeUpstream(t, "good", okCompletion("good-ok"))
	gw := testGateway(t, []UpstreamConfig{badCfg, goodCfg}, nil, 3)

	body := `{"model":"m1","messages":[{"role":"user","content":"hi"}]}`
	for i := 0; i < 20 && badCalls.Load() == 0; i++ {
		resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("status = %d, body = %s", resp.StatusCode, respBody)
		}
	}
	require.GreaterOrEqual(t, badCalls.Load(), int32(1), "坏上游应被选中过")
	require.GreaterOrEqual(t, goodCalls.Load(), badCalls.Load(), "每次坏上游失败都应切换到好上游")
}

// TestAllUpstreamsFailed 验证全部上游失败时透传最后一次尝试的上游错误响应。
func TestAllUpstreamsFailed(t *testing.T) {
	u1Cfg, _, _ := fakeUpstream(t, "u1", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{"error":{"message":"u1 down"}}`))
	})
	u2Cfg, _, _ := fakeUpstream(t, "u2", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{"error":{"message":"u2 down"}}`))
	})
	gw := testGateway(t, []UpstreamConfig{u1Cfg, u2Cfg}, nil, 3)

	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{"model":"m1","messages":[]}`)
	if resp.StatusCode != http.StatusBadGateway {
		t.Fatalf("status = %d, body = %s", resp.StatusCode, respBody)
	}
	if !strings.Contains(respBody, "down") {
		t.Errorf("expected an upstream error body, got %s", respBody)
	}
}

// TestClientErrorNotRetried 验证 4xx(非 429)不重试:直接透传,其他上游不被打扰。
func TestClientErrorNotRetried(t *testing.T) {
	badCfg, _, badCalls := fakeUpstream(t, "bad", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"error":{"message":"invalid key","type":"invalid_request_error"}}`))
	})
	badCfg.Weight = 100 // 权重远大于 good,确保选到 bad
	goodCfg, _, goodCalls := fakeUpstream(t, "good", okCompletion("never-called"))
	goodCfg.Weight = 1
	gw := testGateway(t, []UpstreamConfig{badCfg, goodCfg}, nil, 3)

	body := `{"model":"m1","messages":[]}`
	// 由于 bad 权重高,第一次请求几乎必选 bad → 401 → 直接返回(不重试)
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, body = %s", resp.StatusCode, respBody)
	}
	if !strings.Contains(respBody, "invalid key") {
		t.Errorf("expected upstream 401 body passthrough, got %s", respBody)
	}
	require.GreaterOrEqual(t, badCalls.Load(), int32(1), "401 上游应被选中")
	require.Zero(t, goodCalls.Load(), "4xx 不得重试到其他上游")
}

// TestRetryOn429 验证 429 限流会切换重试。
func TestRetryOn429(t *testing.T) {
	busyCfg, _, busyCalls := fakeUpstream(t, "busy", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
		w.Write([]byte(`{"error":{"message":"rate limited","type":"rate_limit_error"}}`))
	})
	busyCfg.Weight = 100 // 权重远大于 good,确保选到 busy
	goodCfg, _, goodCalls := fakeUpstream(t, "good", okCompletion("after-429"))
	goodCfg.Weight = 1
	gw := testGateway(t, []UpstreamConfig{busyCfg, goodCfg}, nil, 3)

	body := `{"model":"m1","messages":[]}`
	resp, respBody := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, body = %s", resp.StatusCode, respBody)
	}
	require.GreaterOrEqual(t, busyCalls.Load(), int32(1), "429 上游应被选中")
	require.GreaterOrEqual(t, goodCalls.Load(), busyCalls.Load(), "每次 429 都应切换到好上游")
}

// TestAuth 验证本地多 Key 鉴权。
func TestAuth(t *testing.T) {
	upCfg, _, _ := fakeUpstream(t, "u1", okCompletion("authed"))
	gw := testGateway(t, []UpstreamConfig{upCfg}, []string{"sk-local-1", "sk-local-2"}, 0)

	if resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{}`); resp.StatusCode != http.StatusUnauthorized {
		t.Errorf("no auth: status = %d, want 401", resp.StatusCode)
	}
	if resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "Bearer wrong", `{}`); resp.StatusCode != http.StatusUnauthorized {
		t.Errorf("wrong key: status = %d, want 401", resp.StatusCode)
	}
	if resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "Bearer sk-local-2", `{}`); resp.StatusCode != http.StatusOK {
		t.Errorf("right key: status = %d, want 200", resp.StatusCode)
	}
}

// TestModelsMerge 验证 /v1/models 跨上游合并去重。
func TestModelsMerge(t *testing.T) {
	u1Cfg, _, _ := fakeUpstream(t, "u1", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"object":"list","data":[{"id":"a-model","object":"model"},{"id":"b-model","object":"model"}]}`))
	})
	u2Cfg, _, _ := fakeUpstream(t, "u2", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"object":"list","data":[{"id":"b-model","object":"model"},{"id":"c-model","object":"model"}]}`))
	})
	gw := testGateway(t, []UpstreamConfig{u1Cfg, u2Cfg}, nil, 0)

	resp, respBody := doRelay(t, gw, http.MethodGet, "/v1/models", "", "")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	var list struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.Unmarshal([]byte(respBody), &list); err != nil {
		t.Fatal(err)
	}
	ids := []string{}
	for _, d := range list.Data {
		ids = append(ids, d.ID)
	}
	got := strings.Join(ids, ",")
	if got != "a-model,b-model,c-model" {
		t.Errorf("merged models = %q, want a-model,b-model,c-model", got)
	}
}

// TestSingleConcurrency 验证单并发:慢上游在处理期间不会收到第二个并发请求。
func TestSingleConcurrency(t *testing.T) {
	var inflight atomic.Int32
	var maxInflight atomic.Int32
	start := make(chan struct{})
	upCfg, _, _ := fakeUpstream(t, "slow", func(w http.ResponseWriter, r *http.Request) {
		cur := inflight.Add(1)
		for {
			prev := maxInflight.Load()
			if cur <= prev || maxInflight.CompareAndSwap(prev, cur) {
				break
			}
		}
		defer inflight.Add(-1)
		<-start // 所有并发请求都到达上游后才放行,便于统计峰值
		okCompletion("slow-ok")(w, r)
	})
	gw := testGateway(t, []UpstreamConfig{upCfg}, nil, 0)

	done := make(chan bool, 2)
	for i := 0; i < 2; i++ {
		go func() {
			resp, _ := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{"model":"m1","messages":[]}`)
			done <- resp.StatusCode == http.StatusOK
		}()
	}
	// 等第一个请求进入上游后,给第二个请求时间到达闸门;
	// 单并发下第二个必须阻塞在闸门上,不能同时进入上游。
	for maxInflight.Load() == 0 {
		time.Sleep(5 * time.Millisecond)
	}
	time.Sleep(100 * time.Millisecond)
	if got := inflight.Load(); got > 1 {
		t.Fatalf("upstream inflight = %d, want 1 (second request must queue)", got)
	}
	close(start)
	for i := 0; i < 2; i++ {
		if !<-done {
			t.Fatal("request failed")
		}
	}
	if maxInflight.Load() > 1 {
		t.Errorf("max concurrent upstream requests = %d, want <= 1", maxInflight.Load())
	}
}
