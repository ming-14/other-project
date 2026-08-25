package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// UpstreamConfig 描述一个上游 OpenAI 兼容端点(账号池中的一个账号)。
type UpstreamConfig struct {
	Name           string   `json:"name"`
	BaseURL        string   `json:"base_url"`
	APIKey         string   `json:"api_key"`
	Weight         int      `json:"weight"`          // 负载均衡权重,默认 1
	MaxConcurrency int      `json:"max_concurrency"` // 该账号同时允许的请求数,默认 1(单并发)
	Models         []string `json:"models"`          // 该上游负责的模型(支持 * ? 通配符),空 = 匹配所有
}

// CircuitConfig 熔断配置。账号池"时常报错但重试可成功",因此熔断必须温和:
// 只有连续失败达到阈值才短暂冷却,冷却到期自动恢复。
type CircuitConfig struct {
	FailThreshold   int `json:"fail_threshold"`    // 连续失败多少次后熔断,默认 5
	CooldownSeconds int `json:"cooldown_seconds"`  // 熔断冷却秒数,默认 15
}

// Config 网关整体配置。
type Config struct {
	Listen          string           `json:"listen"`             // 本地监听地址,默认 ":8080"
	LocalKeys       []string         `json:"local_keys"`         // 本地出口鉴权 key,空列表 = 不鉴权
	RetryTimes      int              `json:"retry_times"`        // 失败后最多换多少个上游重试,默认 3
	MaxBodySize     int64            `json:"max_body_size"`      // 请求体缓存上限(字节),默认 64MB
	Upstreams       []UpstreamConfig `json:"upstreams"`
	Circuit         CircuitConfig    `json:"circuit"`
	ModelsCacheTTL  int              `json:"models_cache_ttl_seconds"` // /v1/models 合并结果缓存秒数,默认 60
}

func defaultConfig() *Config {
	return &Config{
		Listen:         ":8080",
		RetryTimes:     3,
		MaxBodySize:    64 << 20,
		Circuit:        CircuitConfig{FailThreshold: 5, CooldownSeconds: 15},
		ModelsCacheTTL: 60,
	}
}

// LoadConfig 从 JSON 文件加载配置并做默认值填充与校验。
func LoadConfig(path string) (*Config, error) {
	cfg := defaultConfig()
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}
	if err := json.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parse config %s: %w", path, err)
	}
	if err := cfg.validate(); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (c *Config) validate() error {
	if len(c.Upstreams) == 0 {
		return errors.New("config requires at least one upstream")
	}
	if c.RetryTimes < 0 {
		return errors.New("retry_times must be >= 0")
	}
	if c.MaxBodySize <= 0 {
		return errors.New("max_body_size must be > 0")
	}
	if c.Circuit.FailThreshold <= 0 {
		c.Circuit.FailThreshold = 5
	}
	if c.Circuit.CooldownSeconds < 0 {
		c.Circuit.CooldownSeconds = 15
	}
	if c.ModelsCacheTTL < 0 {
		c.ModelsCacheTTL = 60
	}
	seen := make(map[string]bool, len(c.Upstreams))
	for i := range c.Upstreams {
		up := &c.Upstreams[i]
		up.Name = strings.TrimSpace(up.Name)
		up.BaseURL = strings.TrimRight(strings.TrimSpace(up.BaseURL), "/")
		if up.Name == "" {
			return fmt.Errorf("upstreams[%d].name is required", i)
		}
		if seen[up.Name] {
			return fmt.Errorf("duplicate upstream name: %s", up.Name)
		}
		seen[up.Name] = true
		u, err := url.Parse(up.BaseURL)
		if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
			return fmt.Errorf("upstream %s: base_url must be a valid http(s) URL", up.Name)
		}
		if up.APIKey == "" {
			return fmt.Errorf("upstream %s: api_key is required", up.Name)
		}
		if up.Weight <= 0 {
			up.Weight = 1
		}
		if up.MaxConcurrency <= 0 {
			up.MaxConcurrency = 1
		}
		for j := range up.Models {
			up.Models[j] = strings.TrimSpace(up.Models[j])
			if up.Models[j] == "" {
				return fmt.Errorf("upstream %s: models[%d] must not be empty", up.Name, j)
			}
		}
	}
	return nil
}
