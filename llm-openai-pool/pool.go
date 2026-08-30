package main

import (
	"context"
	"log"
	"math/rand"
	"sort"
	"strings"
	"sync"
	"time"
)

// Upstream 一个上游账号:并发闸门(sem)保证单并发,熔断状态跟踪连续失败。
type Upstream struct {
	name    string
	baseURL string // 规范化:去尾斜杠、去尾部 /v1(转发时再拼回)
	apiKey  string
	weight  int
	maxConc int
	models  []string // 匹配的模型(支持 * ? 通配符),空 = 匹配所有
	sem     chan struct{}

	mu       sync.Mutex
	failures int            // 连续失败次数
	open     bool           // 熔断是否打开
	until    time.Time      // 冷却截止时间
	holders  map[string]int // 当前占用者的请求 ID → 占用数(排障用)
}

func (u *Upstream) available(now time.Time) bool {
	u.mu.Lock()
	defer u.mu.Unlock()
	if u.open {
		if now.Before(u.until) {
			return false
		}
		// 冷却到期,自动恢复
		u.open = false
		u.failures = 0
	}
	return true
}

// addHolder 记录一个请求占用了该上游。
func (u *Upstream) addHolder(reqID string) {
	u.mu.Lock()
	if u.holders == nil {
		u.holders = make(map[string]int)
	}
	u.holders[reqID]++
	u.mu.Unlock()
}

// removeHolder 记录一个请求释放了该上游。
func (u *Upstream) removeHolder(reqID string) {
	u.mu.Lock()
	if u.holders[reqID] <= 1 {
		delete(u.holders, reqID)
	} else {
		u.holders[reqID]--
	}
	u.mu.Unlock()
}

