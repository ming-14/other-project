'use strict';

var fs = require('fs');
var path = require('path');
var proxyServerLib = require('./proxy-server');
var ports = require('./ports');
var forwarder = require('./forwarder');

/*
 * 流量代理（HTTP+SOCKS5 混合）管理：配置持久化、启动/停止、状态查询。
 *
 * 启动是异步的（listen），EADDRINUSE 等失败通过 start(cb) 回调通知，
 * 避免"接口已返回成功但实际未监听"的竞态（见 proxy-server.start 的 onReady）。
 *
 * 端口冲突检查需要 web 面板端口（装配期确定），通过 setWebPort 注入；
 * 转发规则占用端口查询依赖 forwarder.occupiedPorts。
 */

var PROXY_CONFIG_FILE = path.join(__dirname, '..', 'proxy.json');
var DEFAULT_PORT = 8088;

var proxyConfig = { enabled: false, port: DEFAULT_PORT };
var proxyServer = null;
var webPort = 8080;

function load() {
  try {
    var data = fs.readFileSync(PROXY_CONFIG_FILE, 'utf8');
    var cfg = JSON.parse(data);
    proxyConfig = {
      enabled: !!cfg.enabled,
      port: ports.validPort(cfg.port) || DEFAULT_PORT
    };
  } catch (e) {
    proxyConfig = { enabled: false, port: DEFAULT_PORT };
  }
}

function save() {
  fs.writeFileSync(PROXY_CONFIG_FILE, JSON.stringify(proxyConfig, null, 2), 'utf8');
}

function setWebPort(p) {
  webPort = p;
}

function getState() {
  return {
    enabled: proxyConfig.enabled,
    port: proxyConfig.port,
    running: !!proxyServer
  };
}

/* 代理端口不能与转发规则监听端口、Web 面板端口冲突 */
function portConflict(port) {
  if (port === webPort) return '端口与 Web 面板端口冲突';
  var occupied = forwarder.occupiedPorts();
  for (var i = 0; i < occupied.length; i++) {
    if (occupied[i] === port) return '端口已被转发规则占用';
  }
  return null;
}

/* 启动代理，监听结果通过 onReady(errMessage|null) 回调通知 */
function start(onReady) {
  if (proxyServer) { if (onReady) onReady(null); return; }
  var conflict = portConflict(proxyConfig.port);
  if (conflict) { if (onReady) onReady(conflict); return; }
  proxyServer = proxyServerLib.start({ listenPort: proxyConfig.port }, function (err) {
    if (err) proxyServer = null;
    if (onReady) onReady(err ? err.message : null);
  });
  proxyServer.on('error', function () {
    proxyServer = null;
  });
}

function stop() {
  if (proxyServer) {
    proxyServer.close();
    proxyServer = null;
  }
}

/* 更新配置并启停：cb(errMessage|null)。停止时不回调错误。 */
function update(config, cb) {
  var newPort = ports.validPort(config.port);
  if (newPort === null) { cb('代理端口需为 1-65535'); return; }
  proxyConfig = { enabled: !!config.enabled, port: newPort };
  save();
  stop();
  if (!proxyConfig.enabled) { cb(null); return; }
  start(function (perr) { cb(perr); });
}

module.exports = {
  setWebPort: setWebPort,
  load: load,
  getState: getState,
  start: start,
  stop: stop,
  update: update
};
