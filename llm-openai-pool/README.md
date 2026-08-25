# openai-pool

轻量级 OpenAI API 账号池网关——**多个上游 OpenAI 兼容端点(账号)合并为一个本地出口,负载均衡 + 故障自动切换 + 单并发闸门 + 参数完全透传**。

## 使用场景

- 一个本地统一入口,合并所有账号
- 请求自动分散到不同账号(负载均衡)
- 报错自动换下一个账号重试
- 短时冷却后自动恢复(不手动启用)
- 所有参数(model、reasoning_effort、stream 等)原样透传

## 快速开始

### 1. 编译

```bash
cd openai-pool
go build -o openai-pool.exe .
```

### 2. 配置文件

修改 `config.json`:

```json
{
  "local_keys": [],
  "upstreams": [
    {
      "max_concurrency": 1,
      "api_key": "sk-apikey1",
      "base_url": "https://example.com/v1",
      "name": "example1",
      "weight": 1,
      "models": ["*"]
    },
    {
      "max_concurrency": 1,
      "api_key": "sk-apikey2",
      "base_url": "https://example.com/v1",
      "name": "example2",
      "weight": 1,
      "models": ["*"]
    },
    {
      "max_concurrency": 1,
      "api_key": "sk-apikey3",
      "base_url": "https://example.com/v1",
      "name": "example3",
      "weight": 1,
      "models": ["*"]
    }
  ],
  "listen": "127.0.0.1:18080",
  "retry_times": 3,
  "circuit": {
    "cooldown_seconds": 15,
    "fail_threshold": 5
  },
  "models_cache_ttl_seconds": 60,
  "max_body_size": 67108864
}


```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `listen` | `:8080` | 本地监听地址 |
| `local_keys` | `[]` | 本地出口鉴权 key,空 = 不鉴权;支持多个 |
| `retry_times` | `3` | 失败后最多换多少个上游重试 |
| `max_body_size` | `64MB` | 请求体缓存上限(字节) |
| `upstreams[].name` | 必填 | 上游名称,唯一 |
| `upstreams[].base_url` | 必填 | 上游地址 |
| `upstreams[].api_key` | 必填 | 上游 API Key |
| `upstreams[].weight` | `1` | 负载均衡权重 |
| `upstreams[].max_concurrency` | `1` | 该上游同时允许的请求数(单并发=1) |
| `upstreams[].models` | `[]` | 该上游负责的模型,支持 `*`/`?` 通配符;空 = 匹配所有 |
| `circuit.fail_threshold` | `5` | 连续失败多少次后熔断(冷却),温和策略 |
| `circuit.cooldown_seconds` | `15` | 熔断冷却秒数,到期自动恢复 |
| `models_cache_ttl_seconds` | `60` | /v1/models 合并结果缓存秒数 |

### 3. 启动

```bash
./openai-pool -config config.json
```

### 4. 测试

```bash
# 健康检查
curl http://127.0.0.1:8080/healthz

# 模型列表(合并所有上游)
curl http://127.0.0.1:8080/v1/models

# 聊天请求(非流式)
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":32}'

# 聊天请求(流式 + reasoning_effort 思考等级)
curl -N -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"2+2=?"}],"max_tokens":64,"stream":true,"reasoning_effort":"high"}'
```

## 架构

```
客户端 → localhost:8080/v1/* → openai-pool → 选上游(加权随机+空闲优先)
                                              → 替换 Authorization
                                              → 原样透传请求体与路径
                                              → 流式响应原路返回
                                              → 失败自动换上游重试
                                              → 熔断:温和冷却后自动恢复
```

## 设计要点

### 单并发闸门
每个上游的 `max_concurrency`(默认 1)限制同时请求数。流式请求从开始到结束占用该上游,其他请求会排队或分配到空闲上游。

### 负载均衡
可用上游中按权重加权随机排列,依次尝试非阻塞占位;全部忙则阻塞等待。

### 重试策略
- 5xx、429、网络错误 → 换上游重试
- 4xx(除 429)不重试(用户错误,重试无意义),原样透传

### 思考内容校验
请求带思考字段(`reasoning_effort` / `thinking` / `reasoning`)时,校验上游响应确实返回了思考内容(`reasoning_content` / `thinking_content`):

- 流式:检查前 8 个 SSE 事件,出现思考内容即放行(缓冲内容+剩余流原样透传);没有则断连切换
- 非流式:读完整响应检查

检测期间不向客户端写入任何字节,切换是安全的。这能自动把"不支持思考/忽略思考参数"的上游踢出本轮请求,换到真正返回思考内容的上游。

### 熔断
连续失败达到阈值(`fail_threshold`,默认 5)后短暂冷却(默认 15 秒),到期自动恢复正常。设计为"温和"策略,因为账号池时常报错但重试可成功。

### 鉴权
`local_keys` 配置的本地 key 列表,请求必须携带 `Authorization: Bearer <key>`。支持多 key,未配置时放行。

### /v1/models
并发请求所有未熔断上游的 `/v1/models`,合并 id 去重排序,缓存 TTL 内复用。

## 测试

```bash
# 单元测试 + 集成测试(假上游模拟)
go test ./... -count=1 -timeout=60s
```