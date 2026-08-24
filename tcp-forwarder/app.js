#!/usr/bin/env node
'use strict';

var path = require('path');
var forwarder = require('./lib/forwarder');
var proxy = require('./lib/proxy');
var gateway = require('./lib/gateway');
var webServer = require('./lib/web-server');

/*
 * 入口装配：CLI 解析 -> 规则/代理初始化 -> Web 面板 -> 退出清理。
 * 业务实现均在 lib/ 各模块，本文件不包含业务逻辑。
 */

var cliPort = null;
for (var i = 2; i < process.argv.length; i++) {
  var a = process.argv[i];
  if (a.indexOf('--port=') === 0) cliPort = parseInt(a.substring(7), 10);
  else if (a === '--port' && i + 1 < process.argv.length) cliPort = parseInt(process.argv[++i], 10);
}
var WEB_PORT = cliPort || parseInt(process.env.WEB_PORT, 10) || 8080;
var PUBLIC_DIR = path.join(__dirname, 'public');

/* 启动装配：规则 -> 代理（配置注入 web 端口） */
var rules = forwarder.loadRules();
forwarder.syncServers(rules);

proxy.setWebPort(WEB_PORT);
proxy.load();
if (proxy.getState().enabled) {
  proxy.start(function (perr) {
    if (perr) console.error('[PROXY] Start failed: %s', perr);
  });
}

var server = webServer.createServer({ publicDir: PUBLIC_DIR });

/* 监听失败处理：端口被占用时给出明确提示并退出（无监听器会直接抛未捕获异常） */
server.on('error', function (err) {
  console.error('[WEB] Error: %s', err.message);
  if (err.code === 'EADDRINUSE') {
    console.error('[WEB] 端口 %s 已被占用，请通过 --port=<端口> 更换后重试', WEB_PORT);
    process.exit(1);
  }
});

server.listen(WEB_PORT, '0.0.0.0', function () {
  var gw = gateway.getGateway();
  console.log('===========================================');
  console.log('  TCP Port Forwarder');
  console.log('  Web Panel: http://0.0.0.0:' + WEB_PORT);
  console.log('  USB Gateway: ' + (gw || 'N/A'));
  console.log('  Active rules: ' + rules.filter(function (r) { return r.enabled; }).length + '/' + rules.length);
  console.log('===========================================');
});

process.on('SIGINT', function () {
  console.log('\nShutting down...');
  forwarder.stopAll();
  proxy.stop();
  server.close();
  process.exit(0);
});
