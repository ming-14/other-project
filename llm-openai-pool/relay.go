package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
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
		ResponseHeaderTimeout: time.Duration(cfg.ResponseHeaderTimeout) * time.Second, // 只限制响应头,流式 body 不受限
		DisableCompression:    true,                                                   // 原样透传压缩与流,不做透明 gzip
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

// newReqID 生成请求追踪 ID,用于把同一请求的日志串起来。
func newReqID() string {
	var b [4]byte
	if _, err := rand.Read(b[:]); err != nil {
		return fmt.Sprintf("req-%d", time.Now().UnixNano()%1_000_000_000)
	}
	return fmt.Sprintf("req-%08x", b)
}

// fmtElapsed 格式化请求耗时:<1s 显示毫秒,否则显示秒。
func fmtElapsed(d time.Duration) string {
	if d < time.Second {
		return fmt.Sprintf("%dms", d.Milliseconds())
	}
	return fmt.Sprintf("%.1fs", d.Seconds())
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

	reqID := newReqID()
	start := time.Now()

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
		// 并发抢答模式:同时请求多个上游,先到先得
		if g.cfg.ParallelFetch > 1 {
			if g.handleRelayParallel(w, r, path, body, model, requireThinking, blacklist, &lastStatus, &lastHeader, &lastBody, &lastErr, attempt, reqID, start) {
				return
			}
			// 可用上游已全部失败过,无重试目标
			if g.pool.AllBlacklisted(model, blacklist) {
				break
			}
			continue
		}

		up, release, err := g.acquireFresh(r.Context(), reqID, model, blacklist)
		if err != nil {
			return // 客户端断开
		}
		if up == nil {
			break // 可用上游都已失败过,无重试目标
		}

		// 原地重试:对当前上游尝试 retry_times 次(至少 1 次)
		maxTries := g.cfg.RetryTimes
		if maxTries < 1 {
			maxTries = 1
		}
		released := false
		for tries := 1; tries <= maxTries; tries++ {
			log.Printf("[%s] → %s (尝试%d/%d)", reqID, up.name, tries, g.cfg.RetryTimes)
			resp, ferr := g.forward(r.Context(), r, up, path, body)
			if ferr != nil {
				if !released {
					release()
					released = true
				}
				up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
				blacklist[up] = true
				lastErr = ferr
				log.Printf("[%s] ✗ %s 请求失败: %v (尝试%d/%d)", reqID, up.name, ferr, tries, g.cfg.RetryTimes)
				if tries < g.cfg.RetryTimes {
					g.retryDelay()
					continue
				}
				break // 重试耗尽,换上游
			}

			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				ok, payload := g.validateResponse(resp, requireThinking)
				if ok {
					err := g.passthroughPayload(w, payload, nil)
					if err != nil {
						up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
						blacklist[up] = true
						lastErr = err
						if errors.Is(err, errStreamIncomplete) {
							log.Printf("[%s] ✗ %s -> %d 流不完整, 已补发终止事件并熔断 (第%d轮)", reqID, up.name, resp.StatusCode, tries)
						} else {
							log.Printf("[%s] ✗ %s -> %d 透传中断: %v (第%d轮)", reqID, up.name, resp.StatusCode, err, tries)
						}
						payload.resp.Body.Close()
						if !released {
							release()
							released = true
						}
						return
					}
					up.reportSuccess()
					payload.resp.Body.Close()
					if !released {
						release()
						released = true
					}
					log.Printf("[%s] ✓ %s -> %d %s, 用时 %s (尝试%d/%d)", reqID, up.name, resp.StatusCode, path, fmtElapsed(time.Since(start)), tries, g.cfg.RetryTimes)
					return
				}
				// 校验失败(无body/无思考)
				log.Printf("[%s] ✗ %s -> %d 校验失败(无body/无思考), 原地重试 (尝试%d/%d)", reqID, up.name, resp.StatusCode, tries, g.cfg.RetryTimes)
			} else {
				log.Printf("[%s] ✗ %s -> %d, 原地重试 (尝试%d/%d)", reqID, up.name, resp.StatusCode, tries, g.cfg.RetryTimes)
			}

			// 记录失败信息
			errBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
			resp.Body.Close()
			lastStatus = resp.StatusCode
			lastHeader = resp.Header.Clone()
			lastBody = errBody
			lastErr = fmt.Errorf("上游 %s 返回 %d", up.name, resp.StatusCode)
			up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
			blacklist[up] = true

			if tries < g.cfg.RetryTimes {
				g.retryDelay()
				continue
			}
			// 重试耗尽,换上游
			if !released {
				release()
				released = true
			}
		}
	}

	// 全部上游失败:优先透传最后一次上游错误响应,否则返回 502
	// 全部上游失败:
	// - 4xx/5xx:透传最后一次上游错误响应
	// - 2xx 校验失败(无思考/无body):返回 502
	// - 无可用上游(模型不匹配/全部熔断):返回 503
	if lastStatus >= 400 {
		log.Printf("[%s] ✗ 全部上游失败, 透传最后一次错误 %d, 用时 %s", reqID, lastStatus, fmtElapsed(time.Since(start)))
		copyErrorResponse(w, lastStatus, lastHeader, lastBody)
		return
	}
	if lastStatus > 0 {
		log.Printf("[%s] ✗ 全部上游校验失败(2xx 无思考/无body), 用时 %s", reqID, fmtElapsed(time.Since(start)))
		writeError(w, http.StatusBadGateway, nil, "all upstreams failed: 响应不合格(无思考内容或无body)")
		return
	}
	if lastErr != nil {
		log.Printf("[%s] ✗ 全部上游失败: %v, 用时 %s", reqID, lastErr, fmtElapsed(time.Since(start)))
		writeError(w, http.StatusBadGateway, nil, "all upstreams failed: "+lastErr.Error())
		return
	}
	log.Printf("[%s] ✗ 无可用上游, 用时 %s", reqID, fmtElapsed(time.Since(start)))
	writeError(w, http.StatusServiceUnavailable, nil, "no upstream available")
}

