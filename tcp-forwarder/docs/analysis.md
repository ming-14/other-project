# 架构问题分析（A1-A3 及调研新发现）

> 对应 2026 首轮代码审查的"未修复项"。本文档只做分析与决策，实施见 `plan.md`。

## 范围

| 编号 | 问题 | 来源 |
|---|---|---|
| A1 | `app.js` 单体膨胀（498→550 行），五类职责混在一个文件 | 首轮审查 A1 |
| A2 | `proxy-server.js` DNS 缓存无淘汰，长期运行内存只增不减 | 首轮审查 A2 |
| A3 | 双向桥接逻辑在三个文件各写一遍 | 首轮审查 A3 |
| A4 | 网关检测每次调用都同步执行 `execSync`，阻塞事件循环 | 本次调研新发现 |

约束（来自 AGENTS.md）：兼容 Node 13.0.0；ES5 风格 + Node 10 时代 API（项目现状，保持统一）；**不留兼容接口**，重构后更新全部引用点；行为保持不变（冒烟测试为验收基准）；不做无用的防御编程与过度工程。

---

## A1. app.js 单体

### 现状职责清单（550 行）

1. CLI 参数解析（`--port`）与端口选择
2. 网关探测 `getGateway`（execSync + /proc/net/route）
3. 规则持久化 `loadRules` / `saveRules`
4. 端口校验 `validPort`
5. 代理配置：`loadProxyConfig` / `saveProxyConfig` / `proxyPortConflict` / `startProxy` / `stopProxy`
6. 转发管理：`resolveHost` / `startForward` / `stopForward` / `ruleChanged` / `syncServers` / `servers` 状态
7. HTTP 服务：静态文件（MIME 表 + mtime 缓存）+ 全部 API 路由
8. 启动装配（启动横幅、SIGINT）

### 问题影响

- **改动放大**：任何一处修改（哪怕改个错误文案）都要读 550 行；API 路由与转发状态、代理状态互相穿插，认知负担高。
- **状态耦合**：`proxyPortConflict` 直接遍历 `servers`（转发内部状态）；`GET /api/proxy` 直接读 `proxyServer`（代理内部状态）；路由处理函数与模块级变量混在同一闭包。
- **无法独立测试**：没有模块边界，单元级验证只能走黑盒 HTTP。
- **职责混杂违反单一职责**：网关探测（系统命令）与 HTTP 路由（网络协议）与规则同步（业务）在同一个文件。

### 拆分方案

按职责边界拆为 6 个模块 + 1 个入口，依赖单向（入口 → web-server → 各服务模块 → 基础模块）：

```
app.js（入口：CLI、装配、横幅、SIGINT）
 └─ lib/web-server.js（HTTP 服务：静态 + API 路由）
     ├─ lib/forwarder.js（转发管理：规则持久化、启停、diff 同步、端口占用查询）
     │   ├─ lib/gateway.js（网关探测 + TTL 缓存）
     │   ├─ lib/ftp-proxy.js（FTP 应用层代理，已有）
     │   └─ lib/bridge.js（双向桥接，A3 抽取）
     ├─ lib/proxy.js（代理配置 + 生命周期 + 冲突检查）
     │   ├─ lib/proxy-server.js（HTTP+SOCKS5 混合代理，已有）
     │   └─ lib/forwarder.js（occupiedPorts）
     ├─ lib/ports.js（validPort 通用端口校验）
     └─ lib/gateway.js
```

各模块职责与关键决策：

**lib/ports.js** — 仅 `validPort`。被 forwarder（规则校验）与 proxy（代理端口校验）共用，独立成模块避免跨域借用。

**lib/gateway.js** — 仅 `getGateway`。原逻辑原样搬入。
- 决策：**加 TTL 缓存（5s）**。理由：`getGateway` 内部 `execSync` 同步阻塞事件循环（最多 2s）；`/api/gateway` 每 10s 轮询 + `usb_gateway` 规则**每个新连接**都触发一次。缓存后 USB 重插换网段最多 5s 生效，可接受（A4）。

**lib/forwarder.js** — 转发管理域：`loadRules` / `saveRules`（规则持久化，与转发强相关）、`resolveHost`（依赖 gateway）、`startForward` / `stopForward` / `syncServers` / `ruleChanged`、`occupiedPorts`（供 proxy 冲突检查）、`stopAll`（供 SIGINT）。
- 决策：规则持久化并入 forwarder 而非独立 rules-store 模块——规则数组的唯一消费者是"转发启停同步"与"API CRUD"，CRUD 改完立即 `saveRules` + `syncServers`，同域内闭环，避免模块碎片化。

**lib/proxy.js** — 代理管理域：配置读写（proxy.json）、`setWebPort`（注入 web 端口做冲突检查）、`getState`（enabled/port/running，供 API）、`start(cb)` / `stop()` / `update(config, cb)`。
- 决策：web 端口通过 `setWebPort` 注入而非 require 循环——web-server 依赖 proxy，proxy 不能反向依赖 web-server；`webPort` 是装配期才确定的值（CLI 参数），注入比环境变量传递更明确。

**lib/web-server.js** — `createServer({ publicDir })` 返回 `http.Server`。静态服务（MIME 表、mtime 缓存、路径防护）+ 全部 API 路由原样迁移；规则 CRUD 与代理 API 通过 forwarder / proxy 模块函数操作。
- 决策：web 端口仅用于监听与 banner，API 不再直接引用端口常量（冲突检查已下沉到 proxy）。

**app.js** — 入口装配：CLI 解析 → `forwarder.loadRules()` + `syncServers` → `proxy.setWebPort` + `load` + 条件启动 → `webServer.createServer` + error 监听 + listen + banner → SIGINT（`forwarder.stopAll` + `proxy.stop` + `server.close`）。

