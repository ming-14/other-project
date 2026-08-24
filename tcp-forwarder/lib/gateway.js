'use strict';

var childProcess = require('child_process');
var fs = require('fs');

/*
 * USB 网关自动检测（Termux/Android USB tethering）。
 *
 * 检测依赖 execSync（同步系统命令），会阻塞事件循环，
 * 因此结果（含 null）缓存 GATEWAY_CACHE_TTL 毫秒：
 *   - /api/gateway 前端每 10s 轮询，命中缓存不阻塞
 *   - usb_gateway 规则的每个新连接都解析，命中缓存不重复执行命令
 * USB 重插/换网段最多 TTL 后生效。
 */
var GATEWAY_CACHE_TTL = 5000;
var cached = { ip: null, at: 0 };

function detectGateway() {
  try {
    var out = childProcess.execSync('ip route show default 2>/dev/null', { encoding: 'utf8', timeout: 2000 });
    var m = out.match(/via\s+(\d+\.\d+\.\d+\.\d+)/);
    if (m) return m[1];
  } catch (e) {}
  try {
    var data = fs.readFileSync('/proc/net/route', 'utf8');
    var lines = data.split('\n');
    for (var i = 1; i < lines.length; i++) {
      var cols = lines[i].trim().split(/\s+/);
      if (cols[1] === '00000000') {
        var hex = cols[2];
        var gw = parseInt(hex.substring(6, 8), 16) + '.' +
                 parseInt(hex.substring(4, 6), 16) + '.' +
                 parseInt(hex.substring(2, 4), 16) + '.' +
                 parseInt(hex.substring(0, 2), 16);
        if (gw !== '0.0.0.0') return gw;
      }
    }
  } catch (e) {}
  return null;
}

function getGateway() {
  var now = Date.now();
  if (now - cached.at < GATEWAY_CACHE_TTL) return cached.ip;
  cached.ip = detectGateway();
  cached.at = now;
  return cached.ip;
}

module.exports = { getGateway: getGateway };
