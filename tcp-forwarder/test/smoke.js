'use strict';
/* 冒烟测试：验证修复后的关键路径
 * 用法：NODE=/path/to/node node test/smoke.js
 *  1. 静态面板 + API + 静态缓存 mtime 失效 + 路径遍历防护
 *  2. TCP 转发
 *  3. FTP: 控制通道透传、PASV/EPSV 重写、忽略 227 中的错误 IP、latin1 字节透明、空闲不断连
 *  4. CRUD（add/toggle/edit/delete）+ 重复端口 400 + 超大 body 413
 *     + 删除规则强制断开存量 TCP/FTP 会话（含 FTP 数据端口回收）
 *  5. 混合代理: HTTP CONNECT 隧道、HTTP 绝对 URL 转发、SOCKS5(IPv4/域名/BIND 拒绝)
 *     + 代理端口被占 400、停止代理强制断开存量隧道
 *  6. 端口校验：越界/零/脏字符串拒绝；usb_gateway 规则逐连接解析
 * 运行后自动恢复 rules.json / style.css / proxy.json 原内容，并退出 app 进程。
 */
var http = require('http');
var net = require('net');
var fs = require('fs');
var path = require('path');
var cp = require('child_process');

/* node 可执行路径：优先环境变量 NODE，默认取 AGENTS.md 中约定的测试 node */
var NODE = process.env.NODE || 'C:\\UserProgram\\node-v13.0.0-win-x64\\node.exe';
var ROOT = path.join(__dirname, '..');
var WEB_PORT = 18080;
var FTP_LISTEN = 15210, FTP_TARGET = 15211;
var TCP_LISTEN = 15200, TCP_TARGET = 15201, TCP2_TARGET = 15203;
var CRUD_LISTEN = 15202;
var CRUD_LISTEN2 = 15204;
var RULES_FILE = path.join(ROOT, 'rules.json');
var CSS_FILE = path.join(ROOT, 'public', 'style.css');
var PROXY_FILE = path.join(ROOT, 'proxy.json');
var PROXY_LISTEN = 15300;
var HTTP_TARGET = 15206;
var DOH_PORT = 15400;

var failures = 0;
function ok(name, cond, extra) {
  if (cond) console.log('PASS ' + name);
  else { failures++; console.log('FAIL ' + name + (extra ? ' :: ' + String(extra) : '')); }
}
function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

function request(method, url, body) {
  return new Promise(function (resolve, reject) {
    var req = http.request({ host: '127.0.0.1', port: WEB_PORT, path: url, method: method }, function (res) {
      var data = '';
      res.on('data', function (c) { data += c; });
      res.on('end', function () { resolve({ status: res.statusCode, body: data }); });
    });
    req.on('error', reject);
    if (body) { req.setHeader('Content-Type', 'application/json'); req.write(JSON.stringify(body)); }
    req.end();
  });
}

function connect(port, host) {
  return new Promise(function (resolve, reject) {
    var s = net.connect(port, host || '127.0.0.1');
    s.on('connect', function () { resolve(s); });
    s.on('error', reject);
  });
}

function readLine(sock, timeout) {
  return new Promise(function (resolve, reject) {
    var buf = '';
    var to = setTimeout(function () {
      sock.removeAllListeners('data');
      reject(new Error('readLine timeout: ' + JSON.stringify(buf)));
    }, timeout || 5000);
    function onData(c) {
      buf += c.toString('latin1');
      var idx = buf.indexOf('\r\n');
      if (idx !== -1) {
        clearTimeout(to);
        sock.removeListener('data', onData);
        resolve(buf.slice(0, idx));
      }
    }
    sock.on('data', onData);
  });
}

/* 持久行读取器：保持监听器不摘除，避免两行响应之间的数据被丢弃 */
function lineReader(sock) {
  var buf = '';
  var waiters = [];
  sock.on('data', function (c) { buf += c.toString('latin1'); pump(); });
  function pump() {
    while (waiters.length) {
      var idx = buf.indexOf('\r\n');
      if (idx === -1) break;
      var line = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      var w = waiters.shift();
      clearTimeout(w.to);
      w.resolve(line);
    }
  }
  return function (timeout) {
    return new Promise(function (resolve, reject) {
      var to = setTimeout(function () {
        reject(new Error('readLine timeout, buffered: ' + JSON.stringify(buf)));
      }, timeout || 5000);
      waiters.push({ resolve: resolve, to: to });
      pump();
    });
  };
}

