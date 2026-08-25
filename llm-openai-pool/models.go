package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

// modelsCache 合并各上游 /v1/models 的结果并缓存。
type modelsCache struct {
	ttl     time.Duration
	mu      sync.Mutex
	models  []string
	fetched time.Time
}

func newModelsCache(cfg *Config) *modelsCache {
	return &modelsCache{ttl: time.Duration(cfg.ModelsCacheTTL) * time.Second}
}

// handleModels 返回所有上游模型 id 的并集。非阻塞占用上游(忙的跳过),
// 全部失败返回 503,结果按 ttl 缓存。
func (g *Gateway) handleModels(w http.ResponseWriter, r *http.Request) {
	if !checkAuth(r, g.cfg) {
		writeUnauthorized(w)
		return
	}
	g.models.mu.Lock()
	if time.Since(g.models.fetched) < g.models.ttl && g.models.models != nil {
		models := g.models.models
		g.models.mu.Unlock()
		writeModels(w, models)
		return
	}
	g.models.mu.Unlock()

	models, ok := g.fetchAllModels(r)
	if !ok {
		writeError(w, http.StatusServiceUnavailable, nil, "all upstreams failed to provide model list")
		return
	}
	g.models.mu.Lock()
	g.models.models = models
	g.models.fetched = time.Now()
	g.models.mu.Unlock()
	writeModels(w, models)
}

// fetchAllModels 并发向各未熔断上游拉取模型列表,合并去重排序。
func (g *Gateway) fetchAllModels(r *http.Request) ([]string, bool) {
	type result struct {
		models []string
		ok     bool
	}
	now := time.Now()
	resCh := make(chan result, len(g.pool.upstreams))
	var wg sync.WaitGroup
	for _, up := range g.pool.upstreams {
		if !up.available(now) {
			continue
		}
		// 非阻塞占位:单并发的上游正在服务请求时跳过,不排队
		select {
		case up.sem <- struct{}{}:
		default:
			continue
		}
		wg.Add(1)
		go func(up *Upstream) {
			defer wg.Done()
			defer func() { <-up.sem }()
			models, err := g.fetchOneModels(r, up)
			if err != nil {
				log.Printf("upstream %s /v1/models failed: %v", up.name, err)
				resCh <- result{ok: false}
				return
			}
			resCh <- result{models: models, ok: true}
		}(up)
	}
	wg.Wait()
	close(resCh)

	seen := make(map[string]bool)
	var merged []string
	anyOK := false
	for res := range resCh {
		if !res.ok {
			continue
		}
		anyOK = true
		for _, m := range res.models {
			if !seen[m] {
				seen[m] = true
				merged = append(merged, m)
			}
		}
	}
	sort.Strings(merged)
	return merged, anyOK
}

// fetchOneModels 从单个上游拉取 /v1/models,解析 data[].id。
func (g *Gateway) fetchOneModels(r *http.Request, up *Upstream) ([]string, error) {
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, up.baseURL+"/v1/models", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+up.apiKey)
	req.Header.Set("Accept", "application/json")
	resp, err := g.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	var list struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &list); err != nil {
		return nil, err
	}
	models := make([]string, 0, len(list.Data))
	for _, d := range list.Data {
		if strings.TrimSpace(d.ID) != "" {
			models = append(models, d.ID)
		}
	}
	return models, nil
}

func writeModels(w http.ResponseWriter, models []string) {
	data := make([]map[string]string, 0, len(models))
	for _, m := range models {
		data = append(data, map[string]string{"id": m, "object": "model", "owned_by": "openai-pool"})
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"object": "list", "data": data})
}
