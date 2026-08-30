'use strict';

var net = require('net');
var dns = require('dns');
var http = require('http');
var https = require('https');
var bridge = require('./bridge');

/*
 * 混合 HTTP + SOCKS5 代理（单端口自动识别）
 *
 * 首字节 0x05 判定为 SOCKS5，其余按 HTTP 处理，一个端口两种协议通用。
 * 无认证，全流量代理（不限制目标地址），目标由请求动态指定。
 *
 * HTTP:
 *   CONNECT host:port  -> 建立 TCP 隧道（浏览器 HTTPS 代理）
 *   其余方法(绝对 URL)  -> 转发为普通 HTTP 请求（HTTP 明文代理）
 * SOCKS5 (RFC 1928):
 *   仅支持 CONNECT 命令，无认证（05 00）
 *
 * HTTP 部分手写请求头解析：解析完首个请求头后，把请求行/头改写转发
 * 给目标，剩余数据（body、后续 keep-alive 请求）与原连接双向桥接透传，
 * 不做 body 边界解析，keep-alive 复用天然正确。
 *
 * 域名解析由代理端自行完成（UDP 53，服务器经 DNS_SERVERS 配置），
 * 不依赖系统默认解析配置，解析结果带缓存兼顾可用性与性能。
 */

module.exports = { start: startProxyServer };

var BND_ADDR = Buffer.from([0x00, 0x00, 0x00, 0x00, 0x00, 0x00]); /* 0.0.0.0:0 */
var MAX_HEADER = 65536;

function noop() {}

/* ───── 通用 ───── */

/* 查找 \r\n\r\n 位置，未找到返回 -1 */
function findHeaderEnd(buf) {
  for (var i = 0; i + 3 < buf.length; i++) {
    if (buf[i] === 13 && buf[i + 1] === 10 && buf[i + 2] === 13 && buf[i + 3] === 10) return i;
  }
  return -1;
}

/* ───── 域名解析 ─────
 * 用 Node 内置 dns.Resolver 发 UDP 53 查询。服务器列表经 DNS_SERVERS 环境变量
 * 配置（默认 127.0.0.1,8.8.8.8,1.1.1.1）：优先本机解析服务，失败或超时再
 * 尝试外部公共 DNS。可用环境变量覆盖：DNS_SERVERS=8.8.8.8,1.1.1.1 node app.js
 * 缓存 TTL 取应答 TTL（夹在 60s~3600s），解析失败短缓存 30s 防重试风暴；
 * 同一域名并发查询只发一次，挂起回调在结果返回后统一唤醒。
 *
 * 缓存容量上限 DNS_CACHE_MAX：Map 迭代序即插入序，插入超限时淘汰最旧条目，
 * 防止长期运行域名无限累积导致内存膨胀。
 */
var DNS_SERVERS = (process.env.DNS_SERVERS || '127.0.0.1,8.8.8.8,1.1.1.1').split(',');
var DNS_QUERY_TIMEOUT = 3000;
var DNS_CACHE_MAX = 1024;
var dnsCache = new Map();

function isIp(host) {
  return /^\d+\.\d+\.\d+\.\d+$/.test(host) || host.indexOf(':') !== -1;
}

function resolveHost(host, cb) {
  var now = Date.now();
  var entry = dnsCache.get(host);
  if (entry && entry.expires > now) {
    dnsCache.delete(host); dnsCache.set(host, entry); /* 命中刷新 LRU 位置 */
    cb(entry.ips[0] || null);
    return;
  }
  if (entry && entry.pending) { entry.pending.push(cb); return; }

  var pending = [cb];
  var settled = false;
  entry = { expires: 0, ips: [], pending: pending };
  dnsCache.set(host, entry);
  if (dnsCache.size > DNS_CACHE_MAX) {
    /* 淘汰最旧条目（Map 迭代序即插入序） */
    dnsCache.delete(dnsCache.keys().next().value);
  }

  function finish(ip) {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    delete entry.pending;
    for (var i = 0; i < pending.length; i++) pending[i](ip);
  }

  /* UDP 53 直连 DNS_SERVERS：不经过系统解析配置，也不复用上层 HTTP(S) 通道 */
  var res = new dns.Resolver();
  try { res.setServers(DNS_SERVERS); } catch (e) { entry.expires = now + 30000; finish(null); return; }
  var timer = setTimeout(function () {
    res.cancel(); /* 取消挂起的查询，防无限等待 */
    entry.expires = now + 30000;
    finish(null);
  }, DNS_QUERY_TIMEOUT);

  res.resolve4(host, { ttl: true }, function (err, records) {
    clearTimeout(timer);
    if (err || !records || !records[0]) {
      entry.expires = now + 30000; /* 失败短缓存，防重试风暴 */
      finish(null);
      return;
    }
    var rec = records[0];
    var ttl = rec.ttl;
    if (ttl < 60) ttl = 60;
    if (ttl > 3600) ttl = 3600;
    entry.ips = [rec.address];
    entry.expires = now + ttl * 1000;
    finish(rec.address);
  });
}