function readAll(sock, timeout) {
  return new Promise(function (resolve, reject) {
    var b = '';
    var to = setTimeout(function () {
      sock.removeAllListeners('data');
      reject(new Error('readAll timeout: ' + JSON.stringify(b)));
    }, timeout || 5000);
    sock.on('data', function (d) { b += d.toString('latin1'); });
    sock.on('close', function () { clearTimeout(to); resolve(b); });
  });
}

/* 连接被拒则立即返回 true；若还能连上则等 close 生效后重试 */
async function expectRefused(port) {
  for (var i = 0; i < 15; i++) {
    var got = false;
    try { var s = await connect(port); got = true; s.destroy(); } catch (e) {}
    if (!got) return true;
    await sleep(100);
  }
  return false;
}

/* 等待端口开始监听（listen 是异步的，POST /api/proxy 返回后可能尚未就绪） */
async function expectListening(port) {
  for (var i = 0; i < 20; i++) {
    try { var s = await connect(port); s.destroy(); return true; } catch (e) {}
    await sleep(100);
  }
  return false;
}

/* 读到指定字节数；多余字节 unshift 回流，避免同 chunk 数据丢失 */
function readBytes(sock, n, timeout) {
  return new Promise(function (resolve, reject) {
    var buf = Buffer.alloc(0);
    var to = setTimeout(function () {
      sock.removeAllListeners('data');
      reject(new Error('readBytes timeout, got ' + buf.length + '/' + n));
    }, timeout || 5000);
    function onData(c) {
      buf = Buffer.concat([buf, c]);
      if (buf.length >= n) {
        clearTimeout(to);
        sock.removeListener('data', onData);
        var extra = buf.slice(n);
        if (extra.length) sock.unshift(extra);
        resolve(buf.slice(0, n));
      }
    }
    sock.on('data', onData);
  });
}

/* 读到指定标记（含标记）；标记后的数据 unshift 回流 */
function readUntil(sock, marker, timeout) {
  return new Promise(function (resolve, reject) {
    var buf = '';
    var to = setTimeout(function () {
      sock.removeAllListeners('data');
      reject(new Error('readUntil timeout: ' + JSON.stringify(buf)));
    }, timeout || 5000);
    function onData(c) {
      buf += c.toString('latin1');
      var idx = buf.indexOf(marker);
      if (idx !== -1) {
        clearTimeout(to);
        sock.removeListener('data', onData);
        var rest = buf.slice(idx + marker.length);
        if (rest) sock.unshift(Buffer.from(rest, 'latin1'));
        resolve(buf.slice(0, idx + marker.length));
      }
    }
    sock.on('data', onData);
  });
}

/* ───── 测试用 echo 服务器 ───── */
function startEcho(port, tag, cb) {
  var s = net.createServer(function (c) {
    c.on('data', function (d) { c.write(tag + d); });
  });
  s.listen(port, '127.0.0.1', function () { cb(s); });
}

/* ───── 测试用 HTTP 目标服务器（代理转发目标） ───── */
function startHttpServer(port, cb) {
  var s = http.createServer(function (req, res) {
    res.writeHead(200, { 'Content-Type': 'text/plain', 'Connection': 'close' });
    res.end('http-ok:' + req.url);
  });
  s.listen(port, '127.0.0.1', function () { cb(s); });
}

/* ───── 测试用 fake DoH 服务器：所有域名解析到 127.0.0.1，本地闭环验证 DoH 路径 ───── */
function startFakeDoh(port, cb) {
  var s = http.createServer(function (req, res) {
    res.writeHead(200, { 'Content-Type': 'application/dns-json' });
    res.end(JSON.stringify({ Status: 0, Answer: [{ name: 'fake.', TTL: 120, type: 1, data: '127.0.0.1' }] }));
  });
  s.listen(port, '127.0.0.1', function () { cb(s); });
}

/* ───── 测试用最小 FTP 服务器 ─────
 * PASV 故意返回错误 IP (10.99.99.99) 以验证代理忽略 227 中的地址、
 * 改用控制连接对端地址。所有响应按 latin1 写，验证代理字节透明。
 */
