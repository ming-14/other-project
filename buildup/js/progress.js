/**
 * 训练进度管理模块
 * 负责处理训练进度的更新、显示和管理
 */

class ProgressManager {
  /**
   * 构造函数
   * @param {Object} options - 配置选项
   * @param {string} options.progressBarId - 进度条元素ID
   * @param {string} options.progressTextId - 进度文本元素ID
   * @param {string} options.currentSegmentId - 当前环节元素ID
   */
  constructor(options) {
    this.progressBar = document.getElementById(options.progressBarId);
    this.progressText = document.getElementById(options.progressTextId);
    this.currentSegment = document.getElementById(options.currentSegmentId);
    
    // 进度数据
    this.totalSteps = 0;
    this.currentStep = 0;
    this.currentSegmentName = '';
    
    // 初始化
    this.init();
  }

  /**
   * 初始化进度管理器
   */
  init() {
    this.reset();
  }

  /**
   * 重置进度
   */
  reset() {
    this.totalSteps = 0;
    this.currentStep = 0;
    this.currentSegmentName = '';
    
    this.updateProgressBar(0);
    this.updateProgressText(0, 0);
    this.updateCurrentSegment('');
  }

  /**
   * 设置训练计划数据
   * @param {Object} plan - 训练计划对象
   */
  setPlan(plan) {
    if (!plan) return;
    
    // 修复：使用兼容性更好的写法替代可选链操作符
    const firstSegment = plan.segments && plan.segments[0];
    this.currentSegmentName = firstSegment ? firstSegment.name : '';
    this.updateCurrentSegment(this.currentSegmentName);
  }

  /**
   * 设置总步数
   * @param {number} totalSteps - 总步数
   */
  setTotalSteps(totalSteps) {
    this.totalSteps = totalSteps;
    this.updateProgressText(this.currentStep, this.totalSteps);
  }

  /**
   * 设置当前步数
   * @param {number} currentStep - 当前步数
   */
  setCurrentStep(currentStep) {
    // 修复：防止totalSteps为0时的除零错误
    const maxStep = this.totalSteps > 0 ? this.totalSteps : 0;
    this.currentStep = Math.max(0, Math.min(currentStep, maxStep));
    
    // 计算进度百分比
    const progressPercent = this.totalSteps > 0 
      ? Math.round((this.currentStep / this.totalSteps) * 100) 
      : 0;
    
    // 更新进度条
    this.updateProgressBar(progressPercent);
    
    // 更新进度文本
    this.updateProgressText(this.currentStep, this.totalSteps);
  }

  /**
   * 增加当前步数
   * @param {number} increment - 增加的步数，默认为1
   */
  incrementStep(increment = 1) {
    this.setCurrentStep(this.currentStep + increment);
  }

  /**
   * 减少当前步数
   * @param {number} decrement - 减少的步数，默认为1
   */
  decrementStep(decrement = 1) {
    this.setCurrentStep(this.currentStep - decrement);
  }

  /**
   * 更新当前环节
   * @param {string} segmentName - 环节名称
   */
  updateCurrentSegment(segmentName) {
    this.currentSegmentName = segmentName;
    if (this.currentSegment) {
      this.currentSegment.textContent = segmentName;
    }
  }

  /**
   * 更新进度条
   * @param {number} percent - 进度百分比（0-100）
   */
  updateProgressBar(percent) {
    if (this.progressBar) {
      this.progressBar.style.width = `${percent}%`;
      this.progressBar.setAttribute('aria-valuenow', percent);
      this.progressBar.setAttribute('aria-valuemin', 0);
      this.progressBar.setAttribute('aria-valuemax', 100);
    }
  }

  /**
   * 更新进度文本
   * @param {number} current - 当前进度
   * @param {number} total - 总进度
   */
  updateProgressText(current, total) {
    if (this.progressText) {
      this.progressText.textContent = `${current}/${total}`;
    }
  }

  /**
   * 获取当前进度
   * @returns {Object} 当前进度对象
   */
  getProgress() {
    return {
      currentStep: this.currentStep,
      totalSteps: this.totalSteps,
      progressPercent: this.totalSteps > 0 
        ? Math.round((this.currentStep / this.totalSteps) * 100) 
        : 0,
      currentSegment: this.currentSegmentName
    };
  }

  /**
   * 检查是否完成所有训练
   * @returns {boolean} 是否完成所有训练
   */
  isCompleted() {
    return this.currentStep >= this.totalSteps;
  }

  /**
   * 检查是否是第一步
   * @returns {boolean} 是否是第一步
   */
  isFirstStep() {
    return this.currentStep === 0;
  }

  /**
   * 检查是否是最后一步
   * @returns {boolean} 是否是最后一步
   */
  isLastStep() {
    return this.currentStep >= this.totalSteps - 1;
  }
}

// 导出ProgressManager类
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ProgressManager;
}