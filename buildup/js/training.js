/**
 * 训练逻辑模块
 * 负责处理训练的主要流程，包括动作切换、倒计时、训练控制等
 */

class TrainingController {
  /**
   * 构造函数
   * @param {Object} options - 配置选项
   * @param {Object} options.videoController - 视频控制器实例
   * @param {Object} options.progressManager - 进度管理器实例
   * @param {Object} options.exercises - 动作库对象
   * @param {Object} options.uiManager - UI管理器实例
   */
  constructor(options) {
    this.videoController = options.videoController;
    this.progressManager = options.progressManager;
    this.exercises = options.exercises;
    this.uiManager = options.uiManager;
    
    // 训练状态
    this.currentPlan = null;
    this.currentSegmentIndex = 0;
    this.currentExerciseIndex = 0;
    this.currentSetIndex = 0;
    this.isTraining = false;
    this.isPaused = false;
    this.isResting = false;
    this.currentCountdown = 0;
    this.totalCountdown = 0;
    
    // 倒计时定时器
    this.countdownTimer = null;
    
    // DOM元素
    this.currentPlanName = document.getElementById('current-plan-name');
    this.exerciseName = document.getElementById('exercise-name');
    this.exercisePurpose = document.getElementById('exercise-purpose');
    this.exerciseSets = document.getElementById('exercise-sets');
    this.repsTimeLabel = document.getElementById('reps-time-label');
    this.exerciseReps = document.getElementById('exercise-reps');
    this.exerciseRest = document.getElementById('exercise-rest');
    this.exerciseTips = document.getElementById('exercise-tips');
    this.exerciseTipsContent = document.getElementById('exercise-tips-content');
    this.tipsToggleBtn = document.getElementById('tips-toggle-btn');
    this.countdownTime = document.getElementById('countdown-time');
    this.countdownLabel = document.getElementById('countdown-label');
    this.countdownProgress = document.getElementById('countdown-progress');
    this.startPauseBtn = document.getElementById('start-pause-btn');
    this.prevBtn = document.getElementById('prev-btn');
    this.nextBtn = document.getElementById('next-btn');
    this.exitBtn = document.getElementById('exit-btn');
    
    // 视频状态跟踪
    this.currentVideoPath = null;
    
    // 音频提示
    this.audioContext = null;
    this.isAudioEnabled = true;
    
    // 初始化
    this.init();
  }

  /**
   * 初始化训练控制器
   */
  init() {
    this.bindEvents();
    this.reset();
  }

  /**
   * 绑定事件监听器
   */
  bindEvents() {
    if (this.startPauseBtn) {
      this.startPauseBtn.addEventListener('click', () => this.toggleStartPause());
    }
    
    if (this.prevBtn) {
      this.prevBtn.addEventListener('click', () => this.prevStep());
    }
    
    if (this.nextBtn) {
      this.nextBtn.addEventListener('click', () => this.nextStep());
    }
    
    if (this.exitBtn) {
      this.exitBtn.addEventListener('click', () => this.exitTraining());
    }
    
    // 移除了键盘快捷键监听
    
    // 提示信息折叠/展开
    if (this.tipsToggleBtn) {
      this.tipsToggleBtn.addEventListener('click', () => this.toggleTips());
    }
  }

  /**
   * 开始训练计划
   * @param {Object} plan - 训练计划对象
   */
  startTraining(plan) {
    if (!plan) return;
    
    // 重置训练状态
    this.reset();
    
    // 设置当前计划
    this.currentPlan = plan;
    
    // 更新UI
    if (this.currentPlanName) {
      this.currentPlanName.textContent = plan.name;
    }
    
    // 初始化进度管理器
    this.progressManager.setPlan(plan);
    
    // 计算总步数
    let totalSteps = 0;
    plan.segments.forEach(segment => {
      segment.exercises.forEach(exercise => {
        // 每个动作的每组都算一步，加上组间休息
        const sets = this.getSetsCount(exercise);
        totalSteps += sets + (sets - 1); // 动作组 + 休息时间（最后一组没有休息）
      });
    });
    this.progressManager.setTotalSteps(totalSteps);
    
    // 显示第一个动作
    this.showCurrentExercise();
    
    // 更新训练状态
    this.isTraining = false;
    this.isPaused = false;
    this.isResting = false;
    
    // 更新UI状态类
    document.body.classList.remove('resting');
    document.body.classList.add('exercising');
  }

