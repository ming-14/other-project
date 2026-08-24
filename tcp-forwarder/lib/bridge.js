'use strict';

/*
 * 双向桥接：a <-> b 双向 pipe，任一方关闭即销毁对方。
 *
 * 调用点负责连接建立前的处理（握手超时、连接失败等），
 * 本函数只负责连接建立后的透传：
 *   - error 静默（管道断开的正常噪音）
 *   - 任一方 close 时 destroy 对方（对称，destroy 幂等）
 *   - pendingBuf 为握手阶段已缓冲的数据，先写给 b 再开始管道
 */
module.exports = function bridge(a, b, pendingBuf) {
  if (pendingBuf && pendingBuf.length) b.write(pendingBuf);
  a.pipe(b);
  b.pipe(a);
  a.on('error', noop);
  b.on('error', noop);
  a.on('close', function () { b.destroy(); });
  b.on('close', function () { a.destroy(); });
};

function noop() {}
