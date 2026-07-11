/**
 * 应用主入口文件
 * 负责初始化所有模块和处理页面的主要逻辑
 */

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', () => {
  // 初始化应用
  initApp();
});

/**
 * 初始化应用
 */
function initApp() {
  // 初始化UI管理器
  const uiManager = new UIManager();
  
  // 初始化计划选择
  initPlanSelection(uiManager);
  
  // 初始化主题切换
  initThemeToggle();
  
  // 初始化帮助按钮
  initHelpButton(uiManager);
  
  // 初始化动作库
  initExerciseLibrary();
  
  // 初始化动作详情模态框
  initExerciseDetailModal();
  
  console.log('应用初始化完成');
}

/**
 * 初始化计划选择
 * @param {Object} uiManager - UI管理器实例
 */
function initPlanSelection(uiManager) {
  const planList = document.getElementById('plan-list');
  const planDetailModal = document.getElementById('plan-detail-modal');
  const closeModal = document.getElementById('close-modal');
  const cancelPlanBtn = document.getElementById('cancel-plan-btn');
  const startPlanBtn = document.getElementById('start-plan-btn');
  const filterBtns = document.querySelectorAll('.filter-btn');
  
  // 当前选中的计划
  let currentSelectedPlan = null;
  
  // 渲染计划列表
  function renderPlanList(filter = 'all') {
    if (!planList) return;
    
    planList.innerHTML = '';
    
    // 遍历训练计划
    Object.values(trainingPlans).forEach(plan => {
      // 应用筛选
      if (filter !== 'all' && plan.category !== filter) {
        return;
      }
      
      // 创建计划卡片
      const planCard = document.createElement('div');
      planCard.className = 'plan-card';
      planCard.dataset.planId = plan.id;
      
      // 确定计划类别名称
      const categoryNames = {
        'regular': '常规训练',
        'post-run': '跑后训练',
        'pre-run': '跑前热身',
        'knee': '膝关节保护'
      };
      
      planCard.innerHTML = `
        <div class="plan-card__header">
          <div>
            <h3 class="plan-card__title">${plan.name}</h3>
            <span class="plan-card__category">${categoryNames[plan.category]}</span>
          </div>
        </div>
        <p class="plan-card__description">${plan.description}</p>
        <div class="plan-card__details">
          <div class="plan-card__detail">
            <span class="plan-card__detail-value">${plan.duration}</span>
            <span class="plan-card__detail-label">分钟</span>
          </div>
          <div class="plan-card__detail">
            <span class="plan-card__detail-value">${plan.difficulty}</span>
            <span class="plan-card__detail-label">难度</span>
          </div>
          <div class="plan-card__detail">
            <span class="plan-card__detail-value">${getTotalExercises(plan)}</span>
            <span class="plan-card__detail-label">动作</span>
          </div>
        </div>
        <div class="plan-card__footer">
          <div class="plan-card__duration">
            ⏱️ ${plan.duration}分钟
          </div>
          <button class="btn btn--primary plan-card__btn" data-plan-id="${plan.id}">查看详情</button>
        </div>
      `;
      
      // 添加到计划列表
      planList.appendChild(planCard);
    });
    
    // 添加计划卡片点击事件
    const planCards = document.querySelectorAll('.plan-card');
    planCards.forEach(card => {
      card.addEventListener('click', (e) => {
        // 检查是否点击了按钮
        if (e.target.tagName === 'BUTTON') {
          return;
        }
        
        // 获取计划ID
        const planId = card.dataset.planId;
        showPlanDetail(planId);
      });
    });
    
    // 添加查看详情按钮事件
    const viewDetailBtns = document.querySelectorAll('.plan-card__btn');
    viewDetailBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const planId = btn.dataset.planId;
        showPlanDetail(planId);
      });
    });
  }
  
  /**
   * 显示计划详情
   * @param {string} planId - 计划ID
   */
  function showPlanDetail(planId) {
    // 查找计划
    const plan = Object.values(trainingPlans).find(p => p.id === planId);
    if (!plan) return;
    
    currentSelectedPlan = plan;
    
    // 更新模态框内容
    const modalPlanName = document.getElementById('modal-plan-name');
    const modalPlanDescription = document.getElementById('modal-plan-description');
    const modalPlanDuration = document.getElementById('modal-plan-duration');
    const modalPlanDifficulty = document.getElementById('modal-plan-difficulty');
    const modalPlanStructure = document.getElementById('modal-plan-structure');
    
    if (modalPlanName) modalPlanName.textContent = plan.name;
    if (modalPlanDescription) modalPlanDescription.textContent = plan.description;
    if (modalPlanDuration) modalPlanDuration.textContent = `${plan.duration}分钟`;
    if (modalPlanDifficulty) modalPlanDifficulty.textContent = plan.difficulty;
    
    // 渲染计划结构
    if (modalPlanStructure) {
      modalPlanStructure.innerHTML = '';
      
      plan.segments.forEach(segment => {
        const li = document.createElement('li');
        li.innerHTML = `
          <span>${segment.name}</span>
          <span>${segment.duration}分钟</span>
        `;
        modalPlanStructure.appendChild(li);
      });
    }
    
    // 显示模态框
    if (planDetailModal) {
      planDetailModal.classList.add('show');
    }
  }
  
  /**
   * 隐藏计划详情模态框
   */
  function hidePlanDetailModal() {
    if (planDetailModal) {
      planDetailModal.classList.remove('show');
    }
    currentSelectedPlan = null;
  }
  
  // 关闭模态框事件
  if (closeModal) {
    closeModal.addEventListener('click', hidePlanDetailModal);
  }
  
  // 取消按钮事件
  if (cancelPlanBtn) {
    cancelPlanBtn.addEventListener('click', hidePlanDetailModal);
  }
  
  // 开始训练按钮事件
  if (startPlanBtn) {
    startPlanBtn.addEventListener('click', () => {
      if (currentSelectedPlan) {
        // 先保存计划ID，再隐藏模态框
        const planId = currentSelectedPlan.id;
        
        // 隐藏模态框
        hidePlanDetailModal();
        
        // 跳转到训练页面，传递计划ID作为URL参数
        window.location.href = `training.html?plan=${planId}`;
      }
    });
  }
  
  // 点击模态框外部关闭
  if (planDetailModal) {
    planDetailModal.addEventListener('click', (e) => {
      if (e.target === planDetailModal) {
        hidePlanDetailModal();
      }
    });
  }
  
  // 筛选按钮事件
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // 移除所有激活状态
      filterBtns.forEach(b => b.classList.remove('filter-btn--active'));
      
      // 添加当前按钮激活状态
      btn.classList.add('filter-btn--active');
      
      // 获取筛选条件
      const filter = btn.dataset.filter;
      
      // 重新渲染计划列表
      renderPlanList(filter);
    });
  });
  
  // 初始渲染计划列表
  renderPlanList();
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
        showExerciseDetailModal(exercise);
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

/**
 * 获取计划的总动作数
 * @param {Object} plan - 训练计划对象
 * @returns {number} 总动作数
 */
function getTotalExercises(plan) {
  if (!plan || !plan.segments) return 0;
  
  return plan.segments.reduce((total, segment) => {
    return total + segment.exercises.length;
  }, 0);
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

// 全局错误处理
window.addEventListener('error', (e) => {
  console.error('应用错误:', e.error);
  
  // 直接显示通知，因为UIManager可能还未初始化
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