// holderIDs 返回当前占用者的请求 ID 列表(用于日志)。
func (u *Upstream) holderIDs() []string {
	u.mu.Lock()
	defer u.mu.Unlock()
	out := make([]string, 0, len(u.holders))
	for id := range u.holders {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

// reportFailure 记录一次失败;只有连续失败达到阈值才打开熔断(温和策略:
// 账号池时常报错但重试可成功,不能一错就断)。
func (u *Upstream) reportFailure(threshold int, cooldown time.Duration) {
	u.mu.Lock()
	defer u.mu.Unlock()
	u.failures++
	if u.failures >= threshold {
		u.open = true
		u.until = time.Now().Add(cooldown)
	}
}

func (u *Upstream) reportSuccess() {
	u.mu.Lock()
	defer u.mu.Unlock()
	u.failures = 0
	u.open = false
	u.until = time.Time{}
}

// Pool 管理全部上游:选择、并发闸门、熔断、排队唤醒。
type Pool struct {
	upstreams     []*Upstream
	failThreshold int
	cooldown      time.Duration
	releaseCh     chan struct{}
}

func NewPool(cfg *Config) *Pool {
	p := &Pool{
		failThreshold: cfg.Circuit.FailThreshold,
		cooldown:      time.Duration(cfg.Circuit.CooldownSeconds) * time.Second,
		releaseCh:     make(chan struct{}, 1),
	}
	for _, uc := range cfg.Upstreams {
		p.upstreams = append(p.upstreams, &Upstream{
			name:    uc.Name,
			baseURL: strings.TrimSuffix(strings.TrimSuffix(uc.BaseURL, "/"), "/v1"),
			apiKey:  uc.APIKey,
			weight:  uc.Weight,
			maxConc: uc.MaxConcurrency,
			models:  uc.Models,
			sem:     make(chan struct{}, uc.MaxConcurrency),
		})
	}
	return p
}

// Acquire 占用一个可用且匹配 model 的上游(未熔断、有空位、模型匹配)。
// 选择策略:可用上游按权重加权随机排列,依次非阻塞占位;全部忙则阻塞等待空位释放。
// 返回占用成功后的释放函数;ctx 取消时返回错误。
func (p *Pool) Acquire(ctx context.Context, model string) (*Upstream, func(), error) {
	for {
		now := time.Now()
		var candidates []*Upstream
		for _, u := range p.upstreams {
			if u.matchesModel(model) && u.available(now) {
				candidates = append(candidates, u)
			}
		}
		if len(candidates) == 0 {
			// 全部熔断中:等冷却到期(超时后重新评估)
			if !p.wait(ctx, 500*time.Millisecond) {
				return nil, nil, ctx.Err()
			}
			continue
		}
		for _, u := range weightedShuffle(candidates) {
			select {
			case u.sem <- struct{}{}:
				// 占位成功后再次确认没有在占位瞬间被熔断
				if u.available(now) {
					release := func() {
						<-u.sem
						p.notifyRelease()
					}
					return u, release, nil
				}
				<-u.sem
			default:
				// 该上游忙,试下一个
			}
		}
		// 全部忙,等空位释放
		if !p.wait(ctx, 0) {
			return nil, nil, ctx.Err()
		}
	}
}

// wait 等待空位释放或熔断变化;timeout>0 时超时也返回 true(重新评估)。
func (p *Pool) wait(ctx context.Context, timeout time.Duration) bool {
	if timeout > 0 {
		t := time.NewTimer(timeout)
		defer t.Stop()
		select {
		case <-p.releaseCh:
			return true
		case <-t.C:
			return true
		case <-ctx.Done():
			return false
		}
	}
	select {
	case <-p.releaseCh:
		return true
	case <-ctx.Done():
		return false
	}
}

func (p *Pool) notifyRelease() {
	select {
	case p.releaseCh <- struct{}{}:
	default:
	}
}

// AllBlacklisted 判断本次请求已失败排除(blacklist)的上游是否覆盖了所有
// 当前可用且匹配 model 的上游,是则没有可重试目标了。
func (p *Pool) AllBlacklisted(model string, blacklist map[*Upstream]bool) bool {
	now := time.Now()
	for _, u := range p.upstreams {
		if u.matchesModel(model) && u.available(now) && !blacklist[u] {
			return false
		}
	}
	return true
}

// weightedShuffle 按权重随机排列(每个位置独立按剩余权重抽样)。
func weightedShuffle(ups []*Upstream) []*Upstream {
	out := make([]*Upstream, 0, len(ups))
	remaining := append([]*Upstream(nil), ups...)
	for len(remaining) > 0 {
		total := 0
		for _, u := range remaining {
			total += u.weight
		}
		r := rand.Intn(total)
		idx := 0
		for i, u := range remaining {
			r -= u.weight
			if r < 0 {
				idx = i
				break
			}
		}
		out = append(out, remaining[idx])
		remaining = append(remaining[:idx], remaining[idx+1:]...)
	}
	return out
}

// Names 返回上游名列表,用于日志。
func (p *Pool) Names() []string {
	names := make([]string, 0, len(p.upstreams))
	for _, u := range p.upstreams {
		names = append(names, u.name)
	}
	return names
}

// LogState 打印当前每个上游的占用与熔断状态,便于观察。
func (p *Pool) LogState() {
	now := time.Now()
	type row struct {
		name   string
		busy   int
		cap    int
		fail   int
		status string
		ids    []string
	}
	rows := make([]row, 0, len(p.upstreams))
	for _, u := range p.upstreams {
		u.mu.Lock()
		r := row{name: u.name, busy: len(u.sem), cap: u.maxConc, fail: u.failures}
		if u.open {
			r.status = "cooling " + u.until.Sub(now).Round(time.Second).String()
		} else {
			r.status = "ok"
		}
		ids := make([]string, 0, len(u.holders))
		for id := range u.holders {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		r.ids = ids
		u.mu.Unlock()
		rows = append(rows, r)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].name < rows[j].name })
	for _, r := range rows {
		if len(r.ids) > 0 {
			log.Printf("upstream %s: busy=%d/%d [%s] failures=%d %s", r.name, r.busy, r.cap, strings.Join(r.ids, " "), r.fail, r.status)
		} else {
			log.Printf("upstream %s: busy=%d/%d failures=%d %s", r.name, r.busy, r.cap, r.fail, r.status)
		}
	}
}