// respPayload 校验通过后的响应载荷,用于透传给客户端。
type respPayload struct {
	resp     *http.Response
	first    []byte        // 非思考:预读的第一块 body
	buffered *bytes.Buffer // 思考流式:已缓冲的前 N 个事件
	br       *bufio.Reader // 思考流式:剩余流
	body     []byte        // 非流式:完整 body
	isStream bool
	thinking bool // 是否经过思考校验
}

// validateResponse 校验上游 2xx 响应是否"合格":有 body 数据,且思考请求包含思考内容。
// 返回 ok 与透传载荷;ok=false 时调用方可原地重试该上游。
func (g *Gateway) validateResponse(resp *http.Response, requireThinking bool) (bool, *respPayload) {
	if !requireThinking {
		timeout := g.bodyTimeout(resp)
		first := make([]byte, 32*1024)
		n, _ := readFirstWithTimeout(resp.Body, first, timeout)
		if n <= 0 {
			return false, nil // 幽灵请求
		}
		return true, &respPayload{resp: resp, first: first[:n], isStream: isStreamingResponse(resp)}
	}
	if isStreamingResponse(resp) {
		found, buffered, br, err := g.checkStreamingThinking(resp)
		if err != nil {
			return false, nil
		}
		if !found {
			return false, nil // 无思考内容
		}
		return true, &respPayload{resp: resp, buffered: buffered, br: br, isStream: true, thinking: true}
	}
	body, err := g.checkNonStreamingThinking(resp)
	if err != nil {
		return false, nil
	}
	return true, &respPayload{resp: resp, body: body, thinking: true}
}

