/* global frontend for TCP Forwarder */

var editIndex = null;
var cachedRules = [];
var cachedProxy = { enabled: false, port: 8088, running: false };

/* 自动刷新间隔（毫秒） */
var REFRESH_MS = 10000;
var refreshTimer = null;

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function api(method, body, cb) {
  var x = new XMLHttpRequest();
  x.open('POST', '/api');
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function () {
    try {
      cb(JSON.parse(x.responseText));
    } catch (e) {
      alert('响应解析失败：' + e.message);
    }
  };
  x.onerror = function () {
    alert('网络错误，请确认服务是否运行');
  };
  x.send(JSON.stringify({ action: method, rule: body }));
}

/* 同时渲染两套 DOM：宽屏表格 #rulesTable，窄屏卡片 #ruleCards，由 CSS 断点决定显隐 */
function renderRules(rules, gateway) {
  cachedRules = rules;
  var gwDisplay = gateway
    ? escapeHtml(gateway)
    : '<span class="gw-missing">未检测到</span>';

  document.getElementById('gatewayDisplay').innerHTML = gwDisplay;
  document.getElementById('webPort').textContent = window.location.port || '80';

  var tableRows = '';
  var cards = '';
  var activeCount = 0;

  for (var i = 0; i < rules.length; i++) {
    var r = rules[i];
    if (r.enabled) activeCount++;

    var statusClass = r.enabled ? 'on' : 'off';
    var statusText = r.enabled ? '运行中' : '已停止';
    var toggleText = r.enabled ? '停止' : '启动';
    var displayHost = (r.targetHost === 'usb_gateway')
      ? 'USB 网关 (' + gwDisplay + ')'
      : escapeHtml(r.targetHost);
    var protClass = r.protocol === 'ftp' ? 'proto-ftp' : 'proto-tcp';
    var protLabel = r.protocol === 'ftp' ? 'FTP' : 'TCP';
    var nameHtml = escapeHtml(r.name || ('规则 ' + (i + 1)));
    var protBadge = '<span class="proto-badge ' + protClass + '">' + protLabel + '</span>';
    var portHtml = escapeHtml(String(r.listenPort));
    var targetHtml = displayHost + ':' + escapeHtml(String(r.targetPort));

    tableRows += '<tr>' +
      '<td>' + nameHtml + '<br>' + protBadge + '</td>' +
      '<td class="mono">' + portHtml + '</td>' +
      '<td class="mono">' + targetHtml + '</td>' +
      '<td><span class="badge ' + statusClass + '">' + statusText + '</span></td>' +
      '<td class="actions">' +
        '<button class="btn-sm btn-toggle" onclick="toggleRule(' + i + ')">' + toggleText + '</button>' +
        '<button class="btn-sm btn-edit" onclick="editRule(' + i + ')">编辑</button>' +
        '<button class="btn-sm btn-danger" onclick="deleteRule(' + i + ')">删除</button>' +
      '</td>' +
    '</tr>';

    cards += '<div class="rule-card">' +
      '<div class="card-head">' +
        '<span class="card-name">' + nameHtml + ' ' + protBadge + '</span>' +
        '<span class="badge ' + statusClass + '">' + statusText + '</span>' +
      '</div>' +
      '<div class="card-line">监听 <span class="mono">' + portHtml + '</span></div>' +
      '<div class="card-line">目标 <span class="mono">' + targetHtml + '</span></div>' +
      '<div class="card-actions">' +
        '<button class="btn-sm btn-toggle" onclick="toggleRule(' + i + ')">' + toggleText + '</button>' +
        '<button class="btn-sm btn-edit" onclick="editRule(' + i + ')">编辑</button>' +
        '<button class="btn-sm btn-danger" onclick="deleteRule(' + i + ')">删除</button>' +
      '</div>' +
    '</div>';
  }

  document.getElementById('rulesBody').innerHTML = tableRows;
  document.getElementById('ruleCards').innerHTML = cards;

  var showEmpty = rules.length === 0;
  document.getElementById('emptyState').style.display = showEmpty ? 'block' : 'none';
  /* 有规则时清空内联 display，交由 CSS 断点控制显隐 */
  document.getElementById('rulesTable').style.display = showEmpty ? 'none' : '';
  document.getElementById('ruleCards').style.display = showEmpty ? 'none' : '';

  document.getElementById('stats').textContent = rules.length + ' 条规则，' + activeCount + ' 条活跃';
}

/* 列表自动刷新：上次渲染完成后才排下一次，避免请求堆积 */
function scheduleRefresh() {
  if (refreshTimer) return;
  refreshTimer = setTimeout(function () {
    refreshTimer = null;
    loadData();
  }, REFRESH_MS);
}