function startFtpServer(port, cb) {
  var server = net.createServer(function (ctrl) {
    var dataServer = null, dataClient = null;

    ctrl.write('220 test-ftp ready\r\n', 'latin1');

    function closeData() {
      if (dataServer) { try { dataServer.close(); } catch (e) {} dataServer = null; }
      dataClient = null;
    }
    function makeDataListener(cb) {
      dataServer = net.createServer(function (dc) {
        dataClient = dc;
        dc.on('error', function () {});
      });
      dataServer.listen(0, '127.0.0.1', cb);
    }

    ctrl.on('data', function (chunk) {
      var lines = chunk.toString('latin1').split('\r\n');
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (!line) continue;
        var up = line.toUpperCase();
        var resp = null;
        if (up.indexOf('USER') === 0) resp = '331 need password';
        else if (up.indexOf('PASS') === 0) resp = '230 logged in';
        else if (up.indexOf('SYST') === 0) resp = '215 UNIX Type: L8';
        else if (up.indexOf('PWD') === 0) resp = '257 "/"';
        else if (up.indexOf('TYPE') === 0) resp = '200 type set';
        else if (up.indexOf('PASV') === 0) {
          makeDataListener(function () {
            var p = dataServer.address().port;
            ctrl.write('227 Entering Passive Mode (10,99,99,99,' + Math.floor(p / 256) + ',' + (p % 256) + ')\r\n', 'latin1');
          });
          continue;
        } else if (up.indexOf('EPSV') === 0) {
          makeDataListener(function () {
            ctrl.write('229 Entering Extended Passive Mode (|||' + dataServer.address().port + '|)\r\n', 'latin1');
          });
          continue;
        } else if (up.indexOf('LIST') === 0) {
          ctrl.write('150 opening data connection\r\n', 'latin1');
          var sendListing = function () {
            if (dataClient) {
              dataClient.write('total 1\r\n-rw-r--r-- 1 test test 123 Jan 1 2020 test.txt\r\n', 'latin1');
              dataClient.end();
              closeData();
              ctrl.write('226 transfer complete\r\n', 'latin1');
            }
          };
          if (dataClient) sendListing();
          else if (dataServer) dataServer.once('connection', sendListing);
          continue;
        } else if (up.indexOf('ECHO') === 0) {
          resp = '200' + line.slice(4);
        } else if (up.indexOf('QUIT') === 0) {
          ctrl.write('221 bye\r\n', 'latin1');
          ctrl.end();
          return;
        } else resp = '502 not implemented';
        if (resp) ctrl.write(resp + '\r\n', 'latin1');
      }
    });
    ctrl.on('error', function () {});
    ctrl.on('close', closeData);
  });
  server.listen(port, '127.0.0.1', function () { cb(server); });
}