### 方案对比

| 方案 | 说明 | 结论 |
|---|---|---|
| A. 按域拆 6 模块 + 入口（上述） | 职责清晰、依赖单向、每模块 100-200 行 | **采纳** |
| B. 只拆 gateway + forwarder，路由留在 app.js | 改动最小，但 app.js 仍有 300+ 行混合路由与静态服务 | 拒绝：未解决认知负担 |
| C. 引入类/框架（express 等） | 第三方依赖与 Node 13 兼容风险，本地小面板无必要 | 拒绝：过度工程 |

---

## A2. proxy-server.js DNS 缓存无淘汰

### 现状

```js
var dnsCache = Object.create(null);   // host -> { expires, ips, pending }
```

- 命中过期条目时会被新对象**覆盖**（同 key），但**从未删除**任何 key。
- 代理长开 + 流量大时，域名数量无上限增长（浏览场景可轻松累积数万条），每条含数组，内存只增不减。

### 方案对比

| 方案 | 说明 | 结论 |
|---|---|---|
| A. 定期 `setInterval` 扫过期项 | 实现简单，但需起 timer（unref），且扫描是 O(n) | 可行但多一个常驻 timer |
| B. **Map + 容量上限 + 惰性 LRU** | 命中时 delete+set 刷新位置；插入超限时淘汰最旧一条（O(1)）；无 timer | **采纳**：无额外开销、无 timer、边界清晰 |
| C. 只在插入时清理过期项 | 无 LRU 语义，热点域名可能被过期域名挤出 | 拒绝 |

决策：`dnsCache` 改为 `Map`（Node 13 原生支持），上限 **1024 条**（实际并发域名远小于此；超限淘汰最久未命中的条目，FIFO 近似 LRU，对 DNS 缓存足够）。过期条目的覆盖/并发挂起（pending）语义保持不变。

---

## A3. 桥接代码重复三处

### 现状

| 位置 | 代码 | 差异 |
|---|---|---|
| `proxy-server.js` `bridge()`（36-45 行） | pipe 双向 + error noop + close 互毁 + **pendingBuf 先写** | 有 pendingBuf |
| `ftp-proxy.js` `createDataServer`（88-97 行） | pipe 双向 + error noop + close 互毁 | 无 pendingBuf |
| `app.js` `startForward`（180-204 行） | pipe 双向 + cleanup 双毁 + **连接期超时** | 有连接期超时 |

三处的"桥接语义"完全一致：双向 pipe、错误吞掉、任一方关闭即销毁对方。差异只在调用点各自的**连接期处理**（pendingBuf 预写、握手超时），不属于桥接本身。

### 方案

抽取 `lib/bridge.js`，导出唯一函数：

```js
module.exports = function bridge(a, b, pendingBuf) {
  if (pendingBuf && pendingBuf.length) b.write(pendingBuf);
  a.pipe(b);
  b.pipe(a);
  a.on('error', noop);
  b.on('error', noop);
  a.on('close', function () { b.destroy(); });
  b.on('close', function () { a.destroy(); });
};
```

三处调用点：
1. `proxy-server.js`：删除内部 `bridge` 函数，`require('./bridge')`，调用处不变（已有 pendingBuf 参数）。
2. `ftp-proxy.js` `createDataServer`：连接回调里 `bridge(dataClient, dataTarget)`；连接前的 `error noop` 保留（连接失败避免未捕获异常）。
3. `forwarder.js`（原 app.js `startForward`）：连接回调里 `bridge(clientSocket, target)`；连接期 `timeout/error` 的 cleanup 逻辑保留（桥接只负责连接建立后）。

决策：不留 `proxy-server.bridge` 兼容导出（AGENTS.md：更新引用点）。`bridge` 挂的监听器与调用点已有的 close/error 监听并存——destroy 幂等，行为不变，无需在桥接前摘除调用点监听器。

---

## A4. 网关检测阻塞（本次调研新发现）

### 现状与影响

`getGateway()` 每次调用都执行 `execSync('ip route show default ...')`（**同步**，最长 2s 超时）。触发路径：
- `GET /api/gateway`：前端每 10s 轮询一次 → 每次阻塞事件循环。
- `resolveHost('usb_gateway')`：**每个新连接**都调用（TCP 转发 162 行、FTP 每次连接）。

在 Termux 上 `ip` 命令一般毫秒级返回，但 `execSync` 仍会冻结所有并发 socket 的处理；若命令异常（如网络命令缺失、shell 卡顿）则直接冻 2s。代理/转发是并发 IO 程序，事件循环被同步系统命令阻塞是明确的架构缺陷。

### 方案

`lib/gateway.js` 内加 TTL 缓存（5s，覆盖于 A1 拆分中一并实施）：检测结果（含 null）缓存 5s，到期才重新检测。USB 网关变化（重插/换网段）最多 5s 后生效，与前端轮询周期（10s）匹配，用户无感知。

---

## 风险与验收

- **行为不变性**：纯结构迁移，不改变任何协议/API 语义。验收基准：`test/smoke.js` 62 项全绿（黑盒测试，覆盖静态/API/转发/FTP/代理/CRUD/回归全部路径）。
- **状态迁移风险**：`servers`、`proxyConfig`、`staticCache`、`dnsCache` 从模块级变量迁移到对应模块内部，引用点逐一核对（见 plan.md 检查清单）。
- 重构后无新增依赖、无新增运行时开销（除 DNS 缓存 O(1) 淘汰与网关 5s 缓存，均为收益）。
