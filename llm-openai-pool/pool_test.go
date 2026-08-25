package main

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func testPool(upstreams ...UpstreamConfig) *Pool {
	return NewPool(&Config{
		Upstreams: upstreams,
		Circuit:   CircuitConfig{FailThreshold: 2, CooldownSeconds: 1},
	})
}

func up(name string, weight int) UpstreamConfig {
	return UpstreamConfig{Name: name, BaseURL: "https://" + name + ".test/v1", APIKey: "k", Weight: weight, MaxConcurrency: 1}
}

// TestAcquireSingleConcurrency 验证单并发:占满后 Acquire 阻塞,释放后才放行。
func TestAcquireSingleConcurrency(t *testing.T) {
	p := testPool(up("a", 1))
	ctx := context.Background()

	u1, release1, err := p.Acquire(ctx, "")
	require.NoError(t, err)
	require.Equal(t, "a", u1.name)

	// 占满后,Acquire 必须阻塞(100ms 内不应返回)
	done := make(chan struct{})
	go func() {
		defer close(done)
		u2, release2, err := p.Acquire(ctx, "")
		if err == nil && u2 != nil {
			release2()
		}
	}()
	select {
	case <-done:
		t.Fatal("Acquire returned while upstream was busy")
	case <-time.After(200 * time.Millisecond):
	}

	release1()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Acquire did not unblock after release")
	}
}

// TestAcquireWaitsForAnyIdle 验证多个上游全忙时排队,释放一个后放行。
func TestAcquireWaitsForAnyIdle(t *testing.T) {
	p := testPool(up("a", 1), up("b", 1))
	ctx := context.Background()

	ua, ra, err := p.Acquire(ctx, "")
	require.NoError(t, err)
	ub, rb, err := p.Acquire(ctx, "")
	require.NoError(t, err)
	require.NotEqual(t, ua.name, ub.name, "两个并发请求应分到不同上游")

	done := make(chan struct{})
	go func() {
		defer close(done)
		u, release, err := p.Acquire(ctx, "")
		if err == nil && u != nil {
			release()
		}
	}()
	select {
	case <-done:
		t.Fatal("Acquire returned while both upstreams were busy")
	case <-time.After(200 * time.Millisecond):
	}

	ra()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Acquire did not unblock after one release")
	}
	rb()
}

// TestCircuitBreaker 验证熔断:连续失败达阈值后不可用,冷却到期自动恢复。
func TestCircuitBreaker(t *testing.T) {
	p := testPool(up("a", 1))
	u := p.upstreams[0]
	require.True(t, u.available(time.Now()))

	u.reportFailure(p.failThreshold, p.cooldown) // failures=1,阈值 2 未到
	require.True(t, u.available(time.Now()), "未达阈值不应熔断")

	u.reportFailure(p.failThreshold, p.cooldown) // failures=2,熔断打开
	require.False(t, u.available(time.Now()), "达到阈值后应熔断")

	// 冷却期内保持熔断
	require.False(t, u.available(time.Now().Add(p.cooldown/2)))

	// 冷却到期自动恢复
	require.True(t, u.available(time.Now().Add(p.cooldown).Add(time.Millisecond)))
	require.Equal(t, 0, u.failures, "恢复后失败计数应清零")
}

// TestReportSuccessResets 验证成功后清除熔断状态。
func TestReportSuccessResets(t *testing.T) {
	p := testPool(up("a", 1))
	u := p.upstreams[0]
	u.reportFailure(p.failThreshold, p.cooldown)
	u.reportFailure(p.failThreshold, p.cooldown)
	require.False(t, u.available(time.Now()))
	u.reportSuccess()
	require.True(t, u.available(time.Now()))
	require.Equal(t, 0, u.failures)
}

// TestAllBlacklisted 验证黑名单覆盖所有可用上游时判定为无重试目标。
func TestAllBlacklisted(t *testing.T) {
	p := testPool(up("a", 1), up("b", 1))
	blacklist := map[*Upstream]bool{}
	require.False(t, p.AllBlacklisted("", blacklist))

	blacklist[p.upstreams[0]] = true
	require.False(t, p.AllBlacklisted("", blacklist), "还有一个上游可用")

	blacklist[p.upstreams[1]] = true
	require.True(t, p.AllBlacklisted("", blacklist))

	// 熔断中的上游不算可用:即使不在黑名单,全熔断也判定无目标
	p2 := testPool(up("c", 1))
	u := p2.upstreams[0]
	u.reportFailure(p2.failThreshold, p2.cooldown)
	u.reportFailure(p2.failThreshold, p2.cooldown)
	require.True(t, p2.AllBlacklisted("", map[*Upstream]bool{}))
}

// TestWeightedShuffle 验证加权随机的权重比例分布。
func TestWeightedShuffle(t *testing.T) {
	a := &Upstream{name: "a", weight: 3}
	b := &Upstream{name: "b", weight: 1}
	// 洗牌结果应只包含这两个,且多轮统计 a 明显多于 b
	counts := map[string]int{}
	for i := 0; i < 400; i++ {
		order := weightedShuffle([]*Upstream{a, b})
		require.Len(t, order, 2)
		counts[order[0].name]++
	}
	assert.Greater(t, counts["a"], counts["b"], "权重 3:1,首位置 a 应显著多于 b")
	assert.Equal(t, 400, counts["a"]+counts["b"])
}

// TestAcquireSkipsTrippedUpstream 验证熔断中的上游不会被选中。
func TestAcquireSkipsTrippedUpstream(t *testing.T) {
	p := testPool(up("bad", 1), up("good", 1))
	bad := p.upstreams[0]
	bad.reportFailure(p.failThreshold, p.cooldown)
	bad.reportFailure(p.failThreshold, p.cooldown)
	require.False(t, bad.available(time.Now()))

	u, release, err := p.Acquire(context.Background(), "")
	require.NoError(t, err)
	require.Equal(t, "good", u.name)
	release()

	// 熔断中的 bad 占位后会被拒绝并释放:验证没有泄漏(可再次 Acquire 到 good)
	u2, release2, err := p.Acquire(context.Background(), "")
	require.NoError(t, err)
	require.Equal(t, "good", u2.name)
	release2()
}

// TestConcurrentAcquireDistributes 验证并发获取时三个请求能同时占住三个上游
// (峰值并发 = 3,互不阻塞),总数正确。
func TestConcurrentAcquireDistributes(t *testing.T) {
	p := testPool(up("a", 1), up("b", 1), up("c", 1))
	ctx := context.Background()
	var cur, peak atomic.Int32
	ready := make(chan struct{}, 3)
	releaseAll := make(chan struct{})
	var mu sync.Mutex
	got := map[string]int{}
	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			u, release, err := p.Acquire(ctx, "")
			require.NoError(t, err)
			c := cur.Add(1)
			for {
				pv := peak.Load()
				if c <= pv || peak.CompareAndSwap(pv, c) {
					break
				}
			}
			ready <- struct{}{}
			<-releaseAll
			cur.Add(-1)
			mu.Lock()
			got[u.name]++
			mu.Unlock()
			release()
		}()
	}
	for i := 0; i < 3; i++ {
		<-ready
	}
	close(releaseAll)
	wg.Wait()
	require.Equal(t, int32(3), peak.Load(), "三个并发请求应同时占住三个上游")
	require.Equal(t, 3, len(got), "三个上游都应有请求")
	total := 0
	for _, n := range got {
		total += n
	}
	require.Equal(t, 3, total)
}
