/**
 * 训练页面主入口文件
 * 负责初始化训练页面和处理URL参数
 */

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', () => {
  // 初始化训练页面
  initTrainingPage();
});

/**
 * 初始化训练页面
 */
function initTrainingPage() {
  // 从URL参数中获取计划ID
  const planId = getPlanIdFromUrl();
  if (!planId) {
    // 如果没有计划ID，返回计划选择页面
    window.location.href = 'index.html';
    return;
  }
  
  // 查找计划
  const plan = Object.values(trainingPlans).find(p => p.id === planId);
  if (!plan) {
    // 如果计划不存在，返回计划选择页面
    window.location.href = 'index.html';
    return;
  }
  
  // 初始化视频控制器
  const videoController = new VideoController(
    'exercise-video',
    'video-placeholder'
  );
  
  // 初始化进度管理器
  const progressManager = new ProgressManager({
    progressBarId: 'progress-bar',
    progressTextId: 'progress-text',
    currentSegmentId: 'current-segment'
  });
  
  // 初始化UI管理器
  const uiManager = new UIManager();
  
  // 初始化训练控制器
  const trainingController = new TrainingController({
    videoController: videoController,
    progressManager: progressManager,
    exercises: exercises,
    uiManager: uiManager
  });
  
  // 初始化主题切换
  initThemeToggle();
  
  // 初始化视频控制按钮
  initVideoControls(videoController);
  
  // 初始化帮助按钮
  initHelpButton(uiManager);
  
  // 初始化动作库
  initExerciseLibrary();
  
  // 初始化动作详情模态框
  initExerciseDetailModal();
  
  // 开始训练
  trainingController.startTraining(plan);
  
  console.log('训练页面初始化完成');
}

/**
 * 从URL参数中获取计划ID
 * @returns {string|null} 计划ID
 */
function getPlanIdFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('plan') || null;
}

/**
 * 初始化主题切换
 */
function initThemeToggle() {
  const themeToggle = document.getElementById('theme-toggle');
  
  if (!themeToggle) return;
  
  // 检查本地存储中的主题偏好
  const savedTheme = localStorage.getItem('theme') || 'light';
  setTheme(savedTheme);
  
  // 添加主题切换事件
  themeToggle.addEventListener('click', () => {
    const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    setTheme(newTheme);
    
    // 保存到本地存储
    localStorage.setItem('theme', newTheme);
  });
  
  /**
   * 设置主题
   * @param {string} theme - 主题名称 (light or dark)
   */
  function setTheme(theme) {
    if (theme === 'dark') {
      document.body.classList.add('dark-theme');
      if (themeToggle) {
        themeToggle.textContent = '☀️';
      }
    } else {
      document.body.classList.remove('dark-theme');
      if (themeToggle) {
        themeToggle.textContent = '🌙';
      }
    }
  }
}

/**
 * 初始化视频控制按钮
 * @param {Object} videoController - 视频控制器实例
 */
function initVideoControls(videoController) {
  const playPauseBtn = document.getElementById('play-pause-btn');
  const rewindBtn = document.getElementById('rewind-btn');
  const fastForwardBtn = document.getElementById('fast-forward-btn');
  const fullscreenBtn = document.getElementById('fullscreen-btn');
  const floatBtn = document.getElementById('float-btn');
  
  if (playPauseBtn) {
    playPauseBtn.addEventListener('click', () => {
      videoController.togglePlayPause();
    });
  }
  
  if (rewindBtn) {
    rewindBtn.addEventListener('click', () => {
      videoController.rewind(10);
    });
  }
  
  if (fastForwardBtn) {
    fastForwardBtn.addEventListener('click', () => {
      videoController.fastForward(10);
    });
  }
  
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', () => {
      videoController.toggleFullscreen();
    });
  }
  
  if (floatBtn) {
    floatBtn.addEventListener('click', () => {
      videoController.toggleFloatMode();
    });
  }
}

/**
 * 初始化帮助按钮
 * @param {Object} uiManager - UI管理器实例
 */
function initHelpButton(uiManager) {
  const helpBtn = document.getElementById('help-btn');
  
  if (!helpBtn) return;
  
  helpBtn.addEventListener('click', () => {
    uiManager.showHelp();
  });
}

/**
 * 初始化动作库
 */