/* ───── main ───── */
async function main() {
  var originalRules = fs.readFileSync(RULES_FILE, 'utf8');
  var originalCss = fs.readFileSync(CSS_FILE, 'utf8');
  var originalProxy = null;
  try { originalProxy = fs.readFileSync(PROXY_FILE, 'utf8'); } catch (e) {}
  var appProc = null, echo1 = null, echo2 = null, ftp = null, fakeDoh = null;
  var leakDir = null, proxyBlocker = null, webBlocker = null;

  try {
    fs.writeFileSync(RULES_FILE, JSON.stringify([
      { name: 'tcp-test', listenPort: TCP_LISTEN, targetHost: '127.0.0.1', targetPort: TCP_TARGET, protocol: 'tcp', enabled: true },
      { name: 'ftp-test', listenPort: FTP_LISTEN, targetHost: '127.0.0.1', targetPort: FTP_TARGET, protocol: 'ftp', enabled: true }
    ], null, 2));

    echo1 = await new Promise(function (res) { startEcho(TCP_TARGET, '', function (s) { res(s); }); });
    echo2 = await new Promise(function (res) { startEcho(TCP2_TARGET, 'v2:', function (s) { res(s); }); });
    ftp = await new Promise(function (res) { startFtpServer(FTP_TARGET, function (s) { res(s); }); });
    fakeDoh = await new Promise(function (res) { startFakeDoh(DOH_PORT, function (s) { res(s); }); });

    appProc = cp.spawn(NODE, [path.join(ROOT, 'app.js'), '--port=' + WEB_PORT], {
      cwd: ROOT,
      stdio: 'ignore',
      env: Object.assign({}, process.env, { DOH_ENDPOINT: 'http://127.0.0.1:' + DOH_PORT + '/resolve' })
    });

    var up = false;
    for (var i = 0; i < 40; i++) {
      await sleep(250);
      try { if ((await request('GET', '/api/rules')).status === 200) { up = true; break; } } catch (e) {}
    }
    ok('web server up', up);

    /* 1. 静态面板与 API */
    var idx = await request('GET', '/');
    ok('index served', idx.status === 200 && idx.body.indexOf('TCP 端口转发') !== -1);
    var css1 = await request('GET', '/style.css');
    ok('css served', css1.status === 200 && css1.body.indexOf('body{') !== -1);
    var gw = await request('GET', '/api/gateway');
    ok('gateway api ok', gw.status === 200 && JSON.parse(gw.body).ok === true);
    var rulesResp = await request('GET', '/api/rules');
    ok('rules api ok', rulesResp.status === 200 && JSON.parse(rulesResp.body).rules.length === 2);

    /* 2. 静态缓存 mtime 失效 */
    fs.writeFileSync(CSS_FILE, originalCss + '\n/* cache-marker-123 */\n');
    await sleep(50);
    var css2 = await request('GET', '/style.css');
    ok('static cache invalidated on mtime change', css2.body.indexOf('cache-marker-123') !== -1);
    fs.writeFileSync(CSS_FILE, originalCss);

    /* 2.5 静态路径遍历防护：/../public2/... 必须被拒绝（裸 socket 发送，绕过客户端路径规范化） */
    leakDir = path.join(ROOT, 'public2');
    try { fs.mkdirSync(leakDir); } catch (e) { if (e.code !== 'EEXIST') throw e; }
    fs.writeFileSync(path.join(leakDir, 'leaked.txt'), 'leaked-content');
    var ls = await connect(WEB_PORT);
    var leakResp = await new Promise(function (resolve) {
      var b = '';
      ls.on('data', function (c) { b += c.toString('latin1'); });
      ls.on('close', function () { resolve(b); });
      ls.write('GET /../public2/leaked.txt HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n');
    });
    ok('path traversal blocked', leakResp.indexOf('200') === -1 && leakResp.indexOf('leaked-content') === -1,
      JSON.stringify(leakResp.slice(0, 60)));

    /* 3. TCP 转发 */
    var tc = await connect(TCP_LISTEN);
    var tcpEcho = await new Promise(function (resolve) {
      tc.on('data', function (d) { resolve(d.toString('latin1')); });
      tc.write('hello-world');
    });
    ok('tcp forward echo', tcpEcho === 'hello-world', tcpEcho);
    tc.destroy();

    /* 4. FTP 流程 */
    var fc = await connect(FTP_LISTEN);
    var readCtrl = lineReader(fc);
    ok('ftp banner 220', (await readCtrl()).indexOf('220') === 0);
    fc.write('USER test\r\n', 'latin1');
    ok('ftp user 331', (await readCtrl()).indexOf('331') === 0);
    fc.write('PASS x\r\n', 'latin1');
    ok('ftp pass 230', (await readCtrl()).indexOf('230') === 0);

    /* PASV：227 应被重写为代理地址，而不是服务器的错误 IP */
    fc.write('PASV\r\n', 'latin1');
    var pasv = await readCtrl();
    var pasvM = /\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)/.exec(pasv);
    var ph = pasvM[1] + '.' + pasvM[2] + '.' + pasvM[3] + '.' + pasvM[4];
    var pp = (parseInt(pasvM[5], 10) << 8) + parseInt(pasvM[6], 10);
    ok('ftp pasv rewritten to proxy addr', ph === '127.0.0.1', pasv);
    var dc = await connect(pp);
    fc.write('LIST\r\n', 'latin1');
    ok('ftp list 150', (await readCtrl()).indexOf('150') === 0);
    var listing = await readAll(dc);
    ok('ftp pasv listing via data conn', listing.indexOf('test.txt') !== -1, JSON.stringify(listing));
    ok('ftp list 226', (await readCtrl()).indexOf('226') === 0);

    /* EPSV：229 重写，数据连接走代理 */
    fc.write('EPSV\r\n', 'latin1');
    var epsv = await readCtrl();
    var epsvM = /\(\|\|\|(\d+)\|\)/.exec(epsv);
    ok('ftp epsv rewritten', !!epsvM && epsv.indexOf('229') === 0, epsv);
    var dc2 = await connect(parseInt(epsvM[1], 10));
    fc.write('LIST\r\n', 'latin1');
    await readCtrl();
    var listing2 = await readAll(dc2);
    ok('ftp epsv listing via data conn', listing2.indexOf('test.txt') !== -1, JSON.stringify(listing2));
    await readCtrl();

    /* latin1 字节透明：0xE9 往返不损坏 */
    fc.write('ECHO caf\xe9\r\n', 'latin1');
    var ech = await readCtrl();
    ok('ftp control latin1 passthrough', ech === '200 caf\xe9', JSON.stringify(ech));

    fc.write('QUIT\r\n', 'latin1');
    await readCtrl();
    fc.destroy();

    /* 4.5 FTP 控制连接空闲不断连：旧代码 10s 空闲超时会误杀正常会话 */
    var fi = await connect(FTP_LISTEN);
    var fiRead = lineReader(fi);
    ok('ftp idle banner', (await fiRead()).indexOf('220') === 0);
    var fiClosed = false;
    fi.on('close', function () { fiClosed = true; });
    await sleep(11000);
    ok('ftp control survives 11s idle', !fiClosed, fiClosed ? '连接被断开' : '');
    fi.destroy();

    /* 4.6 删除 FTP 规则：强制断开存量控制连接并回收数据端口 */
    var fa = await request('POST', '/api', { action: 'add', rule: { name: 'ftp-a4', listenPort: 15212, targetHost: '127.0.0.1', targetPort: FTP_TARGET, protocol: 'ftp', enabled: true } });
    ok('ftp a4 rule add ok', fa.status === 200);
    var fc2 = await connect(15212);
    var fc2Read = lineReader(fc2);
    await fc2Read(); /* banner */
    fc2.write('PASV\r\n', 'latin1');
    var pasv2 = await fc2Read();
    var pasv2M = /\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)/.exec(pasv2);
    var dataPort2 = (parseInt(pasv2M[5], 10) << 8) + parseInt(pasv2M[6], 10);
    var fc2Closed = false;
    fc2.on('close', function () { fc2Closed = true; });
    var rulesA4f = JSON.parse((await request('GET', '/api/rules')).body).rules;
    await request('POST', '/api', { action: 'delete', rule: { index: rulesA4f.length - 1 } });
    await sleep(500);
    ok('delete ftp rule force-closes control conn', fc2Closed);
    ok('delete ftp rule recycles data port', await expectRefused(dataPort2));

    /* 5. CRUD */
    var add = await request('POST', '/api', { action: 'add', rule: { name: 'crud', listenPort: CRUD_LISTEN, targetHost: '127.0.0.1', targetPort: TCP_TARGET, protocol: 'tcp', enabled: true } });
    ok('add rule ok', add.status === 200 && JSON.parse(add.body).ok === true);
    var tc2 = await connect(CRUD_LISTEN);
    var e2 = await new Promise(function (res) { tc2.on('data', function (d) { res(d.toString()); }); tc2.write('ping'); });
    ok('added rule forwards', e2 === 'ping', e2);
    tc2.destroy();

    var rulesArr = JSON.parse((await request('GET', '/api/rules')).body).rules;
    var idxNew = rulesArr.length - 1;

    await request('POST', '/api', { action: 'toggle', rule: { index: idxNew } });
    ok('toggle stops listener', await expectRefused(CRUD_LISTEN));

    await request('POST', '/api', { action: 'toggle', rule: { index: idxNew } });
    var ed = await request('POST', '/api', { action: 'edit', rule: { index: idxNew, data: { name: 'crud', listenPort: CRUD_LISTEN, targetHost: '127.0.0.1', targetPort: TCP2_TARGET, protocol: 'tcp' } } });
    ok('edit ok', ed.status === 200 && JSON.parse(ed.body).ok === true);
    var tc4 = await connect(CRUD_LISTEN);
    var e4 = await new Promise(function (res) { tc4.on('data', function (d) { res(d.toString()); }); tc4.write('ping'); });
    ok('edited rule forwards to new target', e4 === 'v2:ping', e4);
    tc4.destroy();

    await request('POST', '/api', { action: 'delete', rule: { index: idxNew } });
    ok('delete stops listener', await expectRefused(CRUD_LISTEN));

    var dup = await request('POST', '/api', { action: 'add', rule: { listenPort: TCP_LISTEN, targetHost: '127.0.0.1', targetPort: 9, protocol: 'tcp' } });
    ok('duplicate port rejected 400', dup.status === 400, 'status=' + dup.status);

    var big = await request('POST', '/api', { action: 'add', rule: { name: new Array(70000).join('x'), listenPort: 1, targetHost: '1', targetPort: 1 } });
    ok('large body rejected 413', big.status === 413, 'status=' + big.status);

    /* 6. 修复回归：端口范围 / 字符串重复端口 / 编辑保持启停状态 */
    var bad1 = await request('POST', '/api', { action: 'add', rule: { listenPort: 70000, targetHost: '127.0.0.1', targetPort: 1, protocol: 'tcp' } });
    ok('out-of-range port rejected 400', bad1.status === 400, 'status=' + bad1.status);

    var bad2 = await request('POST', '/api', { action: 'add', rule: { listenPort: 15205, targetHost: '127.0.0.1', targetPort: 0, protocol: 'tcp' } });
    ok('zero target port rejected 400', bad2.status === 400, 'status=' + bad2.status);

    var bad3 = await request('POST', '/api', { action: 'add', rule: { listenPort: String(TCP_LISTEN), targetHost: '127.0.0.1', targetPort: 1, protocol: 'tcp' } });
    ok('string-typed duplicate port rejected 400', bad3.status === 400, 'status=' + bad3.status);

    var add2 = await request('POST', '/api', { action: 'add', rule: { name: 'crud2', listenPort: CRUD_LISTEN2, targetHost: '127.0.0.1', targetPort: TCP_TARGET, protocol: 'tcp', enabled: true } });
    ok('add second rule ok', add2.status === 200);
    var rules2 = JSON.parse((await request('GET', '/api/rules')).body).rules;
    var idx2 = rules2.length - 1;
    await request('POST', '/api', { action: 'toggle', rule: { index: idx2 } });
    ok('second rule stopped', await expectRefused(CRUD_LISTEN2));
    var ed2 = await request('POST', '/api', { action: 'edit', rule: { index: idx2, data: { name: 'renamed', listenPort: CRUD_LISTEN2, targetHost: '127.0.0.1', targetPort: TCP2_TARGET, protocol: 'tcp' } } });
    ok('edit stopped rule accepted', ed2.status === 200);
    var rules3 = JSON.parse((await request('GET', '/api/rules')).body).rules;
    ok('edit keeps rule disabled', rules3[idx2].enabled === false, 'enabled=' + rules3[idx2].enabled);
    ok('stopped rule still not listening', await expectRefused(CRUD_LISTEN2));
    await request('POST', '/api', { action: 'delete', rule: { index: idx2 } });

    /* 删除规则强制断开存量 TCP 连接（A4 语义） */
    var a4Add = await request('POST', '/api', { action: 'add', rule: { name: 'a4', listenPort: 15208, targetHost: '127.0.0.1', targetPort: TCP_TARGET, protocol: 'tcp', enabled: true } });
    ok('a4 add rule ok', a4Add.status === 200);
    var a4sock = await connect(15208);
    await new Promise(function (res) { a4sock.on('data', function () { res(); }); a4sock.write('ping'); });
    var a4Closed = false;
    a4sock.on('close', function () { a4Closed = true; });
    var rules4 = JSON.parse((await request('GET', '/api/rules')).body).rules;
    await request('POST', '/api', { action: 'delete', rule: { index: rules4.length - 1 } });
    await sleep(500);
    ok('delete rule force-closes active tcp connection', a4Closed);

    /* 脏端口字符串拒绝 */
    var dirty = await request('POST', '/api', { action: 'add', rule: { listenPort: '15206abc', targetHost: '127.0.0.1', targetPort: 1, protocol: 'tcp' } });
    ok('dirty port string rejected 400', dirty.status === 400, 'status=' + dirty.status);

    /* usb_gateway 规则逐连接解析（Windows 无网关 → 回退 127.0.0.1） */
    var gwAdd = await request('POST', '/api', { action: 'add', rule: { name: 'gw', listenPort: 15207, targetHost: 'usb_gateway', targetPort: TCP_TARGET, protocol: 'tcp', enabled: true } });
    ok('usb_gateway rule add ok', gwAdd.status === 200);
    var gwSock = await connect(15207);
    var gwEcho = await new Promise(function (res) { gwSock.on('data', function (d) { res(d.toString('latin1')); }); gwSock.write('gw-test'); });
    ok('usb_gateway rule forwards (fallback 127.0.0.1)', gwEcho === 'gw-test', gwEcho);
    gwSock.destroy();
    var rulesGw = JSON.parse((await request('GET', '/api/rules')).body).rules;
    await request('POST', '/api', { action: 'delete', rule: { index: rulesGw.length - 1 } });

    /* 7. 混合代理（HTTP + SOCKS5 单端口） */
    var proxyApi = await request('GET', '/api/proxy');
    ok('proxy api default off', proxyApi.status === 200 && JSON.parse(proxyApi.body).running === false);

    /* 代理 API 大 body 拒绝（与 /api 一致） */
    var bigProxy = await request('POST', '/api/proxy', { enabled: true, port: PROXY_LISTEN, pad: new Array(70000).join('x') });
    ok('proxy api large body rejected 413', bigProxy.status === 413, 'status=' + bigProxy.status);

    /* 代理端口被占用：立即 400 且 running=false（无异步竞态） */
    proxyBlocker = net.createServer();
    await new Promise(function (res) { proxyBlocker.listen(15301, '0.0.0.0', res); });
    var busy = await request('POST', '/api/proxy', { enabled: true, port: 15301 });
    var busyBody = JSON.parse(busy.body);
    ok('proxy on busy port returns 400', busy.status === 400 && busyBody.running === false,
      'status=' + busy.status + ' body=' + JSON.stringify(busyBody));
    proxyBlocker.close(); proxyBlocker = null;

    var httpTarget = await new Promise(function (res) { startHttpServer(HTTP_TARGET, function (s) { res(s); }); });

    var en = await request('POST', '/api/proxy', { enabled: true, port: PROXY_LISTEN });
    ok('proxy start ok', en.status === 200 && JSON.parse(en.body).running === true);
    ok('proxy port listening', await expectListening(PROXY_LISTEN));

    /* HTTP CONNECT 隧道 */
    var hc = await connect(PROXY_LISTEN);
    hc.write('CONNECT 127.0.0.1:' + TCP_TARGET + ' HTTP/1.1\r\nHost: 127.0.0.1:' + TCP_TARGET + '\r\n\r\n');
    var hcResp = await readUntil(hc, '\r\n\r\n');
    ok('http connect 200 established', hcResp.indexOf('200 Connection Established') !== -1, JSON.stringify(hcResp));
    var hcEcho = await new Promise(function (resolve) {
      hc.on('data', function (d) { resolve(d.toString('latin1')); });
      hc.write('via-connect');
    });
    ok('http connect tunnel echo', hcEcho === 'via-connect', hcEcho);
    hc.destroy();

    /* HTTP 普通请求（绝对 URL 转发） */
    var hg = await connect(PROXY_LISTEN);
    hg.write('GET http://127.0.0.1:' + HTTP_TARGET + '/path?q=1 HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n');
    var hgResp = await readAll(hg);
    ok('http get forwarded via proxy', hgResp.indexOf('200') !== -1 && hgResp.indexOf('http-ok:/path?q=1') !== -1, JSON.stringify(hgResp));

    /* 真实域名经 DoH 解析的测试依赖外网可达性，此处跳过（smoke 运行在本地回环网络） */

    /* SOCKS5 握手 + CONNECT（IPv4 目标） */
    var s5 = await connect(PROXY_LISTEN);
    s5.write(Buffer.from([0x05, 0x01, 0x00]));
    var s5greet = await readBytes(s5, 2);
    ok('socks5 greet no-auth', s5greet[0] === 0x05 && s5greet[1] === 0x00, JSON.stringify(s5greet));
    s5.write(Buffer.from([0x05, 0x01, 0x00, 0x01, 127, 0, 0, 1, TCP_TARGET >> 8, TCP_TARGET & 0xff]));
    var s5resp = await readBytes(s5, 10);
    ok('socks5 connect success', s5resp[0] === 0x05 && s5resp[1] === 0x00, JSON.stringify(s5resp));
    var s5echo = await new Promise(function (resolve) {
      s5.on('data', function (d) { resolve(d.toString('latin1')); });
      s5.write('via-socks5');
    });
    ok('socks5 tunnel echo', s5echo === 'via-socks5', s5echo);
    s5.destroy();

    /* SOCKS5 域名目标（ATYP=3）：代理应自行解析 */
    var s5d = await connect(PROXY_LISTEN);
    s5d.write(Buffer.from([0x05, 0x01, 0x00]));
    await readBytes(s5d, 2);
    var dom = Buffer.from('127.0.0.1', 'utf8');
    var reqBuf = Buffer.concat([Buffer.from([0x05, 0x01, 0x00, 0x03, dom.length]), dom, Buffer.from([TCP_TARGET >> 8, TCP_TARGET & 0xff])]);
    s5d.write(reqBuf);
    var s5dresp = await readBytes(s5d, 10);
    ok('socks5 domain target connect', s5dresp[1] === 0x00, JSON.stringify(s5dresp));
    var s5decho = await new Promise(function (resolve) {
      s5d.on('data', function (d) { resolve(d.toString('latin1')); });
      s5d.write('via-domain');
    });
    ok('socks5 domain tunnel echo', s5decho === 'via-domain', s5decho);
    s5d.destroy();

    /* 不支持的 SOCKS5 命令（BIND）应回 0x07 并断开 */
    var s5b = await connect(PROXY_LISTEN);
    s5b.write(Buffer.from([0x05, 0x01, 0x00]));
    await readBytes(s5b, 2);
    s5b.write(Buffer.from([0x05, 0x02, 0x00, 0x01, 127, 0, 0, 1, 0, 1]));
    var s5bresp = await readBytes(s5b, 10);
    ok('socks5 unsupported command 0x07', s5bresp[1] === 0x07, JSON.stringify(s5bresp));

    /* 域名经本地 fake DoH 解析后连接（验证 DoH 路径闭环） */
    var s5f = await connect(PROXY_LISTEN);
    s5f.write(Buffer.from([0x05, 0x01, 0x00]));
    await readBytes(s5f, 2);
    var fdom = Buffer.from('fake.test', 'utf8');
    s5f.write(Buffer.concat([Buffer.from([0x05, 0x01, 0x00, 0x03, fdom.length]), fdom, Buffer.from([TCP_TARGET >> 8, TCP_TARGET & 0xff])]));
    var s5fresp = await readBytes(s5f, 10);
    ok('socks5 domain via fake DoH connect', s5fresp[1] === 0x00, JSON.stringify(s5fresp));
    var s5fecho = await new Promise(function (resolve) {
      s5f.on('data', function (d) { resolve(d.toString('latin1')); });
      s5f.write('via-doh');
    });
    ok('socks5 domain via fake DoH echo', s5fecho === 'via-doh', s5fecho);
    s5f.destroy();

    /* HTTP CONNECT 域名经 fake DoH 解析后建立隧道 */
    var hcf = await connect(PROXY_LISTEN);
    hcf.write('CONNECT fake.test:' + TCP_TARGET + ' HTTP/1.1\r\nHost: fake.test:' + TCP_TARGET + '\r\n\r\n');
    var hcfResp = await readUntil(hcf, '\r\n\r\n');
    ok('http connect via fake DoH', hcfResp.indexOf('200 Connection Established') !== -1, JSON.stringify(hcfResp));
    var hcfEcho = await new Promise(function (resolve) {
      hcf.on('data', function (d) { resolve(d.toString('latin1')); });
      hcf.write('via-doh-http');
    });
    ok('http connect via fake DoH echo', hcfEcho === 'via-doh-http', hcfEcho);
    hcf.destroy();

    /* 停止代理：存量隧道被强制断开 */
    var ps = await connect(PROXY_LISTEN);
    ps.write('CONNECT 127.0.0.1:' + TCP_TARGET + ' HTTP/1.1\r\nHost: 127.0.0.1:' + TCP_TARGET + '\r\n\r\n');
    await readUntil(ps, '\r\n\r\n');
    var psClosed = false;
    ps.on('close', function () { psClosed = true; });
    var dis = await request('POST', '/api/proxy', { enabled: false, port: PROXY_LISTEN });
    ok('proxy stop ok', dis.status === 200 && JSON.parse(dis.body).running === false);
    await sleep(500);
    ok('proxy stop force-closes active tunnel', psClosed);
    ok('proxy port closed', await expectRefused(PROXY_LISTEN));

    try { httpTarget.close(); } catch (e) {}

    /* 8. Web 端口被占用：优雅退出（exit 1），而不是未捕获异常崩溃 */
    webBlocker = net.createServer();
    await new Promise(function (res) { webBlocker.listen(18085, '0.0.0.0', res); });
    var clashProc = cp.spawn(NODE, [path.join(ROOT, 'app.js'), '--port=18085'], { cwd: ROOT, stdio: 'ignore' });
    var clashCode = await new Promise(function (res) {
      clashProc.on('exit', function (code) { res(code); });
      setTimeout(function () { clashProc.kill(); res(null); }, 5000);
    });
    ok('web port conflict exits gracefully', clashCode === 1, 'code=' + clashCode);
    webBlocker.close(); webBlocker = null;

  } finally {
    try { if (appProc) appProc.kill(); } catch (e) {}
    try { if (echo1) echo1.close(); } catch (e) {}
    try { if (echo2) echo2.close(); } catch (e) {}
    try { if (ftp) ftp.close(); } catch (e) {}
    try { if (fakeDoh) fakeDoh.close(); } catch (e) {}
    try { if (proxyBlocker) proxyBlocker.close(); } catch (e) {}
    try { if (webBlocker) webBlocker.close(); } catch (e) {}
    if (leakDir) {
      try { fs.unlinkSync(path.join(leakDir, 'leaked.txt')); } catch (e) {}
      try { fs.rmdirSync(leakDir); } catch (e) {}
    }
    fs.writeFileSync(RULES_FILE, originalRules);
    fs.writeFileSync(CSS_FILE, originalCss);
    if (originalProxy === null) { try { fs.unlinkSync(PROXY_FILE); } catch (e) {} }
    else { fs.writeFileSync(PROXY_FILE, originalProxy); }
  }

  console.log(failures === 0 ? '\nALL PASS' : '\n' + failures + ' FAILURES');
  process.exit(failures === 0 ? 0 : 1);
}

main().catch(function (e) {
  console.error('FATAL: ' + e.stack);
  process.exit(1);
});