function loadData() {
  var rulesData = null;
  var gwData = null;

  function tryRender() {
    if (rulesData === null || gwData === null) return;
    renderRules(rulesData.rules, gwData.gateway);
    scheduleRefresh();
  }

  var xr = new XMLHttpRequest();
  xr.open('GET', '/api/rules');
  xr.onload = function () {
    try { rulesData = JSON.parse(xr.responseText); } catch (e) { rulesData = { rules: [] }; }
    tryRender();
  };
  xr.onerror = function () { rulesData = { rules: [] }; tryRender(); };
  xr.send();

  var xg = new XMLHttpRequest();
  xg.open('GET', '/api/gateway');
  xg.onload = function () {
    try { gwData = JSON.parse(xg.responseText); } catch (e) { gwData = { gateway: null }; }
    tryRender();
  };
  xg.onerror = function () { gwData = { gateway: null }; tryRender(); };
  xg.send();

  /* 代理状态独立渲染，不阻塞规则/网关刷新 */
  var xp = new XMLHttpRequest();
  xp.open('GET', '/api/proxy');
  xp.onload = function () {
    try { renderProxy(JSON.parse(xp.responseText)); } catch (e) {}
  };
  xp.onerror = function () {};
  xp.send();
}

/* ───── 流量代理 ───── */

function renderProxy(cfg) {
  if (!cfg) return;
  cachedProxy = cfg;

  var running = !!cfg.running;
  var statusEl = document.getElementById('proxyStatus');
  statusEl.className = 'badge ' + (running ? 'on' : 'off');
  statusEl.textContent = running ? '运行中' : '已停止';
  document.getElementById('proxyToggleBtn').textContent = running ? '停止' : '启动';

  /* 自动刷新时不要覆盖正在输入的端口 */
  var portEl = document.getElementById('proxyPort');
  if (document.activeElement !== portEl) portEl.value = cfg.port;

  document.getElementById('proxyAddr').textContent = (window.location.hostname || '本机') + ':' + cfg.port;
}

function toggleProxy() {
  var port = parseInt(document.getElementById('proxyPort').value, 10);
  if (!(port >= 1 && port <= 65535)) {
    alert('代理端口需在 1-65535 之间');
    return;
  }
  var nextEnabled = !cachedProxy.running;
  var x = new XMLHttpRequest();
  x.open('POST', '/api/proxy');
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function () {
    try {
      var res = JSON.parse(x.responseText);
      if (res.ok) { renderProxy(res); }
      else { alert(res.error || '操作失败'); renderProxy(cachedProxy); }
    } catch (e) { alert('响应解析失败：' + e.message); }
  };
  x.onerror = function () { alert('网络错误，请确认服务是否运行'); };
  x.send(JSON.stringify({ enabled: nextEnabled, port: port }));
}

function resetForm() {
  editIndex = null;
  document.getElementById('fName').value = '';
  document.getElementById('fListen').value = '';
  document.getElementById('fHost').value = '';
  document.getElementById('fPort').value = '';
  document.getElementById('fProtocol').value = 'tcp';
  document.getElementById('formTitle').textContent = '新建规则';
  document.getElementById('formSubmitBtn').textContent = '添加';
  document.getElementById('addForm').style.display = 'none';
}

function showAddForm() {
  resetForm();
  document.getElementById('addForm').style.display = 'block';
  document.getElementById('fName').focus();
  /* 手机端点 FAB 时滚动到表单，老 WebView 忽略平滑参数，直接跳转 */
  document.getElementById('addForm').scrollIntoView();
}

function hideAddForm() {
  resetForm();
}

function addRule() {
  var n = document.getElementById('fName').value.trim();
  var lp = parseInt(document.getElementById('fListen').value, 10);
  var h = document.getElementById('fHost').value.trim();
  var p = parseInt(document.getElementById('fPort').value, 10);
  var prot = document.getElementById('fProtocol').value;
  if (!h || !(lp >= 1 && lp <= 65535) || !(p >= 1 && p <= 65535)) {
    alert('请填写目标主机，端口需在 1-65535 之间');
    return;
  }
  if (editIndex !== null) {
    api('edit', { index: editIndex, data: { name: n, listenPort: lp, targetHost: h, targetPort: p, protocol: prot } }, function (res) {
      if (res.ok) { resetForm(); loadData(); }
      else { alert(res.error || '保存失败'); }
    });
  } else {
    api('add', { name: n, listenPort: lp, targetHost: h, targetPort: p, protocol: prot, enabled: true }, function (res) {
      if (res.ok) { resetForm(); loadData(); }
      else { alert(res.error || '添加失败'); }
    });
  }
}

function editRule(i) {
  var r = cachedRules[i];
  if (!r) return;
  editIndex = i;
  document.getElementById('fName').value = r.name;
  document.getElementById('fListen').value = r.listenPort;
  document.getElementById('fHost').value = r.targetHost;
  document.getElementById('fPort').value = r.targetPort;
  document.getElementById('formTitle').textContent = '编辑规则';
  document.getElementById('formSubmitBtn').textContent = '保存';
  document.getElementById('fProtocol').value = r.protocol || 'tcp';
  document.getElementById('addForm').style.display = 'block';
  document.getElementById('fName').focus();
}

function toggleRule(i) {
  api('toggle', { index: i }, function (res) {
    if (res.ok) { loadData(); }
    else { alert(res.error || '操作失败'); }
  });
}

function deleteRule(i) {
  if (confirm('确定删除此规则？')) {
    api('delete', { index: i }, function (res) {
      if (res.ok) { loadData(); }
      else { alert(res.error || '删除失败'); }
    });
  }
}

window.onload = loadData;