  /**
   * 重置训练状态
   */
  reset() {
    // 清除倒计时定时器
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = null;
    }
    
    // 重置状态
    this.currentPlan = null;
    this.currentSegmentIndex = 0;
    this.currentExerciseIndex = 0;
    this.currentSetIndex = 0;
    this.isTraining = false;
    this.isPaused = false;
    this.isResting = false;
    this.isFailureMode = false;
    this.currentCountdown = 0;
    this.totalCountdown = 0;
    // 视频状态
    this.currentVideoPath = null;
    // 次数型动作相关属性
    this.repsTotal = 0;
    this.repDuration = 7;
    this.currentRep = 0;
    
    // 重置视频控制器
    if (this.videoController) {
      this.videoController.reset();
    }
    
    // 重置进度管理器
    if (this.progressManager) {
      this.progressManager.reset();
    }
    
    // 重置UI
    this.resetUI();
  }

  /**
   * 重置UI
   */
  resetUI() {
    if (this.countdownTime) this.countdownTime.textContent = '0';
    if (this.countdownLabel) this.countdownLabel.textContent = '秒';
    if (this.countdownProgress) this.countdownProgress.style.width = '100%';
    if (this.startPauseBtn) this.startPauseBtn.textContent = '开始';
    
    // 移除状态类
    document.body.classList.remove('exercising', 'resting', 'paused');
  }

  /**
   * 折叠/展开关键要领
   */
  toggleTips() {
    if (!this.exerciseTipsContent || !this.tipsToggleBtn) return;
    
    // 切换内容显示状态
    this.exerciseTipsContent.classList.toggle('collapsed');
    
    // 切换按钮状态
    this.tipsToggleBtn.classList.toggle('collapsed');
  }

  /**
   * 获取动作详细信息
   * @param {Object} exercise - 训练计划中的动作对象
   * @returns {Object|null} 完整的动作对象
   */
  getExerciseDetails(exercise) {
    if (!exercise || !this.exercises) return null;
    
    // 如果动作对象包含id字段，则从动作库中获取详细信息
    if (exercise.id) {
      return this.exercises[exercise.id] || null;
    }
    
    // 兼容旧格式，直接返回
    return exercise;
  }

  /**
   * 显示当前动作
   */
  showCurrentExercise() {
    if (!this.currentPlan) return;
    
    const segment = this.currentPlan.segments[this.currentSegmentIndex];
    if (!segment) return;
    
    const exercise = segment.exercises[this.currentExerciseIndex];
    if (!exercise) return;
    
    // 获取动作详细信息
    const exerciseDetails = this.getExerciseDetails(exercise);
    if (!exerciseDetails) return;
    
    // 更新当前环节
    this.progressManager.updateCurrentSegment(segment.name);
    
    // 更新动作信息
    if (this.exerciseName) this.exerciseName.textContent = exerciseDetails.name;
    if (this.exercisePurpose) this.exercisePurpose.textContent = exerciseDetails.purpose;
    
    // 更新组数
    const sets = this.getSetsCount(exercise);
    if (this.exerciseSets) {
      this.exerciseSets.textContent = `${this.currentSetIndex + 1}/${sets}`;
    }
    
    // 获取动作类型
    const exerciseType = exerciseDetails.type;
    
    // 更新标签
    if (this.repsTimeLabel) {
      this.repsTimeLabel.textContent = exerciseType === 'reps' ? '次数：' : '时间：';
    }
    
    // 更新次数/时长
    if (this.exerciseReps) {
      if (exerciseType === 'time' || exercise.time) {
        // 使用timeLabel作为显示文本，如果没有则使用time值
        this.exerciseReps.textContent = exercise.timeLabel || `${exercise.time}秒`;
      } else if (exerciseType === 'reps' || exercise.reps) {
        // 使用repsLabel作为显示文本，如果没有则使用reps值
        this.exerciseReps.textContent = exercise.repsLabel || exercise.reps;
      }
    }
    
    // 更新组间休息
    if (this.exerciseRest) {
      this.exerciseRest.textContent = `${exercise.rest}秒`;
    }
    
    // 更新动作提示（支持HTML换行）
    if (this.exerciseTips) {
      this.exerciseTips.innerHTML = exerciseDetails.tips;
    }
    
    // 加载视频（仅当视频路径变化时才重新加载）
    if (this.videoController && exerciseDetails.videoPath) {
      if (this.currentVideoPath !== exerciseDetails.videoPath) {
        this.videoController.loadVideo(exerciseDetails.videoPath);
        this.currentVideoPath = exerciseDetails.videoPath;
      }
    } else {
      // 如果没有视频路径，重置当前视频路径
      this.currentVideoPath = null;
    }
    
    // 计算倒计时时间
    this.calculateCountdown();
    
    // 更新倒计时显示
    this.updateCountdownDisplay();
    
    // 检查是否需要暂停倒计时（仅在用户未点击开始时）
    if (!this.isTraining) {
      this.pauseCountdown();
    }
  }

  /**
   * 处理范围值，返回中值
   * @param {number|string} value - 范围值，如"45-60"或45
   * @returns {number} 中值
   */
  processRangeValue(value) {
    if (typeof value === 'number') {
      return value;
    }
    
    if (typeof value === 'string') {
      // 处理范围值，如"45-60"
      const match = value.match(/(\d+)\s*-\s*(\d+)/);
      if (match) {
        const min = parseInt(match[1]);
        const max = parseInt(match[2]);
        return Math.round((min + max) / 2);
      }
      
      // 处理单个数值字符串，如"60"
      const num = parseInt(value);
      return isNaN(num) ? 30 : num;
    }
    
    return 30; // 默认值
  }

  /**
   * 计算倒计时时间
   */
  calculateCountdown() {
    if (!this.currentPlan) return;
    
    const exercise = this.getCurrentExercise();
    if (!exercise) return;
    
    // 获取动作详细信息
    const exerciseDetails = this.getExerciseDetails(exercise);
    if (!exerciseDetails) return;
    
    // 检查是否为力竭情况（修复：使用精确匹配）
    const isFailure = (exercise.timeLabel && exercise.timeLabel.trim() === '力竭') || 
                     (exercise.repsLabel && exercise.repsLabel.trim() === '力竭') ||
                     (exercise.time && exercise.time.toString().trim() === '力竭') ||
                     (exercise.reps && exercise.reps.toString().trim() === '力竭');
    
    if (this.isResting) {
      // 休息时间（修复：处理rest为0的情况）
      const restValue = this.processRangeValue(exercise.rest);
      this.totalCountdown = restValue > 0 ? restValue : 5; // 默认5秒休息
      if (this.countdownLabel) {
        this.countdownLabel.textContent = '休息';
      }
      this.currentCountdown = this.totalCountdown;
      this.isFailureMode = false;
    } else if (isFailure) {
      // 力竭模式
      this.isFailureMode = true;
      this.totalCountdown = 0;
      this.currentCountdown = 0;
    } else {
      // 正常训练模式
      this.isFailureMode = false;
      // 获取动作类型
      const exerciseType = exerciseDetails.type;
      
      if (exerciseType === 'time' || exercise.time) {
        // 时间型动作
        this.totalCountdown = this.processRangeValue(exercise.time);
        if (this.countdownLabel) {
          this.countdownLabel.textContent = '秒';
        }
        this.currentCountdown = this.totalCountdown;
      } else if (exerciseType === 'reps' || exercise.reps) {
        // 次数型动作
        this.repsTotal = exercise.reps || 10; // 总次数
        this.repDuration = 7; // 每次动作默认7秒（修复：从3秒改为7秒）
        this.totalCountdown = this.repsTotal * this.repDuration; // 总倒计时时间
        this.currentRep = 0; // 当前次数
        
        // 显示当前次数
        if (this.countdownLabel) {
          this.countdownLabel.textContent = '次';
        }
        this.currentCountdown = this.totalCountdown;
      } else {
        // 默认情况
        this.totalCountdown = 30;
        if (this.countdownLabel) {
          this.countdownLabel.textContent = '准备';
        }
        this.currentCountdown = this.totalCountdown;
      }
    }
  }

  /**
   * 更新倒计时显示
   */
  updateCountdownDisplay() {
    // 确保倒计时不小于0
    this.currentCountdown = Math.max(0, this.currentCountdown);
    
    // 处理力竭模式
    if (this.isFailureMode) {
      // 显示力竭提示文本
      if (this.countdownTime) {
        this.countdownTime.textContent = '力竭时点击下一组';
        this.countdownTime.style.fontSize = '1.5rem'; // 减小字体大小
        this.countdownTime.style.fontWeight = 'normal'; // 正常字重
      }
      
      if (this.countdownLabel) {
        this.countdownLabel.textContent = ''; // 隐藏倒计时标签
      }
      
      if (this.countdownProgress) {
        this.countdownProgress.style.width = '100%'; // 进度条满
      }
      
      // 移除警告样式
      this.countdownTime.parentElement.classList.remove('countdown--warning');
      
      // 暂停倒计时
      this.pauseCountdown();
      return;
    }
    
    // 恢复正常样式
    if (this.countdownTime) {
      this.countdownTime.style.fontSize = ''; // 恢复默认字体大小
      this.countdownTime.style.fontWeight = ''; // 恢复默认字重
    }
    
    // 获取当前动作信息
    const exercise = this.getCurrentExercise();
    const exerciseDetails = exercise ? this.getExerciseDetails(exercise) : null;
    
    if (this.countdownTime) {
      if (exerciseDetails && exerciseDetails.type === 'reps' && !this.isResting) {
        // 次数型动作，显示当前次数
        // 当前次数 = 总次数 - Math.ceil(剩余时间 / 每次时长)
        const currentRep = this.repsTotal - Math.ceil(this.currentCountdown / this.repDuration);
        const displayRep = Math.max(0, Math.min(currentRep, this.repsTotal));
        this.countdownTime.textContent = displayRep > 0 ? displayRep : 0;
      } else {
        // 时间型动作或休息，显示剩余秒数
        this.countdownTime.textContent = this.currentCountdown;
      }
    }
    
    if (this.countdownProgress) {
      const progressPercent = (this.currentCountdown / this.totalCountdown) * 100;
      this.countdownProgress.style.width = `${Math.max(0, Math.min(100, progressPercent))}%`;
    }
    
    // 添加警告样式
    if (this.currentCountdown <= 5 && this.currentCountdown > 0) {
      this.countdownTime.parentElement.classList.add('countdown--warning');
    } else {
      this.countdownTime.parentElement.classList.remove('countdown--warning');
    }
  }

  /**
   * 开始倒计时
   */
  startCountdown() {
    // 力竭模式下不启动倒计时
    if (this.isFailureMode) {
      return;
    }
    
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
    }
    
    this.countdownTimer = setInterval(() => {
      this.currentCountdown--;
      
      // 更新显示
      this.updateCountdownDisplay();
      
      // 倒计时结束
      if (this.currentCountdown <= 0) {
        this.onCountdownEnd();
      }
    }, 1000);
  }

  /**
   * 暂停倒计时
   */
  pauseCountdown() {
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = null;
    }
  }

  /**
   * 倒计时结束处理
   */
  onCountdownEnd() {
    // 清除定时器
    this.pauseCountdown();
    
    // 播放提示音
    this.playBeepSound();
    
    // 检查是否有当前计划
    if (!this.currentPlan) {
      // 没有当前计划，结束训练
      this.finishTraining();
      return;
    }
    
    // 获取当前动作
    const exercise = this.getCurrentExercise();
    if (!exercise) {
      // 没有当前动作，结束训练
      this.finishTraining();
      return;
    }
    
    if (this.isResting) {
      // 休息结束，开始下一组动作
      this.isResting = false;
      this.isPaused = false;
      this.currentSetIndex++;
      
      // 更新UI状态
      document.body.classList.remove('resting');
      document.body.classList.add('exercising');
      
      // 更新进度
      this.progressManager.incrementStep();
      
      // 检查是否完成所有组
      const sets = this.getSetsCount(exercise);
      
      if (this.currentSetIndex < sets) {
        // 还有下一组，显示当前动作
        this.showCurrentExercise();
        this.startCountdown();
      } else {
        // 完成所有组，进入下一个动作
        this.nextExercise();
      }
    } else {
      // 动作结束，更新进度
      this.progressManager.incrementStep();
      
      // 检查是否需要休息
      const sets = this.getSetsCount(exercise);
      
      if (this.currentSetIndex < sets - 1) {
        // 还有下一组，开始休息
        this.isResting = true;
        this.isPaused = false;
        
        // 更新UI状态
        document.body.classList.add('resting');
        document.body.classList.remove('exercising');
        
        // 显示休息倒计时
        this.calculateCountdown();
        this.updateCountdownDisplay();
        this.startCountdown();
      } else {
        // 完成所有组，进入下一个动作
        this.nextExercise();
      }
    }
  }

  /**
   * 切换到下一个动作
   */
  nextExercise() {
    // 检查是否有当前计划
    if (!this.currentPlan) return;
    
    // 重置当前组索引
    this.currentSetIndex = 0;
    
    // 切换到下一个动作
    this.currentExerciseIndex++;
    
    const segment = this.currentPlan.segments[this.currentSegmentIndex];
    
    if (this.currentExerciseIndex >= segment.exercises.length) {
      // 当前环节结束，切换到下一个环节
      this.currentExerciseIndex = 0;
      this.currentSegmentIndex++;
      
      if (this.currentSegmentIndex >= this.currentPlan.segments.length) {
        // 所有环节结束，训练完成
        this.finishTraining();
        return;
      }
    }
    
    // 显示下一个动作
    this.isResting = false;
    this.isPaused = false;
    
    // 更新UI状态
    document.body.classList.remove('resting');
    document.body.classList.add('exercising');
    
    // 更新进度
    this.progressManager.incrementStep();
    
    // 显示当前动作
    this.showCurrentExercise();
    
    // 如果正在训练且未暂停，开始倒计时
    if (this.isTraining && !this.isPaused) {
      this.startCountdown();
    }
  }

  /**
   * 完成训练
   */
  finishTraining() {
    this.isTraining = false;
    this.isPaused = false;
    this.isResting = false;
    
    // 清除定时器
    this.pauseCountdown();
    
    // 重置UI
    this.resetUI();
    
    // 显示训练完成提示
    this.showNotification('训练完成！恭喜你完成了今天的训练计划！', 'success');
    
    // 重置视频控制器
    if (this.videoController) {
      this.videoController.reset();
    }
    
    // 重置进度
    this.progressManager.setCurrentStep(this.progressManager.totalSteps);
  }

  /**
   * 获取当前动作
   * @returns {Object|null} 当前动作对象
   */
  getCurrentExercise() {
    if (!this.currentPlan) return null;
    
    const segment = this.currentPlan.segments[this.currentSegmentIndex];
    if (!segment) return null;
    
    return segment.exercises[this.currentExerciseIndex] || null;
  }

  /**
   * 获取组数
   * @param {Object} exercise - 动作对象
   * @returns {number} 组数
   */
  getSetsCount(exercise) {
    if (!exercise) {
      return 1;
    }
    if (typeof exercise.sets === 'number') {
      return exercise.sets;
    } else if (typeof exercise.sets === 'string') {
      // 处理范围型组数，如 "3-4组"，取最小值
      const match = exercise.sets.match(/^(\d+)/);
      return match ? parseInt(match[1], 10) : 1;
    }
    return 1;
  }

  /**
   * 开始/暂停训练
   */
  toggleStartPause() {
    if (!this.isTraining) {
      // 开始训练
      this.isTraining = true;
      this.isPaused = false;
      
      // 更新UI状态
      document.body.classList.add('exercising');
      document.body.classList.remove('resting', 'paused');
      
      // 开始倒计时
      this.startCountdown();
      
      // 更新按钮文本
      if (this.startPauseBtn) {
        this.startPauseBtn.textContent = '暂停';
      }
    } else if (this.isPaused) {
      // 继续训练
      this.isPaused = false;
      
      // 更新UI状态
      document.body.classList.remove('paused');
      
      // 继续倒计时
      this.startCountdown();
      
      // 更新按钮文本
      if (this.startPauseBtn) {
        this.startPauseBtn.textContent = '暂停';
      }
    } else {
      // 暂停训练
      this.isPaused = true;
      
      // 更新UI状态
      document.body.classList.add('paused');
      
      // 暂停倒计时
      this.pauseCountdown();
      
      // 更新按钮文本
      if (this.startPauseBtn) {
        this.startPauseBtn.textContent = '继续';
      }
    }
  }

  /**
   * 上一组/上一个动作
   */
  prevStep() {
    // 检查是否有当前计划
    if (!this.currentPlan) return;
    
    // 根据当前状态处理
    if (this.isResting) {
      // 如果正在休息，返回上一组动作
      this.isResting = false;
      
      // 更新进度
      this.progressManager.decrementStep();
      
      // 更新UI状态
      document.body.classList.remove('resting');
      document.body.classList.add('exercising');
    } else {
      // 如果正在做动作，检查是否是第一组
      if (this.currentSetIndex > 0) {
        // 返回上一组
        this.currentSetIndex--;
        
        // 如果不是第一组，需要减去休息时间的进度
        if (this.currentSetIndex > 0) {
          this.progressManager.decrementStep();
        }
        this.progressManager.decrementStep();
      } else {
        // 是第一组，返回上一个动作
        this.currentExerciseIndex--;
        
        if (this.currentExerciseIndex < 0) {
          // 当前环节的第一个动作，返回上一个环节
          this.currentSegmentIndex--;
          
          if (this.currentSegmentIndex < 0) {
            // 已经是第一个环节，不能再返回
            this.currentSegmentIndex = 0;
            this.currentExerciseIndex = 0;
            return;
          }
          
          // 切换到上一个环节的最后一个动作
          const prevSegment = this.currentPlan.segments[this.currentSegmentIndex];
          this.currentExerciseIndex = prevSegment.exercises.length - 1;
        }
        
        // 获取上一个动作
        const exercise = this.getCurrentExercise();
        const sets = this.getSetsCount(exercise);
        this.currentSetIndex = sets - 1;
        
        // 更新进度
        // 每个动作的每组都算一步，加上组间休息
        this.progressManager.decrementStep(2 * sets - 1);
      }
    }
    
    // 显示当前动作
    this.showCurrentExercise();
    
    // 如果正在训练且未暂停，继续倒计时
    if (this.isTraining && !this.isPaused && !this.countdownTimer) {
      this.startCountdown();
    }
  }

  /**
   * 下一组/下一个动作
   */
  nextStep() {
    // 检查是否有当前计划
    if (!this.currentPlan) return;
    
    // 如果正在休息，直接结束休息，开始下一组
    if (this.isResting) {
      this.isResting = false;
      
      // 更新进度
      this.progressManager.incrementStep();
      
      // 更新UI状态
      document.body.classList.remove('resting');
      document.body.classList.add('exercising');
      
      // 显示下一组动作
      this.currentSetIndex++;
      this.showCurrentExercise();
      
      // 如果正在训练且未暂停，继续倒计时
      if (this.isTraining && !this.isPaused && !this.countdownTimer) {
        this.startCountdown();
      }
    } else {
      // 直接完成当前动作/组，进入下一步
      const exercise = this.getCurrentExercise();
      if (!exercise) return;
      
      const sets = this.getSetsCount(exercise);
      
      if (this.currentSetIndex < sets - 1) {
        // 完成当前组，开始休息
        this.isResting = true;
        
        // 更新进度
        this.progressManager.incrementStep();
        
        // 更新UI状态
        document.body.classList.add('resting');
        document.body.classList.remove('exercising');
        
        // 显示休息倒计时
        this.calculateCountdown();
        this.updateCountdownDisplay();
        
        // 如果正在训练且未暂停，继续倒计时
        if (this.isTraining && !this.isPaused && !this.countdownTimer) {
          this.startCountdown();
        }
      } else {
        // 完成所有组，进入下一个动作
        this.nextExercise();
      }
    }
  }

  /**
   * 退出训练
   */
  exitTraining() {
    if (this.uiManager.showConfirm('确定要退出训练吗？')) {
      // 重置训练状态
      this.reset();
      
      // 切换到计划选择页面
      this.switchToPlanSelection();
    }
  }

  /**
   * 切换到计划选择页面
   */
  switchToPlanSelection() {
    const planSelection = document.getElementById('plan-selection');
    const trainingPage = document.getElementById('training-page');
    
    if (planSelection && trainingPage) {
      planSelection.style.display = 'block';
      trainingPage.style.display = 'none';
    }
  }

  /**
   * 切换到训练页面
   */
  switchToTrainingPage() {
    const planSelection = document.getElementById('plan-selection');
    const trainingPage = document.getElementById('training-page');
    
    if (planSelection && trainingPage) {
      planSelection.style.display = 'none';
      trainingPage.style.display = 'block';
    }
  }



  /**
   * 播放提示音
   */
  playBeepSound() {
    if (!this.isAudioEnabled) return;
    
    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      
      const oscillator = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(this.audioContext.destination);
      
      oscillator.frequency.setValueAtTime(800, this.audioContext.currentTime);
      oscillator.frequency.setValueAtTime(1000, this.audioContext.currentTime + 0.1);
      
      gainNode.gain.setValueAtTime(0.1, this.audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.2);
      
      oscillator.start(this.audioContext.currentTime);
      oscillator.stop(this.audioContext.currentTime + 0.2);
    } catch (error) {
      console.error('无法播放提示音:', error);
    }
  }

  /**
   * 显示通知
   * @param {string} message - 通知消息
   * @param {string} type - 通知类型 (success, error, info)
   */
  showNotification(message, type = 'info') {
    if (this.uiManager) {
      this.uiManager.showNotification(message, type);
    }
  }

  /**
   * 获取当前训练状态
   * @returns {Object} 训练状态对象
   */
  getTrainingState() {
    return {
      isTraining: this.isTraining,
      isPaused: this.isPaused,
      isResting: this.isResting,
      currentPlan: this.currentPlan,
      currentSegmentIndex: this.currentSegmentIndex,
      currentExerciseIndex: this.currentExerciseIndex,
      currentSetIndex: this.currentSetIndex,
      currentCountdown: this.currentCountdown,
      totalCountdown: this.totalCountdown
    };
  }
}

// 导出TrainingController类
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TrainingController;
}