function initExerciseLibrary() {
  const exerciseSearch = document.getElementById('exercise-search');
  const exerciseList = document.getElementById('exercise-list');
  
  // 获取所有动作
  function getAllExercises() {
    // 直接从动作库中获取所有动作
    return Object.values(exercises);
  }
  
  // 渲染动作库
  function renderExerciseLibrary(searchTerm = '') {
    if (!exerciseList) return;
    
    const allExercises = getAllExercises();
    const filteredExercises = searchTerm
      ? allExercises.filter(exercise => exercise.name.includes(searchTerm))
      : allExercises;
    
    // 清空列表
    exerciseList.innerHTML = '';
    
    // 渲染动作列表
    filteredExercises.forEach(exercise => {
      const li = document.createElement('div');
      li.className = 'exercise-list-item';
      li.textContent = exercise.name;
      
      // 添加点击事件
      li.addEventListener('click', () => {
        showExerciseDetail(exercise);
      });
      
      exerciseList.appendChild(li);
    });
  }
  
  /**
   * 显示动作详情
   * @param {Object} exercise - 动作对象
   */
  function showExerciseDetail(exercise) {
    // 使用模态框显示动作详情
    showExerciseDetailModal(exercise);
  }
  
  /**
   * 初始化动作详情模态框
   */
  function initExerciseDetailModal() {
    const closeExerciseModal = document.getElementById('close-exercise-modal');
    const closeExerciseDetailBtn = document.getElementById('close-exercise-detail-btn');
    const exerciseDetailModal = document.getElementById('exercise-detail-modal');
    
    // 关闭模态框
    function hideExerciseDetailModal() {
      if (exerciseDetailModal) {
        exerciseDetailModal.classList.remove('show');
      }
    }
    
    if (closeExerciseModal) {
      closeExerciseModal.addEventListener('click', hideExerciseDetailModal);
    }
    
    if (closeExerciseDetailBtn) {
      closeExerciseDetailBtn.addEventListener('click', hideExerciseDetailModal);
    }
    
    if (exerciseDetailModal) {
      exerciseDetailModal.addEventListener('click', (e) => {
        if (e.target === exerciseDetailModal) {
          hideExerciseDetailModal();
        }
      });
    }
  }
  
  /**
   * 显示动作详情模态框
   * @param {Object} exercise - 动作对象
   */
  function showExerciseDetailModal(exercise) {
    const modal = document.getElementById('exercise-detail-modal');
    const modalExerciseName = document.getElementById('modal-exercise-name');
    const modalExercisePurpose = document.getElementById('modal-exercise-purpose');
    const modalExerciseTips = document.getElementById('modal-exercise-tips');
    const modalExerciseMistakes = document.getElementById('modal-exercise-mistakes');
    const modalExerciseVideo = document.getElementById('modal-exercise-video');
    const modalVideoPlaceholder = document.getElementById('modal-video-placeholder');
    
    if (!modal) return;
    
    // 更新模态框内容
    if (modalExerciseName) modalExerciseName.textContent = exercise.name;
    if (modalExercisePurpose) modalExercisePurpose.textContent = exercise.purpose;
    if (modalExerciseTips) modalExerciseTips.textContent = exercise.tips;
    if (modalExerciseMistakes) modalExerciseMistakes.textContent = exercise.mistakes || '暂无常见错误信息';
    
    // 处理视频
    if (modalExerciseVideo && modalVideoPlaceholder) {
      if (exercise.videoPath) {
        modalExerciseVideo.src = exercise.videoPath;
        modalExerciseVideo.load();
        modalExerciseVideo.style.display = 'block';
        modalVideoPlaceholder.style.display = 'none';
      } else {
        modalExerciseVideo.style.display = 'none';
        modalVideoPlaceholder.style.display = 'flex';
      }
    }
    
    // 显示模态框
    modal.classList.add('show');
  }
  
  // 添加搜索事件
  if (exerciseSearch) {
    exerciseSearch.addEventListener('input', (e) => {
      const searchTerm = e.target.value;
      renderExerciseLibrary(searchTerm);
    });
  }
  
  // 初始渲染
  renderExerciseLibrary();
}

// 全局错误处理
window.addEventListener('error', (e) => {
  console.error('应用错误:', e.error);
  
  // 直接显示通知
  const notification = document.getElementById('notification');
  if (notification) {
    notification.textContent = '应用发生错误，请刷新页面重试';
    notification.className = 'notification error';
    notification.classList.add('show');
    
    setTimeout(() => {
      notification.classList.remove('show');
    }, 3000);
  }
});

// showNotification 函数已移至 UIManager 类中