// passthroughPayload 把校验通过的响应透传给客户端。onReady 在写任何字节前调用
// (并行模式用于取消其他上游并记录"已中断")。返回错误表示透传中断(响应已部分发出)。
func (g *Gateway) passthroughPayload(w http.ResponseWriter, v *respPayload, onReady func()) error {
	if onReady != nil {
		onReady()
	}
	copyResponseHeaders(w, v.resp.Header)
	w.WriteHeader(v.resp.StatusCode)

	if v.thinking {
		// 思考校验通过:写缓冲内容 + 剩余流
		if v.isStream {
			w.Write(v.buffered.Bytes())
			idleTimeout := time.Duration(g.cfg.StreamIdleTimeout) * time.Second
			return g.copyStreamToClient(w, v.br, v.resp.Body, idleTimeout, scanSSECompletion(v.buffered.Bytes()))
		}
		w.Write(v.body)
		return nil
	}

	// 非思考:写预读第一块 + 剩余
	w.Write(v.first)
	if v.isStream {
		return g.copyStreamToClient(w, v.resp.Body, v.resp.Body, time.Duration(g.cfg.StreamIdleTimeout)*time.Second, false)
	}
	data, err := readAllWithTimeout(v.resp.Body, 1<<20, time.Duration(g.cfg.UpstreamTimeout)*time.Second)
	if err != nil {
		log.Printf("non-streaming body read timeout: %v", err)
		return nil
	}
	w.Write(data)
	return nil
}

// retryDelay 原地重试前的等待(可配置,默认 0=立即)。
func (g *Gateway) retryDelay() {
	if g.cfg.RetryDelayMs > 0 {
		time.Sleep(time.Duration(g.cfg.RetryDelayMs) * time.Millisecond)
	}
}