/* 连接目标：IP 直连；域名走 UDP DNS 解析（不依赖系统解析配置）。
 * DNS 解析失败或返回的 IP 连不上（含 SYN 被丢导致的挂起，10s 超时兜底）时，
 * 不额外 fallback（系统 DNS 也已不可靠），直接通知调用方。onConnect(target)
 * 成功回调，onError() 最终失败回调。 */
var CONNECT_TIMEOUT = 10000;

function connectTo(port, host, onConnect, onError) {
  var done = false;
  function fail() {
    if (!done) { done = true; onError(); }
  }
  /* dial: 尝试连接 addr；失败（error/超时）时调用 next() 走下一方案 */
  function dial(addr, next) {
    var t = net.createConnection(port, addr);
    var settled = false;
    function abort() {
      if (settled) return;
      settled = true;
      clearTimeout(to);
      t.destroy();
      next();
    }
    var to = setTimeout(abort, CONNECT_TIMEOUT);
    t.on('error', abort);
    t.on('connect', function () {
      if (settled) { t.destroy(); return; }
      settled = true;
      clearTimeout(to);
      done = true;
      onConnect(t);
    });
  }
  if (isIp(host)) { dial(host, fail); return; }
  resolveHost(host, function (ip) {
    if (ip) dial(ip, function () { dial(host, fail); }); /* DNS IP 连不上 -> 系统 DNS */
    else dial(host, fail);
  });
}

/* ───── SOCKS5 (RFC 1928) ───── */

/*
 * 首块数据 chunk 已含握手首字节。流程:
 *   VER(5) NMETHODS METHODS...           -> 05 00 (no auth)
 *   VER(5) CMD(1) RSV(0) ATYP DST.ADDR DST.PORT -> 05 REP ...
 * 仅支持 CONNECT (CMD=1)，其余回 0x07 (command not supported)。
 */
function handleSocks5(socket, firstChunk) {
  var buf = firstChunk;
  var greeted = false; /* 握手是否完成，之后开始解析 CONNECT 请求 */

  function onData(chunk) {
    buf = Buffer.concat([buf, chunk]);
    pump();
  }
  socket.on('data', onData);

  function pump() {
    if (!greeted) {
      if (buf.length < 2) return;
      var nmethods = buf[1];
      if (buf.length < 2 + nmethods) return;
      /* 客户端要求什么都回 no-auth：我们不做认证 */
      buf = buf.slice(2 + nmethods);
      greeted = true;
      socket.write(Buffer.from([0x05, 0x00]));
      if (buf.length === 0) return;
    }

    /* CONNECT 请求: VER CMD RSV ATYP DST.ADDR DST.PORT */
    if (buf.length < 4) return;
    var ver = buf[0];
    var cmd = buf[1];
    var atyp = buf[3];
    if (ver !== 0x05) { socket.destroy(); return; }

    var host, addrEnd;
    if (atyp === 0x01) { /* IPv4 */
      if (buf.length < 10) return;
      host = buf[4] + '.' + buf[5] + '.' + buf[6] + '.' + buf[7];
      addrEnd = 8;
    } else if (atyp === 0x03) { /* 域名 */
      if (buf.length < 5) return;
      var dlen = buf[4];
      if (buf.length < 5 + dlen + 2) return;
      host = buf.slice(5, 5 + dlen).toString('utf8');
      addrEnd = 5 + dlen;
    } else if (atyp === 0x04) { /* IPv6 */
      if (buf.length < 22) return;
      var parts = [];
      for (var i = 0; i < 16; i += 2) {
        parts.push(('0' + buf[4 + i].toString(16)).slice(-2) + ('0' + buf[4 + i + 1].toString(16)).slice(-2));
      }
      host = parts.join(':');
      addrEnd = 20;
    } else {
      socket.destroy();
      return;
    }

    var port = (buf[addrEnd] << 8) + buf[addrEnd + 1];
    var rest = buf.slice(addrEnd + 2);
    /* 请求解析完成，后续字节直接交给隧道 */
    socket.removeListener('data', onData);

    if (cmd !== 0x01) {
      socket.write(Buffer.concat([Buffer.from([0x05, 0x07, 0x00, 0x01]), BND_ADDR]));
      socket.destroy();
      return;
    }

    connectTo(port, host, function (target) {
      if (socket.destroyed) { target.destroy(); return; } /* 等待解析期间客户端已断开 */
      socket.write(Buffer.concat([Buffer.from([0x05, 0x00, 0x00, 0x01]), BND_ADDR]));
      bridge(socket, target, rest);
    }, function () {
      socket.write(Buffer.concat([Buffer.from([0x05, 0x01, 0x00, 0x01]), BND_ADDR]));
      socket.destroy();
    });
  }

  pump();
}

/* ───── HTTP：手写请求头解析 + 桥接透传 ───── */

/*
 * 首个请求头解析完成后:
 *   CONNECT -> 连目标、回 200、剩余数据入隧道
 *   普通请求 -> 改写请求行(绝对 URL -> origin-form)与头(去 proxy 头)，
 *               发给目标后桥接透传（body 与后续 keep-alive 请求原样转发）
 */
