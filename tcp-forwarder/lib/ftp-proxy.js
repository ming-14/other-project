'use strict';

var net = require('net');
var bridge = require('./bridge');

/*
 * FTP 应用层代理
 *
 * 透传控制通道，拦截 227(PASV)/229(EPSV) 响应和 PORT/EPRT 命令，
 * 动态代理数据连接，实现完整 FTP 兼容。
 *
 * 主要流程:
 *   PASV - 截获服务端 227，替换地址为代理本地数据端口
 *   PORT - 截获客户端 PORT，替换地址为代理本地数据端口
 *   数据端口自动创建、桥接、回收
 */

module.exports = { start: startFtpForward };

/* ───── helpers ───── */

function extractPasvAddr(line) {
  var m = line.match(/\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)/);
  if (!m) return null;
  return {
    host: m[1] + '.' + m[2] + '.' + m[3] + '.' + m[4],
    port: (parseInt(m[5], 10) << 8) + parseInt(m[6], 10)
  };
}

function extractEpsvAddr(line) {
  var m = line.match(/\(([|]{3})(\d+)(\|)\)/);
  if (!m) return null;
  return { port: parseInt(m[2], 10) };
}

function extractPortAddr(line) {
  var m = line.match(/^PORT (\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\r?$/);
  if (!m) return null;
  return {
    host: m[1] + '.' + m[2] + '.' + m[3] + '.' + m[4],
    port: (parseInt(m[5], 10) << 8) + parseInt(m[6], 10)
  };
}

function extractEprtAddr(line) {
  /* EPRT 协议族: 1=IPv6, 2=IPv4，两种都解析 */
  var m = line.match(/^EPRT \|([12])\|([0-9a-fA-F:.]+)\|(\d+)\|\r?$/);
  if (!m) return null;
  return { host: m[2], port: parseInt(m[3], 10) };
}

function buildPasvResp(ip, port) {
  var o = ip.split('.');
  return '227 Entering Passive Mode (' + o.join(',') + ',' + (port >> 8) + ',' + (port & 255) + ')\r\n';
}

function buildEpsvResp(port) {
  return '229 Entering Extended Passive Mode (|||' + port + '|)\r\n';
}

function buildPortCmd(ip, port) {
  var o = ip.split('.');
  return 'PORT ' + o.join(',') + ',' + (port >> 8) + ',' + (port & 255) + '\r\n';
}

function buildEprtCmd(ip, port) {
  /* 协议族与地址匹配：含 : 视为 IPv6 */
  var family = ip.indexOf(':') !== -1 ? '1' : '2';
  return 'EPRT |' + family + '|' + ip + '|' + port + '|\r\n';
}

/* 去掉 IPv4-mapped IPv6 前缀（::ffff:a.b.c.d -> a.b.c.d），
   避免目标主机为纯 IPv4 时连接异常 */
function stripV4Mapped(addr) {
  if (!addr) return addr;
  var m = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/.exec(addr);
  return m ? m[1] : addr;
}

/* ───── data port management ───── */

/*
 * dataPorts: localPort -> { server, dataHost, dataPort, controlId }
 */
var dataPorts = {};

function createDataServer(dataHost, dataPort, controlId, cb) {
  var ds = net.createServer(function (dataClient) {
    var dataTarget = net.createConnection(dataPort, dataHost, function () {
      /* 桥接（含 close 互毁）；连接前的错误仍需静默 */
      bridge(dataClient, dataTarget);
    });
    dataClient.on('error', noop);
    dataTarget.on('error', noop);
  });

  ds.on('error', function (err) {
    console.error('[FTP-DATA:%s] Error: %s', controlId, err.message);
  });

  ds.listen(0, '0.0.0.0', function () {
    var localPort = ds.address().port;
    dataPorts[localPort] = { server: ds, dataHost: dataHost, dataPort: dataPort, controlId: controlId };
    cb(localPort);
  });
}

function cleanupDataPort(port) {
  var entry = dataPorts[port];
  if (entry) {
    try { entry.server.close(); } catch (e) {}
    delete dataPorts[port];
  }
}

function cleanupAllDataPorts(controlId) {
  for (var p in dataPorts) {
    if (dataPorts[p].controlId === controlId) {
      cleanupDataPort(parseInt(p, 10));
    }
  }
}

/* ───── control channel proxy ───── */

/*
 * ownerControlIds: 可选。FTP server 传入的归属集合，用于记录本会话的 controlId，
 * 使 server close 时只清理自己创建的数据端口，不影响其它 FTP 规则。
 */
function proxyCtrl(clientSocket, serverSocket, ownerControlIds) {
  var controlId = Date.now() + '_' + Math.random();
  if (ownerControlIds) ownerControlIds[controlId] = true;

  /* 控制通道按 latin1 逐字节处理：FTP 传统上为 8-bit 文本，
     utf8 解码会破坏非 UTF-8 字节流（写回时字节已损坏） */
  /* C2S: client command lines (may need async data port allocation) */
  var c2sBuf = '';
  var c2sBusy = false;

  function processC2S() {
    if (c2sBusy) return;
    var idx = c2sBuf.indexOf('\r\n');
    if (idx === -1) return;

    c2sBusy = true;
    var line = c2sBuf.substring(0, idx);
    c2sBuf = c2sBuf.substring(idx + 2);

    handleC2SLine(line, function (rewritten) {
      serverSocket.write(rewritten, 'latin1');
      c2sBusy = false;
      processC2S();
    });
  }

  /* S2C: server response lines */
  var s2cBuf = '';
  var s2cBusy = false;

  function processS2C() {
    if (s2cBusy) return;
    var idx = s2cBuf.indexOf('\r\n');
    if (idx === -1) return;

    s2cBusy = true;
    var line = s2cBuf.substring(0, idx);
    s2cBuf = s2cBuf.substring(idx + 2);

    /* Multi-line response: lines after 3-digit code + '-' are not intercepted */
    var isMultiLine = line.length >= 4 && line.charAt(3) === '-';
    if (isMultiLine) {
      s2cBusy = false;
      clientSocket.write(line + '\r\n', 'latin1');
      processS2C();
      return;
    }

    handleS2CLine(line, function (rewritten) {
      clientSocket.write(rewritten, 'latin1');
      s2cBusy = false;
      processS2C();
    });
  }

  /*
   * Client-to-Server: intercept PORT / EPRT
   * Rewrite client's listening addr to proxy data port so server
   * connects through the proxy.
   */
  function handleC2SLine(line, cb) {
    var portAddr = extractPortAddr(line);
    if (portAddr) {
      var proxyIp = clientSocket.localAddress;
      /* 忽略 PORT 中通告的地址：NAT 后的客户端常通告不可达内网 IP，
         改用控制连接对端地址作为数据连接目标（与 PASV 227 处理一致） */
      createDataServer(stripV4Mapped(clientSocket.remoteAddress), portAddr.port, controlId, function (localPort) {
        cb(buildPortCmd(proxyIp, localPort));
      });
      return;
    }
    var eprtAddr = extractEprtAddr(line);
    if (eprtAddr) {
      var proxyIp2 = clientSocket.localAddress;
      createDataServer(stripV4Mapped(clientSocket.remoteAddress), eprtAddr.port, controlId, function (localPort) {
        cb(buildEprtCmd(proxyIp2, localPort));
      });
      return;
    }
    cb(line + '\r\n');
  }

  /*
   * Server-to-Client: intercept 227 PASV / 229 EPSV
   * Replace real server data addr with proxy data port so client
   * connects through the proxy.
   */
  function handleS2CLine(line, cb) {
    var pasvAddr = extractPasvAddr(line);
    if (pasvAddr) {
      var proxyIp = clientSocket.localAddress;
      /* 忽略 227 响应中携带的地址：NAT 后的服务器常返回不可达内网 IP，
         改用控制连接对端地址作为数据连接目标 */
      createDataServer(stripV4Mapped(serverSocket.remoteAddress), pasvAddr.port, controlId, function (localPort) {
        cb(buildPasvResp(proxyIp, localPort));
      });
      return;
    }
    var epsvAddr = extractEpsvAddr(line);
    if (epsvAddr) {
      createDataServer(stripV4Mapped(serverSocket.remoteAddress), epsvAddr.port, controlId, function (localPort) {
        cb(buildEpsvResp(localPort));
      });
      return;
    }
    cb(line + '\r\n');
  }

  /* Wire up */
  clientSocket.on('data', function (chunk) {
    c2sBuf += chunk.toString('latin1');
    processC2S();
  });
  serverSocket.on('data', function (chunk) {
    s2cBuf += chunk.toString('latin1');
    processS2C();
  });

  /* Cleanup on close */
  function shutdown() {
    cleanupAllDataPorts(controlId);
    if (ownerControlIds) delete ownerControlIds[controlId];
    clientSocket.destroy();
    serverSocket.destroy();
  }
  clientSocket.on('close', shutdown);
  serverSocket.on('close', shutdown);
  clientSocket.on('error', function () {});
  serverSocket.on('error', function () {});
}

/* ───── main entry ───── */

/*
 * rule: { listenPort, targetHost, targetPort, resolveHost }
 * resolveHost 每次连接时调用（usb_gateway 需按连接时网络状态解析），
 * 与 TCP 转发的行为保持一致。
 *
 * 超时策略：
 *   CONNECT_TIMEOUT - 连接目标服务器（握手期）超时，防目标不可达时挂起；
 *                     连接建立后清除，不影响正常会话。
 *   IDLE_TIMEOUT    - 控制连接空闲超时，取 5 分钟（与常见 FTP 服务器一致），
 *                     只回收真正废弃的连接，不误杀正常思考停顿的会话。
 *
 * close 语义：停止规则时强制断开本规则的存量控制连接并回收其数据端口
 * （net.Server.close 默认只停止 accept，存量连接会残留到自然结束）。
 */
var CONNECT_TIMEOUT = 10000;
var IDLE_TIMEOUT = 300000;

function startFtpForward(rule) {
  var listenPort = rule.listenPort;
  var targetHost = rule.targetHost;
  var targetPort = rule.targetPort;
  var resolveHost = rule.resolveHost;

  /* 本 server 产生的数据端口归属集合，用于 close 时精确清理 */
  var myControlIds = {};
  /* 本 server 的存量连接，close 时强制断开 */
  var activeSockets = new Set();

  var ctrlServer = net.createServer(function (clientSocket) {
    activeSockets.add(clientSocket);
    clientSocket.on('close', function () { activeSockets.delete(clientSocket); });

    var serverSocket = null;
    var connected = false;

    serverSocket = net.createConnection({
      host: resolveHost(targetHost),
      port: targetPort,
      timeout: CONNECT_TIMEOUT
    }, function () {
      connected = true;
      serverSocket.setTimeout(0); /* 握手期超时已达成目的，连接建立后清除 */
      proxyCtrl(clientSocket, serverSocket, myControlIds);
    });
    activeSockets.add(serverSocket);
    serverSocket.on('close', function () { activeSockets.delete(serverSocket); });

    serverSocket.on('timeout', function () {
      /* 目标服务器在握手期内无响应 */
      clientSocket.destroy();
      serverSocket.destroy();
    });
    serverSocket.on('error', function () {
      if (!connected) clientSocket.destroy();
    });
    clientSocket.on('error', function () {
      if (serverSocket) serverSocket.destroy();
    });

    /* 控制连接空闲超时：5 分钟 */
    clientSocket.setTimeout(IDLE_TIMEOUT);
    clientSocket.on('timeout', function () {
      clientSocket.destroy();
    });
  });

  ctrlServer.on('error', function (err) {
    console.error('[FTP:%s] Error: %s', listenPort, err.message);
  });

  ctrlServer.listen(listenPort, '0.0.0.0', function () {
    console.log('[FTP:%s] Proxy -> %s:%s', listenPort, targetHost, targetPort);
  });

  /* Override close: 先强制断开存量会话（触发各自的 shutdown 回收数据端口），
     再精确清理剩余数据端口，最后关闭监听 */
  var origClose = ctrlServer.close.bind(ctrlServer);
  ctrlServer.close = function (cb) {
    activeSockets.forEach(function (s) { s.destroy(); });
    for (var id in myControlIds) cleanupAllDataPorts(id);
    origClose(cb);
  };

  return ctrlServer;
}

function noop() {}
