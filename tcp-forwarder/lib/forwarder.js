'use strict';

var net = require('net');
var fs = require('fs');
var path = require('path');
var ftpProxy = require('./ftp-proxy');
var bridge = require('./bridge');
var gateway = require('./gateway');

/*
 * 转发规则管理：规则持久化、按规则 diff 启停转发服务器。
 *
 * servers: listenPort -> net.Server（TCP）或 ftp-proxy 的 ctrlServer（FTP），
 * 两者都挂 _rule（当前生效规则引用，用于 diff 与状态刷新）。
 *
 * 停止规则语义（stopForward）：强制断开存量连接后关闭监听——
 * TCP 服务器销毁 _sockets 集合中的连接，FTP 服务器在其 close 覆盖内处理。
 */

var CONFIG_FILE = path.join(__dirname, '..', 'rules.json');
/* 连接目标超时：目标不可达（静默丢包）时快速失败，避免客户端挂起数分钟 */
var CONNECT_TIMEOUT = 10000;
var servers = {};

function loadRules() {
  try {
    var data = fs.readFileSync(CONFIG_FILE, 'utf8');
    return JSON.parse(data);
  } catch (e) {
    return [];
  }
}

function saveRules(rules) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(rules, null, 2), 'utf8');
}

function resolveHost(host) {
  if (host === 'usb_gateway') {
    var gw = gateway.getGateway();
    if (gw) {
      console.log('[RESOLVE] gateway -> %s', gw);
      return gw;
    }
    console.error('[RESOLVE] gateway detection failed, using 127.0.0.1');
    return '127.0.0.1';
  }
  return host;
}

function startForward(rule) {
  var port = rule.listenPort;
  if (servers[port]) return;

  if (rule.protocol === 'ftp') {
    /* FTP 规则传入 resolveHost，每次连接时解析 usb_gateway（与 TCP 规则一致） */
    var ftpServer = ftpProxy.start({
      listenPort: rule.listenPort,
      targetHost: rule.targetHost,
      targetPort: rule.targetPort,
      resolveHost: resolveHost
    });
    ftpServer.on('error', function (err) {
      console.error('[FTP:%s] Error: %s', port, err.message);
      delete servers[port];
    });
    servers[port] = ftpServer;
    ftpServer._rule = rule;
    return;
  }

  var server = net.createServer(function (clientSocket) {
    /* 存量连接登记：停止规则时强制断开 */
    server._sockets.add(clientSocket);
    clientSocket.on('close', function () { server._sockets.delete(clientSocket); });

    var targetHost = resolveHost(rule.targetHost);
    var cleaned = false;
    function cleanup() {
      if (cleaned) return;
      cleaned = true;
      clientSocket.destroy();
      target.destroy();
    }

    var target = net.createConnection({
      port: rule.targetPort,
      host: targetHost,
      timeout: CONNECT_TIMEOUT
    });
    target.on('timeout', cleanup); /* 连接目标超时（含目标不可达） */
    target.on('connect', function () {
      target.setTimeout(0); /* 连接建立后清除握手期超时，允许隧道长期空闲 */
      bridge(clientSocket, target);
    });

    clientSocket.on('error', cleanup);
    target.on('error', cleanup);
    clientSocket.on('close', cleanup);
    target.on('close', cleanup);
  });
  server._sockets = new Set();

  server.on('error', function (err) {
    console.error('[FWD:%s] Error: %s', port, err.message);
    delete servers[port];
  });

  server.listen(port, '0.0.0.0', function () {
    console.log('[FWD:%s] Listening -> %s:%s', port, rule.targetHost, rule.targetPort);
  });

  server._rule = rule;
  servers[port] = server;
}

function stopForward(port) {
  if (servers[port]) {
    /* 强制断开存量连接：停止规则语义为立即销毁（FTP 服务器内部同样处理） */
    if (servers[port]._sockets) {
      servers[port]._sockets.forEach(function (sock) { sock.destroy(); });
    }
    servers[port].close();
    delete servers[port];
    console.log('[FWD:%s] Stopped', port);
  }
}

/* 规则变化（转发目标/协议不同）才需要重启对应端口 */
function ruleChanged(a, b) {
  return a.listenPort !== b.listenPort ||
         a.targetHost !== b.targetHost ||
         a.targetPort !== b.targetPort ||
         a.protocol !== b.protocol;
}

/* 按规则 diff 同步服务器：只启停变化的部分，避免全量重启造成端口中断 */
function syncServers(rules) {
  var wanted = {};
  for (var i = 0; i < rules.length; i++) {
    if (rules[i].enabled) wanted[rules[i].listenPort] = rules[i];
  }

  var ports = Object.keys(servers);
  for (var j = 0; j < ports.length; j++) {
    var port = parseInt(ports[j], 10);
    var want = wanted[port];
    if (!want || !servers[port]._rule || ruleChanged(servers[port]._rule, want)) {
      stopForward(port);
    } else {
      /* 规则未变化：刷新 _rule 引用，保持最新数据（如名称编辑） */
      servers[port]._rule = want;
    }
  }

  for (var k in wanted) {
    var wp = parseInt(k, 10);
    if (!servers[wp]) startForward(wanted[k]);
  }
}

/* 当前监听的转发端口列表（供代理端口冲突检查） */
function occupiedPorts() {
  return Object.keys(servers).map(function (p) { return parseInt(p, 10); });
}

/* 停止全部转发（退出时调用） */
function stopAll() {
  Object.keys(servers).forEach(function (port) {
    stopForward(parseInt(port, 10));
  });
}

module.exports = {
  loadRules: loadRules,
  saveRules: saveRules,
  syncServers: syncServers,
  stopAll: stopAll,
  occupiedPorts: occupiedPorts
};
