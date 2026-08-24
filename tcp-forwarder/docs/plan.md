# 架构重构实施计划（A1-A3 + A4）

> 依据 `analysis.md`。目标：行为不变、冒烟测试 62 项全绿、不留兼容接口。

## 实施顺序（每阶段独立可验证）

### 阶段 1：lib/bridge.js（A3）

1. 新建 `lib/bridge.js`：导出 `bridge(a, b, pendingBuf)`（pipe 双向 + error noop + close 互毁 + pendingBuf 预写）。
2. `lib/proxy-server.js`：删除内部 `bridge` 函数与 `noop`（若仅剩 bridge 使用则一并删），改 `require('./bridge')`；两处调用 `bridge(socket, ct)` / `bridge(socket, t, rest)` 签名不变。
3. `lib/ftp-proxy.js` `createDataServer`：连接回调改 `bridge(dataClient, dataTarget)`；保留连接前 `error noop`。
4. `app.js` `startForward`：连接回调改 `bridge(clientSocket, target)`；保留连接期 timeout/error cleanup。
5. 验证：`node --check` + 冒烟测试。

### 阶段 2：lib/gateway.js + lib/ports.js（A4 + 基础）

1. 新建 `lib/gateway.js`：`getGateway()`，内部 `detectGateway()`（原逻辑）+ TTL 5s 缓存（含 null）。
2. 新建 `lib/ports.js`：`validPort()` 原样迁移。
3. 验证：`node --check`；`app.js` 暂不引用（阶段 3 起替换）。

### 阶段 3：lib/forwarder.js（A1 核心）

1. 新建 `lib/forwarder.js`，从 app.js 迁移：
   - 状态：`servers`、`CONNECT_TIMEOUT`、`CONFIG_FILE`（→ `__dirname/../rules.json`）
   - 函数：`loadRules` / `saveRules` / `resolveHost`（用 gateway.getGateway）/ `startForward`（用 bridge、ftpProxy）/ `stopForward` / `ruleChanged` / `syncServers`
   - 新增：`occupiedPorts()`（返回监听端口数组）、`stopAll()`（遍历 stopForward）
2. 验证：`node --check`；app.js 暂不引用（阶段 5 装配时切换）。

### 阶段 4：lib/proxy.js（A1）

1. 新建 `lib/proxy.js`，从 app.js 迁移：
   - 状态：`proxyConfig`、`proxyServer`、`PROXY_CONFIG_FILE`、webPort（默认 8080）
   - 函数：`load` / `save` / `setWebPort` / `getState` / `start(cb)`（含冲突检查，用 forwarder.occupiedPorts）/ `stop` / `update(config, cb)`（保存+启停，端口校验用 ports.validPort）
2. 验证：`node --check`。

### 阶段 5：lib/web-server.js + app.js 瘦身（A1）

1. 新建 `lib/web-server.js`：
   - 迁移 MIME_TYPES、staticCache、loadStatic
   - `createServer({ publicDir })`：静态服务 + 全部 API 路由（GET/POST /api/rules、/api/gateway、/api/proxy、/api CRUD）
   - 路由引用 forwarder / proxy / gateway / ports 模块函数，不再直接读模块级变量
2. `app.js` 瘦身为入口：
   - CLI 解析 → forwarder.loadRules + syncServers → proxy.setWebPort + load + 条件 start → webServer.createServer + error 监听 + listen + banner → SIGINT（forwarder.stopAll + proxy.stop + server.close）
3. 验证：`node --check` + 冒烟测试全绿。

### 阶段 6：proxy-server.js DNS 缓存 LRU（A2）

1. `dnsCache` 改 `Map`（host → { expires, ips, pending }）。
2. 命中未过期：delete+set 刷新 LRU，返回缓存。
3. 插入新条目：`size > 1024` 时删除迭代序第一条（最旧）。
4. 过期/失败 30s 短缓存、pending 并发合并语义保持不变。
5. 验证：`node --check` + 冒烟测试全绿。

## 检查清单（迁移引用点核对）

- [ ] `servers` 引用：startForward / stopForward / syncServers / proxyPortConflict（→ forwarder.occupiedPorts）
- [ ] `proxyConfig` 引用：loadProxyConfig / saveProxyConfig / GET+POST /api/proxy（→ proxy.getState / proxy.update）
- [ ] `rules` 引用：启动装配 / GET /api/rules / POST /api CRUD / banner（→ forwarder.loadRules 或入口局部变量）
- [ ] `validPort` 引用：POST /api CRUD、POST /api/proxy（→ ports.validPort）
- [ ] `getGateway` 引用：resolveHost、GET /api/gateway、banner（→ gateway.getGateway）
- [ ] bridge 调用点：proxy-server ×2、ftp-proxy ×1、forwarder ×1（无残留本地实现）
- [ ] SIGINT：servers 遍历 → forwarder.stopAll

## 验收标准

1. `node --check` 全部文件通过。
2. `test/smoke.js` 62 项全绿（`NODE=C:\UserProgram\node-v13.0.0-win-x64\node.exe`）。
3. 无残留：无未使用的 require / 无兼容导出 / 无重复桥接实现。
4. `grep` 确认 app.js 不再包含路由/静态/MIME/网关实现。
5. docs/analysis.md 与 docs/plan.md 随代码提交。