function handleHttp(socket, firstChunk) {
  var buf = firstChunk;
  var done = false;

  function onData(chunk) {
    buf = Buffer.concat([buf, chunk]);
    pump();
  }
  socket.on('data', onData);

  function pump() {
    if (done) return;
    var idx = findHeaderEnd(buf);
    if (idx === -1) {
      if (buf.length > MAX_HEADER) socket.destroy(); /* 头过大，防内存膨胀 */
      return;
    }
    done = true;
    socket.removeListener('data', onData);

    var head = buf.slice(0, idx).toString('latin1');
    var rest = buf.slice(idx + 4);
    var lines = head.split('\r\n');
    var reqLine = lines[0];

    /* CONNECT host:port 隧道（支持 IPv6 字面量 [::1]:443） */
    var cm = /^CONNECT\s+\[([0-9a-fA-F:.]+)\]:(\d+)\s/i.exec(reqLine) ||
             /^CONNECT\s+([^:\s]+):(\d+)\s/i.exec(reqLine);
    if (cm) {
      var cport = parseInt(cm[2], 10);
      if (!(cport >= 1 && cport <= 65535)) { socket.destroy(); return; }
      connectTo(cport, cm[1], function (ct) {
        if (socket.destroyed) { ct.destroy(); return; }
        socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
        if (rest.length) ct.write(rest); /* CONNECT 后随附的数据(如 TLS ClientHello) */
        bridge(socket, ct);
      }, function () { socket.destroy(); });
      return;
    }

    /* 普通请求：解析方法 + URL */
    var um = /^([A-Z]+)\s+(\S+)\s+HTTP\/(\d\.\d)$/i.exec(reqLine);
    if (!um) { socket.destroy(); return; }
    var url;
    try { url = new URL(um[2]); } catch (e) {
      /* 相对路径：用 Host 头补全（非标准代理客户端） */
      var hostH = /^Host:\s*(\S+)/im.exec(head);
      if (!hostH) { socket.destroy(); return; }
      try { url = new URL('http://' + hostH[1] + um[2]); } catch (e2) { socket.destroy(); return; }
    }
    var port = url.port ? parseInt(url.port, 10) : (url.protocol === 'https:' ? 443 : 80);
    if (!(port >= 1 && port <= 65535)) { socket.destroy(); return; }

    /* 改写请求行与头：绝对 URL 必须转 origin-form，剥掉代理专用头 */
    var outLines = [um[1] + ' ' + url.pathname + url.search + ' HTTP/' + um[3]];
    for (var i = 1; i < lines.length; i++) {
      var lk = lines[i].split(':')[0].toLowerCase();
      if (lk === 'proxy-connection' || lk === 'proxy-authorization') continue;
      outLines.push(lines[i]);
    }

    connectTo(port, url.hostname, function (t) {
      if (socket.destroyed) { t.destroy(); return; }
      t.write(outLines.join('\r\n') + '\r\n\r\n');
      if (rest.length) t.write(rest); /* 首个请求的 body 部分 */
      bridge(socket, t);
    }, function () { socket.destroy(); });
  }

  pump();
}

/* ───── main entry ───── */

/*
 * start(opts, onReady)
 *   onReady(err): 监听结果回调。err 为 null 表示监听成功；
 *   EADDRINUSE 等监听失败时携带错误，调用方据此判断 running 状态，
 *   避免"返回成功但实际未监听"的竞态（错误事件晚于同步返回）。
 *
 * close 语义：停止代理时强制断开全部存量会话（默认 close 只停止 accept，
 * 已建立的隧道会残留到自然结束）。
 */
function startProxyServer(opts, onReady) {
  var listenPort = opts.listenPort;

  /* 存量会话集合，close 时强制断开 */
  var sessions = new Set();

  var server = net.createServer(function (socket) {
    sessions.add(socket);
    socket.on('close', function () { sessions.delete(socket); });
    socket.setTimeout(60000);
    socket.on('timeout', function () { socket.destroy(); });
    socket.on('error', noop);

    /* 首字节判型：0x05 -> SOCKS5，否则 -> HTTP */
    socket.once('data', function (chunk) {
      if (chunk.length > 0 && chunk[0] === 0x05) {
        handleSocks5(socket, chunk);
      } else {
        handleHttp(socket, chunk);
      }
    });
  });

  var ready = false;
  function fire(err) {
    if (onReady) { var cb = onReady; onReady = null; cb(err); }
  }

  server.on('error', function (err) {
    console.error('[PROXY:%s] Error: %s', listenPort, err.message);
    if (!ready) fire(err); /* 监听失败：回调通知调用方 */
  });
  server.on('listening', function () {
    ready = true;
    fire(null);
    console.log('[PROXY:%s] HTTP+SOCKS5 mixed proxy listening', listenPort);
  });

  var origClose = server.close.bind(server);
  server.close = function (cb) {
    sessions.forEach(function (s) { s.destroy(); });
    return origClose(cb);
  };

  server.listen(listenPort, '0.0.0.0');

  return server;
}