// forward 把请求原样转发到指定上游:仅替换 host 与 Authorization。
// ctx 控制请求生命周期,并发抢答时可取消在途请求。
func (g *Gateway) forward(ctx context.Context, r *http.Request, up *Upstream, path string, body []byte) (*http.Response, error) {
	target := up.baseURL + path
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	req, err := http.NewRequestWithContext(ctx, r.Method, target, bytes.NewReader(body))
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
// 可用上游全部失败过时返回 (nil, nil, nil)。reqID 用于日志跟踪占用者。
func (g *Gateway) acquireFresh(ctx context.Context, reqID, model string, blacklist map[*Upstream]bool) (*Upstream, func(), error) {
	for {
		if g.pool.AllBlacklisted(model, blacklist) {
			return nil, nil, nil
		}
		up, release, err := g.pool.Acquire(ctx, model)
		if err != nil {
			return nil, nil, err
		}
		if !blacklist[up] {
			up.addHolder(reqID)
			innerRelease := release
			release = func() {
				up.removeHolder(reqID)
				innerRelease()
			}
			return up, release, nil
		}
		release()
	}
}

// acquireParallel 获取最多 n 个可用的未黑名单上游(非阻塞占位)。
// 至少返回 1 个;全部忙时阻塞等待空位;ctx 取消返回错误。
// 全部可用上游已黑名单时返回 (nil, nil, nil) 表示无重试目标。
// reqID 用于日志跟踪占用者。
func (g *Gateway) acquireParallel(ctx context.Context, reqID, model string, n int, blacklist map[*Upstream]bool) ([]*Upstream, []func(), error) {
	if n > len(g.pool.upstreams) {
		n = len(g.pool.upstreams)
	}
	for {
		now := time.Now()
		candidates := make([]*Upstream, 0)
		for _, u := range g.pool.upstreams {
			if u.matchesModel(model) && u.available(now) && !blacklist[u] {
				candidates = append(candidates, u)
			}
		}
		if len(candidates) == 0 {
			if g.pool.AllBlacklisted(model, blacklist) {
				return nil, nil, nil // 所有可用上游都已失败
			}
			// 全部熔断中:等冷却
			if !g.pool.wait(ctx, 500*time.Millisecond) {
				return nil, nil, ctx.Err()
			}
			continue
		}

		ups := make([]*Upstream, 0, n)
		releases := make([]func(), 0, n)
		for _, u := range weightedShuffle(candidates) {
			if len(ups) >= n {
				break
			}
			select {
			case u.sem <- struct{}{}:
				if u.available(now) {
					up := u
					up.addHolder(reqID)
					release := func() {
						<-up.sem
						up.removeHolder(reqID)
						g.pool.notifyRelease()
					}
					ups = append(ups, up)
					releases = append(releases, release)
				} else {
					<-u.sem
				}
			default:
			}
		}
		if len(ups) == 0 {
			// 全部忙:等空位释放
			if !g.pool.wait(ctx, 0) {
				return nil, nil, ctx.Err()
			}
			continue
		}
		return ups, releases, nil
	}
}

// parallelResult 并发抢答中单个上游的一次尝试结果。
type parallelResult struct {
	resp    *http.Response
	up      *Upstream
	release func()
	err     error
	cancel  context.CancelFunc // 取消该上游的请求(不取消胜利者)
}

// handleRelayParallel 并发抢答:同时向多个上游发起请求,每个上游独立原地重试
// (最多 retry_times 次,间隔 retry_delay_ms)。第一个返回合格响应的胜出并透传,
// 其余请求立即取消。全部失败返回 false(由调用方返回错误)。
func (g *Gateway) handleRelayParallel(
	w http.ResponseWriter, r *http.Request, path string, body []byte,
	model string, requireThinking bool,
	blacklist map[*Upstream]bool,
	lastStatus *int, lastHeader *http.Header, lastBody *[]byte, lastErr *error,
	attempt int, reqID string, start time.Time,
) bool {
	ups, releases, err := g.acquireParallel(r.Context(), reqID, model, g.cfg.ParallelFetch, blacklist)
	if err != nil {
		return true // 客户端断开
	}
	if len(ups) == 0 {
		return false // 无可用重试目标
	}

	sentNames := make([]string, 0, len(ups))
	for _, u := range ups {
		sentNames = append(sentNames, u.name)
	}
	maxTries := g.cfg.RetryTimes
	if maxTries < 1 {
		maxTries = 1
	}
	log.Printf("[%s] 并行抢答 → %s (每个上游最多试 %d 次)", reqID, strings.Join(sentNames, " "), maxTries)

	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	// 在途请求的取消管理:胜利者除外,取消其他
	var cancelMu sync.Mutex
	activeCancels := make(map[*Upstream]context.CancelFunc)
	registerCancel := func(up *Upstream, c context.CancelFunc) {
		cancelMu.Lock()
		activeCancels[up] = c
		cancelMu.Unlock()
	}
	unregisterCancel := func(up *Upstream) {
		cancelMu.Lock()
		delete(activeCancels, up)
		cancelMu.Unlock()
	}
	cancelOthers := func(winner *Upstream) {
		cancelMu.Lock()
		defer cancelMu.Unlock()
		for up, c := range activeCancels {
			if up != winner {
				c()
			}
		}
	}

	// 每个上游一次尝试的结果
	type upResult struct {
		payload   *respPayload
		up        *Upstream
		release   func()
		err       error
		tries     int
		status    int         // 最后一次 HTTP 状态(失败时)
		errBody   []byte      // 最后一次错误响应 body
		errHeader http.Header // 最后一次错误响应头
	}
	resultCh := make(chan upResult, len(ups))

	for i, up := range ups {
		go func(up *Upstream, release func()) {
			sent := false
			defer func() {
				if !sent {
					release() // 失败/取消:释放占位
				}
			}()

			// goroutine 内不写任何共享变量(blacklist/lastStatus/lastErr),
			// 失败信息通过 upResult 传回,由主协程统一写入,避免并发 map 写崩溃
			var lastStatus int
			var lastHeader http.Header
			var lastBody []byte
			var lastFailure error

			for tries := 1; tries <= maxTries; tries++ {
				if ctx.Err() != nil {
					resultCh <- upResult{up: up, err: context.Canceled, tries: tries}
					return
				}
				reqCtx, reqCancel := context.WithCancel(ctx)
				registerCancel(up, reqCancel)
				resp, ferr := g.forward(reqCtx, r, up, path, body)
				unregisterCancel(up)

				if ferr != nil {
					if errors.Is(ferr, context.Canceled) {
						resultCh <- upResult{up: up, err: ferr, tries: tries}
						return
					}
					lastFailure = ferr
					up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
					log.Printf("[%s] ✗ %s 请求失败: %v (尝试%d/%d)", reqID, up.name, ferr, tries, g.cfg.RetryTimes)
					g.retryDelay()
					continue
				}

				if resp.StatusCode >= 200 && resp.StatusCode < 300 {
					// 2xx:校验合格性(有 body + 思考内容)
					ok, payload := g.validateResponse(resp, requireThinking)
					if ok {
						sent = true
						resultCh <- upResult{payload: payload, up: up, release: release, tries: tries}
						return
					}
					log.Printf("[%s] ✗ %s -> %d 无 body/无思考, 原地重试 (尝试%d/%d)", reqID, up.name, resp.StatusCode, tries, g.cfg.RetryTimes)
				} else {
					log.Printf("[%s] ✗ %s -> %d, 原地重试 (尝试%d/%d)", reqID, up.name, resp.StatusCode, tries, g.cfg.RetryTimes)
				}

				// 失败:记录错误信息供最终透传
				errBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
				resp.Body.Close()
				lastStatus = resp.StatusCode
				lastHeader = resp.Header.Clone()
				lastBody = errBody
				lastFailure = fmt.Errorf("上游 %s 返回 %d", up.name, resp.StatusCode)
				up.reportFailure(g.pool.failThreshold, g.pool.cooldown)

				if tries < g.cfg.RetryTimes {
					g.retryDelay()
				}
			}
			// 重试耗尽,放弃
			resultCh <- upResult{up: up, err: lastFailure, tries: g.cfg.RetryTimes, status: lastStatus, errBody: lastBody, errHeader: lastHeader}
		}(up, releases[i])
	}

	// 主协程:等待第一个成功结果
	received := 0
	failedCount := 0
	for {
		select {
		case r := <-resultCh:
			received++
			if r.payload != nil {
				// 成功!取消其他在途请求,透传
				cancelOthers(r.up)
				err := g.passthroughPayload(w, r.payload, func() {
					logInterrupted(reqID, r.up.name, r.payload.resp.StatusCode, path, interruptedNames(sentNames, r.up.name), attempt+1)
				})
				if err != nil {
					r.up.reportFailure(g.pool.failThreshold, g.pool.cooldown)
					blacklist[r.up] = true
					if errors.Is(err, errStreamIncomplete) {
						log.Printf("[%s] ✗ %s -> %d 流不完整, 已补发终止事件并熔断 (第%d轮)", reqID, r.up.name, r.payload.resp.StatusCode, attempt+1)
					} else {
						log.Printf("[%s] ✗ %s -> %d 流透传中断: %v (第%d轮)", reqID, r.up.name, r.payload.resp.StatusCode, err, attempt+1)
					}
				} else {
					r.up.reportSuccess()
				}
				r.payload.resp.Body.Close()
				r.release()
				// 回收剩余结果:落选但已成功(sent=true)的上游 sem 必须释放,
				// 否则 busy 永久占用(goroutine 的 defer 因 sent=true 不会释放)
				for received < len(ups) {
					remaining := <-resultCh
					received++
					if remaining.payload != nil {
						remaining.payload.resp.Body.Close()
						remaining.release()
					}
				}
				log.Printf("[%s] 完成: %s 胜出, 用时 %s", reqID, r.up.name, fmtElapsed(time.Since(start)))
				return true
			}
			// 失败结果:由主协程统一写共享变量(blacklist/lastStatus/lastErr),
			// 避免多个 goroutine 并发写 map 导致崩溃
			if r.status > 0 {
				*lastStatus = r.status
				*lastHeader = r.errHeader
				*lastBody = r.errBody
			}
			if r.err != nil && !errors.Is(r.err, context.Canceled) {
				*lastErr = r.err
				blacklist[r.up] = true
			}
			failedCount++
			if failedCount >= len(ups) {
				return false // 全部上游失败
			}
		case <-ctx.Done():
			// 客户端断开:回收剩余结果,释放落选成功者的 sem
			for received < len(ups) {
				remaining := <-resultCh
				received++
				if remaining.payload != nil {
					remaining.payload.resp.Body.Close()
					remaining.release()
				}
			}
			return true // 客户端断开
		}
	}
}

// interruptedNames 计算已发送但未胜出的上游名列表(用于"已中断"日志)。
func interruptedNames(sentNames []string, winner string) []string {
	var out []string
	for _, n := range sentNames {
		if n != winner {
			out = append(out, n)
		}
	}
	return out
}

// logInterrupted 打印并发抢答的胜出和已中断日志。
func logInterrupted(reqID, name string, status int, path string, interrupted []string, attempt int) {
	if len(interrupted) > 0 {
		log.Printf("[%s] ✓ %s -> %d %s, 已中断: %s (第%d轮)", reqID, name, status, path, strings.Join(interrupted, " "), attempt)
	} else {
		log.Printf("[%s] ✓ %s -> %d %s (第%d轮)", reqID, name, status, path, attempt)
	}
}

// shouldRetryStatus 判断上游状态码是否值得换上游重试:429 与 5xx 重试,
// 其余 4xx 不重试(用户错误,重试无意义)。
func shouldRetryStatus(status int) bool {
	return status == http.StatusTooManyRequests || status >= 500
}

// copyResponse 把上游 2xx 响应原样写回客户端(流式透明)。
// 流程:先预读第一块 body(带超时,不写任何字节),确认上游真的开始返回数据后
// 调用 onReady 回调,再写响应头+第一块+剩余流。
// 预读失败(幽灵请求:有响应头但 body 迟迟无数据)返回 errNoBody,
// 调用方可安全切换上游(未写任何字节)。
// 流式响应透传时进行 SSE 完整性检查,不完整时自动补发终止事件修复。
func (g *Gateway) copyResponse(w http.ResponseWriter, resp *http.Response, onReady func()) error {
	timeout := g.bodyTimeout(resp)
	first := make([]byte, 32*1024)
	n, err := readFirstWithTimeout(resp.Body, first, timeout)
	if n <= 0 {
		_ = err // 统一按无 body 处理(err 可能是 io.EOF 或 nil)
		return errNoBody
	}

	// 预读通过,尚未向客户端写任何字节;回调让调用方取消其他上游/记录日志
	if onReady != nil {
		onReady()
	}

	copyResponseHeaders(w, resp.Header)
	w.WriteHeader(resp.StatusCode)
	w.Write(first[:n])

	if isStreamingResponse(resp) {
		return g.copyStreamToClient(w, resp.Body, resp.Body, time.Duration(g.cfg.StreamIdleTimeout)*time.Second, false)
	}
	if g.cfg.UpstreamTimeout > 0 {
		data, err := readAllWithTimeout(resp.Body, 1<<20, time.Duration(g.cfg.UpstreamTimeout)*time.Second)
		if err != nil {
			log.Printf("non-streaming body read timeout: %v", err)
			return nil
		}
		w.Write(data)
	} else {
		io.Copy(w, resp.Body)
	}
	return nil
}

// errNoBody 上游 2xx 响应无 body 数据(幽灵请求),尚未向客户端写任何字节,可安全切换。
var errNoBody = errors.New("upstream no body data")

// scanSSECompletion 扫描 SSE 数据,判断是否已包含完成标记([DONE] 或非 null finish_reason)。
func scanSSECompletion(data []byte) bool {
	for _, line := range bytes.Split(data, []byte("\n")) {
		trimmed := strings.TrimSpace(string(line))
		if strings.HasPrefix(trimmed, "data: ") {
			d := strings.TrimPrefix(trimmed, "data: ")
			if d == "[DONE]" {
				return true
			}
			if strings.Contains(d, "\"finish_reason\"") && !strings.Contains(d, "\"finish_reason\":null") {
				return true
			}
		}
	}
	return false
}

// errStreamIncomplete 流式响应不完整(缺 finish_reason / [DONE]),已补发终止事件修复。
var errStreamIncomplete = errors.New("stream incomplete, repaired")

// copyStreamToClient 把 SSE 流逐行透传给客户端,同时跟踪完成状态。
// sawCompletion 表示上游已确认流完整(调用方在缓冲数据中已看到 [DONE] 或
// finish_reason),此时仅透传不检查;否则进行 SSE 完整性检查,不完整时自动补发。
// 启用 StreamCompletionCheck 时跟踪 SSE 内容;关闭时仅原样透传(带空闲超时)。
func (g *Gateway) copyStreamToClient(w io.Writer, src io.Reader, closer io.Closer, idleTimeout time.Duration, sawCompletion bool) error {
	if !g.cfg.StreamCompletionCheck || sawCompletion {
		// 已确认完整或检查关闭:仅透传(带空闲超时)
		if idleTimeout > 0 {
			r := newStreamIdleReader(src, closer, idleTimeout)
			_, err := io.Copy(w, r)
			return err
		}
		_, err := io.Copy(w, src)
		return err
	}

	// 带空闲超时 + SSE 完整性跟踪
	var r io.Reader = src
	if idleTimeout > 0 {
		r = newStreamIdleReader(src, closer, idleTimeout)
	}
	br := bufio.NewReaderSize(r, 32*1024)

	sawDone := false
	sawFinish := false
	repaired := false // 是否已补发 finish_reason(避免重复)

	// 补发 finish_reason 的工具函数
	writeFinish := func() {
		w.Write([]byte("data: {\"choices\":[{\"delta\":{},\"finish_reason\":\"stop\"}]}\n\n"))
	}

	for {
		line, err := br.ReadString('\n')
		if len(line) > 0 {
			trimmed := strings.TrimRight(line, "\r\n")
			if strings.HasPrefix(trimmed, "data: ") {
				data := strings.TrimPrefix(trimmed, "data: ")
				if data == "[DONE]" {
					sawDone = true
					// [DONE] 前:如果没看到 finish_reason,先补发
					// 客户端严格要求 finish_reason,只有 [DONE] 不够
					if !sawFinish {
						writeFinish()
						repaired = true
					}
					if _, werr := w.Write([]byte(line)); werr != nil {
						return werr
					}
				} else {
					if strings.Contains(data, "\"finish_reason\"") && !strings.Contains(data, "\"finish_reason\":null") {
						sawFinish = true
					}
					if _, werr := w.Write([]byte(line)); werr != nil {
						return werr
					}
				}
			} else {
				if _, werr := w.Write([]byte(line)); werr != nil {
					return werr
				}
			}
		}
		if err != nil {
			if err == io.EOF {
				break // 正常结束:检查完整性
			}
			// 非 EOF 错误:数据可能不完整,不补发
			return err
		}
	}

	// 流结束:如果没看到 finish_reason 且没在 [DONE] 前补发过,补发终止事件
	if !sawFinish && !repaired {
		writeFinish()
		if !sawDone {
			w.Write([]byte("data: [DONE]\n\n"))
		}
		return errStreamIncomplete
	}
	return nil
}

// bodyTimeout 返回预读第一块 body 的超时:流式用空闲超时,非流式用整体超时。
func (g *Gateway) bodyTimeout(resp *http.Response) time.Duration {
	if isStreamingResponse(resp) {
		return time.Duration(g.cfg.StreamIdleTimeout) * time.Second
	}
	return time.Duration(g.cfg.UpstreamTimeout) * time.Second
}

// readFirstWithTimeout 带超时读取第一块数据;超时关闭 r 中断阻塞读并返回错误。
func readFirstWithTimeout(r io.ReadCloser, p []byte, timeout time.Duration) (int, error) {
	if timeout <= 0 {
		return r.Read(p)
	}
	type res struct {
		n   int
		err error
	}
	ch := make(chan res, 1)
	go func() {
		n, err := r.Read(p)
		ch <- res{n, err}
	}()
	select {
	case r := <-ch:
		return r.n, r.err
	case <-time.After(timeout):
		r.Close()
		<-ch
		return 0, fmt.Errorf("no body within %v", timeout)
	}
}

// copyBodyWithTimeout 从 src 拷贝到 dst,在流式响应中检测空闲超时。
// 每次成功读入数据后重置计时器;空闲超过 timeout 则关闭 closer 并返回错误。
// closer 通常为 resp.Body,用于中断阻塞中的底层 Read(src 可能是 bufio.Reader)。
func copyBodyWithTimeout(dst io.Writer, src io.Reader, closer io.Closer, timeout time.Duration) error {
	if timeout <= 0 {
		_, err := io.Copy(dst, src)
		return err
	}

	errCh := make(chan error, 1)
	timer := time.NewTimer(timeout)
	defer timer.Stop()

	go func() {
		buf := make([]byte, 32*1024)
		for {
			n, err := src.Read(buf)
			if n > 0 {
				if _, werr := dst.Write(buf[:n]); werr != nil {
					errCh <- werr
					return
				}
				timer.Reset(timeout)
			}
			if err == io.EOF {
				errCh <- nil
				return
			}
			if err != nil {
				errCh <- err
				return
			}
		}
	}()

	select {
	case err := <-errCh:
		return err
	case <-timer.C:
		if closer != nil {
			closer.Close()
		}
		<-errCh // 等待拷贝 goroutine 结束
		return fmt.Errorf("upstream stream idle timeout (%v)", timeout)
	}
}

// readAllWithTimeout 在超时限制下读取全部数据。
func readAllWithTimeout(r io.Reader, maxSize int64, timeout time.Duration) ([]byte, error) {
	if timeout <= 0 {
		return io.ReadAll(io.LimitReader(r, maxSize))
	}

	type result struct {
		data []byte
		err  error
	}
	ch := make(chan result, 1)

	go func() {
		data, err := io.ReadAll(io.LimitReader(r, maxSize))
		ch <- result{data, err}
	}()

	select {
	case r := <-ch:
		return r.data, r.err
	case <-time.After(timeout):
		if closer, ok := r.(io.Closer); ok {
			closer.Close()
		}
		<-ch
		return nil, fmt.Errorf("upstream timeout after %v", timeout)
	}
}

// streamIdleReader 包装 io.Reader,在两次 Read 之间空闲超时时返回错误。
// r 为数据源(可以是 bufio.Reader),closer 为超时时要关闭的对象(通常是
// 底层 resp.Body,用于中断阻塞中的 Read)。
type streamIdleReader struct {
	r       io.Reader
	closer  io.Closer
	timeout time.Duration
	timer   *time.Timer
}

func newStreamIdleReader(r io.Reader, closer io.Closer, timeout time.Duration) *streamIdleReader {
	return &streamIdleReader{
		r:       r,
		closer:  closer,
		timeout: timeout,
		timer:   time.NewTimer(timeout),
	}
}

func (s *streamIdleReader) Read(p []byte) (int, error) {
	s.timer.Reset(s.timeout)

	type readResult struct {
		n   int
		err error
	}
	ch := make(chan readResult, 1)

	go func() {
		n, err := s.r.Read(p)
		ch <- readResult{n, err}
	}()

	select {
	case r := <-ch:
		if !s.timer.Stop() {
			select {
			case <-s.timer.C:
			default:
			}
		}
		return r.n, r.err
	case <-s.timer.C:
		if s.closer != nil {
			s.closer.Close()
		}
		r := <-ch // 等待 goroutine 结束
		return r.n, fmt.Errorf("stream idle timeout after %v", s.timeout)
	}
}

func (s *streamIdleReader) Close() error {
	s.timer.Stop()
	if s.closer != nil {
		return s.closer.Close()
	}
	return nil
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
