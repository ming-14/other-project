/**
 * 通用界面功能模块
 * 负责处理通知、提示、询问等通用界面功能
 */

class UIManager {
  /**
   * 构造函数
   */
  constructor() {
    // 初始化
    this.init();
  }

  /**
   * 初始化UI管理器
   */
  init() {
    // 初始化通知元素
    this.notification = document.getElementById('notification');
  }

  /**
   * 显示通知
   * @param {string} message - 通知消息
   * @param {string} type - 通知类型 (success, error, info)
   */
  showNotification(message, type = 'info') {
    if (!this.notification) return;
    
    this.notification.textContent = message;
    this.notification.className = `notification ${type}`;
    this.notification.classList.add('show');
    
    // 3秒后自动隐藏
    setTimeout(() => {
      this.notification.classList.remove('show');
    }, 3000);
  }

  /**
   * 显示确认对话框
   * @param {string} message - 确认消息
   * @returns {boolean} 用户的选择 (true 确认, false 取消)
   */
  showConfirm(message) {
    return confirm(message);
  }

  /**
   * 显示提示对话框
   * @param {string} message - 提示消息
   */
  showAlert(message) {
    alert(message);
  }

  /**
   * 显示帮助信息
   */
  showHelp() {
    const helpMessage = `力量训练指南App

功能说明：
1. 选择训练计划：根据需求选择合适的训练计划
2. 开始训练：按照指引完成每个动作
3. 视频演示：查看标准动作视频
4. 训练控制：可暂停、上一组、下一组
5. 进度追踪：实时查看训练进度

如有问题，请联系开发团队。`;
    
    this.showAlert(helpMessage);
  }
}

// 导出UIManager类
if (typeof module !== 'undefined' && module.exports) {
  module.exports = UIManager;
}