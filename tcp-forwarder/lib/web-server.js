'use strict';

var http = require('http');
var fs = require('fs');
var path = require('path');
var forwarder = require('./forwarder');
var proxy = require('./proxy');
var gateway = require('./gateway');
var ports = require('./ports');

/*
 * Web 面板 HTTP 服务：静态文件 + 管理 API。
 * 规则/代理/网关状态都通过各服务模块的函数访问，本文件不持有业务状态。
 */

var MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.eot': 'application/vnd.ms-fontobject',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'text/xml',
  '.wasm': 'application/wasm',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.webp': 'image/webp',
};

/* 静态文件缓存：按 mtime 失效，修改 public/ 后无需重启 */
var staticCache = {};

function loadStatic(filePath) {
  var stat;
  try {
    stat = fs.statSync(filePath);
  } catch (e) {
    return null;
  }
  var entry = staticCache[filePath];
  if (entry && entry.mtime === stat.mtimeMs) return entry.content;
  try {
    var content = fs.readFileSync(filePath, 'utf8');
    staticCache[filePath] = { mtime: stat.mtimeMs, content: content };
    return content;
  } catch (e) {
    return null;
  }
}

function sendJson(res, status, obj) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(obj));
}

function createServer(opts) {
  var publicDir = opts.publicDir;

  return http.createServer(function (req, res) {
    /* GET /api/rules — returns rules JSON */
    if (req.method === 'GET' && req.url === '/api/rules') {
      sendJson(res, 200, { ok: true, rules: forwarder.loadRules() });
      return;
    }

    /* GET /api/gateway — returns detected gateway IP */
    if (req.method === 'GET' && req.url === '/api/gateway') {
      sendJson(res, 200, { ok: true, gateway: gateway.getGateway() });
      return;
    }

    /* GET /api/proxy — returns proxy config & running state */
    if (req.method === 'GET' && req.url === '/api/proxy') {
      var st = proxy.getState();
      sendJson(res, 200, { ok: true, enabled: st.enabled, port: st.port, running: st.running });
      return;
    }

    /* POST /api/proxy — update proxy config & start/stop */
    if (req.method === 'POST' && req.url === '/api/proxy') {
      var pbody = '';
      var ptooLarge = false;
      req.on('data', function (c) { pbody += c; if (pbody.length > 65536) ptooLarge = true; });
      req.on('end', function () {
        if (ptooLarge) {
          sendJson(res, 413, { ok: false, error: 'request too large' });
          return;
        }
        try {
          var msg = JSON.parse(pbody);
          /* 等 listen 结果（成功或 EADDRINUSE）落地后再响应，避免 running 竞态 */
          proxy.update(msg, function (perr) {
            var st = proxy.getState();
            if (perr) {
              sendJson(res, 400, { ok: false, error: perr, enabled: false, port: st.port, running: false });
              return;
            }
            sendJson(res, 200, { ok: true, enabled: st.enabled, port: st.port, running: st.running });
          });
        } catch (e) {
          sendJson(res, 500, { ok: false, error: e.message });
        }
      });
      return;
    }

    /* POST /api — CRUD operations */
    if (req.method === 'POST' && req.url === '/api') {
      var body = '';
      var tooLarge = false;
      req.on('data', function (chunk) {
        body += chunk;
        if (body.length > 65536) tooLarge = true;
      });
      req.on('end', function () {
        if (tooLarge) {
          sendJson(res, 413, { ok: false, error: 'request too large' });
          return;
        }
        try {
          var msg = JSON.parse(body);
          var rules = forwarder.loadRules();

          if (msg.action === 'add') {
            var r = msg.rule;
            var lp = ports.validPort(r && r.listenPort);
            var tp = ports.validPort(r && r.targetPort);
            if (!r || !r.targetHost || lp === null || tp === null) {
              sendJson(res, 400, { ok: false, error: '监听端口/目标端口需为 1-65535，目标主机必填' });
              return;
            }
            var dup = false;
            for (var i = 0; i < rules.length; i++) {
              if (rules[i].listenPort === lp) { dup = true; break; }
            }
            if (dup) {
              sendJson(res, 400, { ok: false, error: 'Port already in use' });
              return;
            }
            rules.push({
              name: r.name || '',
              listenPort: lp,
              targetHost: r.targetHost,
              targetPort: tp,
              protocol: r.protocol === 'ftp' ? 'ftp' : 'tcp',
              enabled: r.enabled !== false,
            });
            forwarder.saveRules(rules);
            forwarder.syncServers(rules);
          } else if (msg.action === 'toggle') {
            var idx = msg.rule.index;
            if (idx >= 0 && idx < rules.length) {
              rules[idx].enabled = !rules[idx].enabled;
              forwarder.saveRules(rules);
              forwarder.syncServers(rules);
            }
          } else if (msg.action === 'edit') {
            var ei = msg.rule.index;
            var ed = msg.rule.data;
            var elp = ports.validPort(ed && ed.listenPort);
            var etp = ports.validPort(ed && ed.targetPort);
            if (ei < 0 || ei >= rules.length || !ed || !ed.targetHost || elp === null || etp === null) {
              sendJson(res, 400, { ok: false, error: '监听端口/目标端口需为 1-65535，目标主机必填' });
              return;
            }
            var dup2 = false;
            for (var k = 0; k < rules.length; k++) {
              if (k !== ei && rules[k].listenPort === elp) {
                dup2 = true; break;
              }
            }
            if (dup2) {
              sendJson(res, 400, { ok: false, error: '端口已被占用' });
              return;
            }
            rules[ei].name = ed.name || '';
            rules[ei].listenPort = elp;
            rules[ei].targetHost = ed.targetHost;
            rules[ei].targetPort = etp;
            rules[ei].protocol = ed.protocol === 'ftp' ? 'ftp' : 'tcp';
            /* 编辑不改变启停状态：已停止的规则编辑保存后保持停止 */
            forwarder.saveRules(rules);
            forwarder.syncServers(rules);
          } else if (msg.action === 'delete') {
            var di = msg.rule.index;
            if (di >= 0 && di < rules.length) {
              rules.splice(di, 1);
              forwarder.saveRules(rules);
              forwarder.syncServers(rules);
            }
          }

          sendJson(res, 200, { ok: true });
        } catch (e) {
          sendJson(res, 500, { ok: false, error: e.message });
        }
      });
      return;
    }

    /* Serve static files from public/ */
    var filePath = req.url === '/' ? path.join(publicDir, 'index.html') : path.join(publicDir, req.url);

    if (filePath.indexOf(publicDir + path.sep) !== 0) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    var ext = path.extname(filePath);
    var contentType = MIME_TYPES[ext] || 'application/octet-stream';

    var content = loadStatic(filePath);
    if (content === null) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
  });
}

module.exports = { createServer: createServer };
