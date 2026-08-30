# openai-pool

轻量级 OpenAI API 账号池网关——**多个上游 OpenAI 兼容端点(账号)合并为一个本地出口,负载均衡 + 并发抢答 + 原地重试 + 单并发闸门 + 参数完全透传**。

## 使用场景

- 一个本地统一入口,合并所有账号
- 同一请求并发发到多个账号,先到先得(降低尾延迟)
- 报错/无思考内容 → 原地重试同一账号,重试耗尽自动换下一个
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
  "retry_delay_ms": 0,
  "circuit": {
    "cooldown_seconds": 15,
    "fail_threshold": 5
  },
  "models_cache_ttl_seconds": 60,
  "max_body_size": 67108864,
  "upstream_timeout_seconds": 120,
  "stream_idle_timeout_seconds": 60,
  "response_header_timeout_seconds": 120,
  "parallel_fetch": 1,
  "stream_completion_check": true
}


```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `listen` | `:8080` | 本地监听地址 |
| `local_keys` | `[]` | 本地出口鉴权 key,空 = 不鉴权;支持多个 |
| `retry_times` | `3` | 每个上游的最大尝试次数(含第一次,最小 1);失败原地重试,耗尽后换上游 |
| `retry_delay_ms` | `0` | 原地重试间隔毫秒,`0` = 立即 |
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
| `upstream_timeout_seconds` | `120` | 非流式请求整体超时(秒),`0` = 不限制 |
| `stream_idle_timeout_seconds` | `60` | 流式响应两次数据间的空闲超时(秒),`0` = 不限制 |
| `response_header_timeout_seconds` | `120` | 等待上游响应头超时(秒),`0` = 不限制 |
| `parallel_fetch` | `1` | 并发抢答:同一请求同时发到多个上游,先到先得;`1` = 关闭(顺序) |
| `stream_completion_check` | `true` | 检查流式响应完整性(缺 `finish_reason`/`[DONE]` 时自动补发终止事件并熔断该上游) |

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
                                              → 并发抢答(parallel_fetch):同时请求多个,先到先得
                                              → 替换 Authorization
                                              → 原样透传请求体与路径
                                              → 流式响应原路返回
                                              → 失败/无思考 → 原地重试同一上游(最多 retry_times 次)
                                              → 熔断:温和冷却后自动恢复
```

## 设计要点

### 单并发闸门
每个上游的 `max_concurrency`(默认 1)限制同时请求数。流式请求从开始到结束占用该上游,其他请求会排队或分配到空闲上游。

### 负载均衡
可用上游中按权重加权随机排列,依次尝试非阻塞占位;全部忙则阻塞等待。

### 重试策略(原地重试)
**每个上游独立重试 `retry_times` 次(含第一次,最小 1)**,`retry_delay_ms` 可配间隔:

- 网络错误、**所有 4xx**(401/402/403/400/422/429)、5xx → 原地重试同一上游
- 2xx 但无 body(幽灵请求)→ 原地重试
- 2xx 但无思考内容(思考请求时)→ 原地重试
- 重试耗尽 → 放弃该上游,换下一个(或等并发中其他上游的结果)
- 全部上游失败:4xx/5xx 透传最后一次错误;2xx 校验失败返回 502;无可用上游返回 503

### 并发抢答(Parallel Fetch)
当 `parallel_fetch > 1` 时,一个请求同时发送到多个上游,每个上游独立原地重试。第一个返回合格 2xx 的胜出、透传,其余在途请求(含重试中)立即取消。适用于:

- 多个上游响应速度差异大时,降低尾延迟
- 部分上游可能熔断/超时,通过并发减少等待时间

思考校验(`reasoning_effort` / `thinking` / `reasoning`)在并发模式下也正常工作:校验不合格的响应触发该上游原地重试,合格才胜出。

注意:并发抢答会消耗更多上游的并发槽位,适用场景是上游账号较多且希望降低延迟。`parallel_fetch` 设为 `1` 即关闭,退化为顺序原地重试。

### 思考内容校验
请求带思考字段(`reasoning_effort` / `thinking` / `reasoning`)时,校验上游响应确实返回了思考内容(`reasoning_content` / `thinking_content`):

- 流式:检查前 8 个 SSE 事件,出现思考内容即放行(缓冲内容+剩余流原样透传);没有则原地重试
- 非流式:读完整响应检查

检测期间不向客户端写入任何字节,重试/换上游是安全的。所有上游重试耗尽都不返回思考内容时,返回 502 错误(不兜底透传无思考响应)。

### SSE 流完整性检查
透传流式响应时跟踪是否收到 `finish_reason` 或 `[DONE]`:

- 流完整 → 正常透传
- 流不完整(连接在 `finish_reason` 前断开)→ **自动补发终止事件修复流**(客户端不会报 "Stream ended without finish_reason"),并熔断该上游
- 可用 `stream_completion_check: false` 关闭(仅原样透传)

### 熔断
连续失败达到阈值(`fail_threshold`,默认 5)后短暂冷却(默认 15 秒),到期自动恢复正常。设计为"温和"策略,因为账号池时常报错但重试可成功。

### 鉴权
`local_keys` 配置的本地 key 列表,请求必须携带 `Authorization: Bearer <key>`。支持多 key,未配置时放行。

### /v1/models
并发请求所有未熔断上游的 `/v1/models`,合并 id 去重排序,缓存 TTL 内复用。

## 日志与排障

每个请求有唯一 ID(`req-xxxxxxxx`),日志按 ID 关联同一请求的完整生命周期:

```
[req-62a7686d] 并行抢答 → fast slow (每个上游最多试 3 次)
[req-62a7686d] ✗ slow -> 500, 原地重试 (尝试1/3)
[req-62a7686d] ✓ fast -> 200 /v1/chat/completions, 已中断: slow (第1轮)
[req-62a7686d] 完成: fast 胜出, 用时 1ms
```

每 30 秒打印一次上游状态,显示当前占用者请求 ID(`[req-xxx]`),便于排查 busy 归属:

```
upstream example1: busy=1/1 [req-dde34635] failures=0 ok
```

- `busy=1/1` = 该上游被占用;`[req-xxx]` = 占用它的请求 ID(多个用空格分隔)
- 空闲时无 `[xxx]` 部分
- 若请求完成后某上游仍长期 `busy=1/1 [req-xxx]` 且该请求早已结束,说明有占用未释放(可重启排查)

## 测试

```bash
# 单元测试 + 集成测试(假上游模拟)
go test ./... -count=1 -timeout=60s
```