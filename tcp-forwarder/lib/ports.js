'use strict';

/* 端口合法性：返回 1-65535 的整数，非法（含 NaN/越界/非纯数字）返回 null */
function validPort(v) {
  if (typeof v === 'number' && !isFinite(v)) return null;
  var s = String(v).trim();
  if (!/^\d+$/.test(s)) return null;
  var n = parseInt(s, 10);
  return (n >= 1 && n <= 65535) ? n : null;
}

module.exports = { validPort: validPort };
