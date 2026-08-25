package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"time"
)

// Gateway 转发网关:本地 OpenAI 兼容出口 -> 上游账号池。
type Gateway struct {
	pool   *Pool
	cfg    *Config
	client *http.Client
	models *modelsCache
}

func NewGateway(cfg *Config) *Gateway {
	transport := &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   30 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		TLSHandshakeTimeout:   30 * time.Second,
		ResponseHeaderTimeout: 120 * time.Second, // 只限制响应头,流式 body 不受限
		DisableCompression:    true,              // 原样透传压缩与流,不做透明 gzip
		MaxIdleConns:          100,
		MaxIdleConnsPerHost:   8,
		IdleConnTimeout:       90 * time.Second,
	}
	return &Gateway{
		pool:   NewPool(cfg),
		cfg:    cfg,
		client: &http.Client{Transport: transport},
		models: newModelsCache(cfg),
	}
}

// handleRelay 处理所有 /v1/* 请求:鉴权 -> 选上游 -> 字节级透传 -> 失败换上游重试。
func (g *Gateway) handleRelay(w http.ResponseWriter, r *http.Request) {
	if !checkAuth(r, g.cfg) {
		writeUnauthorized(w)
		return
	}
	path := r.URL.Path
	if path == "/v1/models" {
		g.handleModels(w, r)
		return
	}
	if !strings.HasPrefix(path, "/v1/") {
		http.NotFound(w, r)
		return
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, g.cfg.MaxBodySize+1))
	if err != nil {
		writeError(w, http.StatusBadRequest, nil, "read request body failed")
		return
	}
	if int64(len(body)) > g.cfg.MaxBodySize {
		writeError(w, http.StatusRequestEntityTooLarge, nil, "request body too large")
		return
	}

	// 请求要求思考时,校验上游响应确实包含思考内容,否则切换重试
	requireThinking := requestHasThinking(body)
	// 按请求 model 过滤上游(models 通配符路由)
	model := requestModel(body)

	blacklist := make(map[*Upstream]bool)
	var lastStatus int
	var lastHeader http.Header
	var lastBody []byte
	var lastErr error

	for attempt := 0; attempt <= g.cfg.RetryTimes; attempt++ {
		up, release, err := g.acquireFresh(r.Context(), model, blacklist)
		if err != nil {
			return // 客户端断开
		}
		if up == nil {
			break // 可用上游都已失败过,无重试目标
		}

		resp, err := g.forward(r, up, path, body)
		if err != nil {
			release()
			up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
			blacklist[up] = true
			lastErr = err
			log.Printf("upstream %s request failed: %v (attempt %d)", up.name, err, attempt+1)
			continue
		}

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			err = g.copyResponseWithThinkingCheck(w, resp, requireThinking)
			if err != nil {
				// 思考内容缺失(或读流出错):视为该上游不合格,切换重试
				resp.Body.Close()
				release()
				up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
				blacklist[up] = true
				lastErr = err
				log.Printf("upstream %s no thinking content, switching: %v (attempt %d)", up.name, err, attempt+1)
				continue
			}
			up.reportSuccess()
			resp.Body.Close()
			release()
			log.Printf("upstream %s -> %d %s (attempt %d)", up.name, resp.StatusCode, path, attempt+1)
			return
		}

		// 非 2xx:读错误 body 供透传/日志
		errBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		resp.Body.Close()
		release()
		lastStatus = resp.StatusCode
		lastHeader = resp.Header.Clone()
		lastBody = errBody

		if shouldRetryStatus(resp.StatusCode) {
			up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
			blacklist[up] = true
			log.Printf("upstream %s -> %d %s, switching (attempt %d)", up.name, resp.StatusCode, path, attempt+1)
			continue
		}
		// 4xx 用户错误(非 429)重试无意义,原样透传给客户端
		copyErrorResponse(w, resp.StatusCode, resp.Header, errBody)
		return
	}

	// 全部上游失败:优先透传最后一次上游错误响应,否则返回 502
	if lastStatus > 0 {
		copyErrorResponse(w, lastStatus, lastHeader, lastBody)
		return
	}
	if lastErr != nil {
		writeError(w, http.StatusBadGateway, nil, "all upstreams failed: "+lastErr.Error())
		return
	}
	writeError(w, http.StatusServiceUnavailable, nil, "no upstream available")
}

// forward 把请求原样转发到指定上游:仅替换 host 与 Authorization。
func (g *Gateway) forward(r *http.Request, up *Upstream, path string, body []byte) (*http.Response, error) {
	target := up.baseURL + path
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	req, err := http.NewRequestWithContext(r.Context(), r.Method, target, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	for k, vs := range r.Header {
		if hopByHop(k) {
			continue
		}
		for _, v := range vs {
			req.Header.Add(k, v)
		}
	}
	req.Header.Set("Authorization", "Bearer "+up.apiKey)
	if req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", "application/json")
	}
	return g.client.Do(req)
}

// acquireFresh 获取一个不在本次请求黑名单中、且匹配 model 的可用上游。
// 加权随机可能反复选中已失败的上游,这里内层循环跳过它们,不消耗重试次数;
// 可用上游全部失败过时返回 (nil, nil, nil)。
func (g *Gateway) acquireFresh(ctx context.Context, model string, blacklist map[*Upstream]bool) (*Upstream, func(), error) {
	for {
		if g.pool.AllBlacklisted(model, blacklist) {
			return nil, nil, nil
		}
		up, release, err := g.pool.Acquire(ctx, model)
		if err != nil {
			return nil, nil, err
		}
		if !blacklist[up] {
			return up, release, nil
		}
		release()
	}
}

// shouldRetryStatus 判断上游状态码是否值得换上游重试:429 与 5xx 重试,
// 其余 4xx 不重试(用户错误,重试无意义)。
func shouldRetryStatus(status int) bool {
	return status == http.StatusTooManyRequests || status >= 500
}

// copyResponse 把上游 2xx 响应原样写回客户端(流式透明)。
func copyResponse(w http.ResponseWriter, resp *http.Response) {
	for k, vs := range resp.Header {
		if hopByHop(k) {
			continue
		}
		for _, v := range vs {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// copyErrorResponse 把上游错误响应原样透传给客户端。
func copyErrorResponse(w http.ResponseWriter, status int, header http.Header, body []byte) {
	for k, vs := range header {
		if hopByHop(k) {
			continue
		}
		for _, v := range vs {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(status)
	w.Write(body)
}

func writeError(w http.ResponseWriter, status int, header http.Header, message string) {
	if header != nil {
		for k, vs := range header {
			if !hopByHop(k) {
				for _, v := range vs {
					w.Header().Add(k, v)
				}
			}
		}
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	body := fmt.Sprintf(`{"error":{"message":%q,"type":"upstream_error","code":%d}}`, message, status)
	w.Write([]byte(body))
}

// hopByHop 过滤逐跳头,避免透传给客户端。
func hopByHop(k string) bool {
	switch strings.ToLower(k) {
	case "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
		"te", "trailer", "transfer-encoding", "upgrade", "host", "content-length":
		return true
	}
	return false
}
