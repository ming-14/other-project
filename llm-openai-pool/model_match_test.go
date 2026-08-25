package main

import (
	"context"
	"net/http"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestGlobMatch(t *testing.T) {
	cases := []struct {
		pattern, name string
		want          bool
	}{
		{"*", "anything", true},
		{"*", "", true},
		{"deepseek-*", "deepseek-v4-flash", true},
		{"deepseek-*", "deepseek-v4", true},
		{"deepseek-*", "gpt-4", false},
		{"gpt-*", "gpt-4o", true},
		{"gpt-*", "gpt-4-turbo", true},
		{"gpt-4?", "gpt-4o", true},
		{"gpt-4?", "gpt-4o-mini", false},
		{"gpt-4?*", "gpt-4o-mini", true},
		{"*-flash", "deepseek-v4-flash", true},
		{"*-flash", "gpt-4", false},
		{"org/*", "org/model", true},
		{"org/*", "other/model", false},
		{"", "", true},
		{"", "anything", false},
		{"a", "a", true},
		{"a", "b", false},
		{"?", "a", true},
		{"?", "ab", false},
	}
	for _, c := range cases {
		t.Run(c.pattern+"/"+c.name, func(t *testing.T) {
			require.Equal(t, c.want, globMatch(c.pattern, c.name))
		})
	}
}

func TestMatchesModel(t *testing.T) {
	up := &Upstream{models: []string{"deepseek-*", "gpt-4?"}}
	require.True(t, up.matchesModel("deepseek-v4-flash"))
	require.True(t, up.matchesModel("gpt-4o"))
	require.False(t, up.matchesModel("claude-3"))
	require.False(t, up.matchesModel("gpt-5"))
	require.True(t, up.matchesModel(""), "model 为空时不过滤")
}

func TestMatchesModelEmpty(t *testing.T) {
	up := &Upstream{} // models 为空
	require.True(t, up.matchesModel("anything"))
	require.True(t, up.matchesModel(""))
}

func TestAcquireFiltersByModel(t *testing.T) {
	ctx := context.Background()
	// 两个上游,一个只匹配 deepseek-*,一个只匹配 gpt-*
	deepseek := UpstreamConfig{Name: "ds", BaseURL: "https://ds.test/v1", APIKey: "k", Weight: 1, MaxConcurrency: 1, Models: []string{"deepseek-*"}}
	gpt := UpstreamConfig{Name: "gpt", BaseURL: "https://gpt.test/v1", APIKey: "k", Weight: 1, MaxConcurrency: 1, Models: []string{"gpt-*"}}
	p := testPool(deepseek, gpt)

	// 请求 deepseek 模型 → 只返回 ds
	u, release, err := p.Acquire(ctx, "deepseek-v4-flash")
	require.NoError(t, err)
	require.Equal(t, "ds", u.name)
	release()

	// 请求 gpt 模型 → 只返回 gpt
	u2, release2, err := p.Acquire(ctx, "gpt-4o")
	require.NoError(t, err)
	require.Equal(t, "gpt", u2.name)
	release2()

	// 请求不匹配的模型 → 死锁?Acquire 会等待,但 ctx 取消后应返回
	ctx2, cancel := context.WithCancel(ctx)
	cancel()
	_, _, err = p.Acquire(ctx2, "claude-3")
	require.Error(t, err, "无匹配模型时应返回错误")
}

func TestGatewayModelRouting(t *testing.T) {
	dsCfg, _, dsCalls := fakeUpstream(t, "ds", func(w http.ResponseWriter, r *http.Request) {
		okCompletion("ds-ok")(w, r)
	})
	dsCfg.Models = []string{"deepseek-*"}
	gptCfg, _, gptCalls := fakeUpstream(t, "gpt", func(w http.ResponseWriter, r *http.Request) {
		okCompletion("gpt-ok")(w, r)
	})
	gptCfg.Models = []string{"gpt-*"}
	gw := testGateway(t, []UpstreamConfig{dsCfg, gptCfg}, nil, 0)

	// 请求 deepseek 模型 → 只打到 ds
	resp, body := doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{"model":"deepseek-v4-flash","messages":[]}`)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, body, "ds-ok")
	require.Equal(t, int32(1), dsCalls.Load())
	require.Equal(t, int32(0), gptCalls.Load())

	// 请求 gpt 模型 → 只打到 gpt
	resp, body = doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{"model":"gpt-4o","messages":[]}`)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Contains(t, body, "gpt-ok")
	require.Equal(t, int32(1), dsCalls.Load())
	require.Equal(t, int32(1), gptCalls.Load())

	// 请求不匹配的模型 → 503(无可用上游)
	resp, _ = doRelay(t, gw, http.MethodPost, "/v1/chat/completions", "", `{"model":"claude-3","messages":[]}`)
	require.Equal(t, http.StatusServiceUnavailable, resp.StatusCode)
}