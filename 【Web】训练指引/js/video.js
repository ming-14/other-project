/**
 * 视频播放控制模块
 * 负责处理视频的加载、播放、暂停、快进、快退、全屏等操作
 */

class VideoController {
  /**
   * 构造函数
   * @param {string} videoElementId - 视频元素ID
   * @param {string} placeholderElementId - 视频占位符元素ID
   */
  constructor(videoElementId, placeholderElementId) {
    this.videoElement = document.getElementById(videoElementId);
    this.placeholderElement = document.getElementById(placeholderElementId);
    this.isPlaying = false;
    this.isFullscreen = false;
    this.volume = 0.5;
    this.isFloatMode = false;
    this.floatContainer = document.getElementById('video-float-container');
    this.floatVideoElement = document.getElementById('float-exercise-video');
    this.floatCloseBtn = document.getElementById('video-float-close');
    this.floatResizeHandle = document.getElementById('video-float-resize');
    this.floatHeader = document.querySelector('.video-float-header');
    this.floatModeIndicator = null;
    this.currentVideoElement = null; // 添加currentVideoElement属性
    
    // 拖动相关变量
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    
    // 调整大小相关变量
    this.isResizing = false;
    this.resizeStartX = 0;
    this.resizeStartY = 0;
    this.resizeStartWidth = 0;
    this.resizeStartHeight = 0;
    
    // 初始化视频设置
    this.init();
    this.initFloatWindow();
    this.initEventListeners();
  }

  /**
   * 初始化视频控制器
   */
  init() {
    if (this.videoElement) {
      // 设置默认音量
      this.videoElement.volume = this.volume;
      
      // 监听视频事件
      this.videoElement.addEventListener('play', () => {
        this.isPlaying = true;
      });
      
      this.videoElement.addEventListener('pause', () => {
        this.isPlaying = false;
      });
      
      this.videoElement.addEventListener('ended', () => {
        this.isPlaying = false;
      });
      
      this.videoElement.addEventListener('error', (e) => {
        console.error('视频加载错误:', e);
        this.showPlaceholder();
      });
      
      // 监听全屏变化事件
      document.addEventListener('fullscreenchange', () => {
        this.isFullscreen = !!document.fullscreenElement;
      });
    }
  }

  /**
   * 初始化悬浮窗
   */
  initFloatWindow() {
    // 创建悬浮窗模式指示器
    this.floatModeIndicator = document.createElement('div');
    this.floatModeIndicator.className = 'video-float-mode';
    this.floatModeIndicator.textContent = '悬浮窗模式播放中';
    this.floatModeIndicator.style.display = 'none';
    
    // 将指示器添加到视频容器中
    if (this.videoElement && this.videoElement.parentElement) {
      this.videoElement.parentElement.parentElement.appendChild(this.floatModeIndicator);
    }
  }

  /**
   * 初始化事件监听器
   */
  initEventListeners() {
    // 悬浮窗关闭按钮
    if (this.floatCloseBtn) {
      this.floatCloseBtn.addEventListener('click', () => {
        this.switchToWebMode();
      });
    }
    
    // 悬浮窗拖动 - 鼠标事件
    if (this.floatHeader) {
      this.floatHeader.addEventListener('mousedown', (e) => {
        this.startDrag(e);
      });
      
      // 悬浮窗拖动 - 触摸事件
      this.floatHeader.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        this.startDrag(touch);
        e.preventDefault();
      });
    }
    
    // 悬浮窗大小调整 - 鼠标事件
    if (this.floatResizeHandle) {
      this.floatResizeHandle.addEventListener('mousedown', (e) => {
        this.startResize(e);
      });
      
      // 悬浮窗大小调整 - 触摸事件
      this.floatResizeHandle.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        this.startResize(touch);
        e.preventDefault();
      });
    }
    
    // 全局鼠标事件
    document.addEventListener('mousemove', (e) => {
      this.onMouseMove(e);
    });
    
    document.addEventListener('mouseup', () => {
      this.stopDrag();
      this.stopResize();
    });
    
    // 全局触摸事件
    document.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        this.onMouseMove(touch);
        e.preventDefault();
      }
    });
    
    document.addEventListener('touchend', () => {
      this.stopDrag();
      this.stopResize();
    });
    
    // 窗口大小调整事件
    window.addEventListener('resize', () => {
      this.adjustFloatWindowBounds();
    });
  }

  /**
   * 开始拖动悬浮窗
   * @param {MouseEvent} e - 鼠标事件
   */
  startDrag(e) {
    this.isDragging = true;
    this.dragStartX = e.clientX - this.floatContainer.getBoundingClientRect().left;
    this.dragStartY = e.clientY - this.floatContainer.getBoundingClientRect().top;
    this.floatContainer.style.cursor = 'grabbing';
  }

  /**
   * 停止拖动悬浮窗
   */
  stopDrag() {
    this.isDragging = false;
    if (this.floatContainer) {
      this.floatContainer.style.cursor = 'default';
    }
  }

  /**
   * 开始调整悬浮窗大小
   * @param {MouseEvent} e - 鼠标事件
   */
  startResize(e) {
    this.isResizing = true;
    this.resizeStartX = e.clientX;
    this.resizeStartY = e.clientY;
    this.resizeStartWidth = this.floatContainer.offsetWidth;
    this.resizeStartHeight = this.floatContainer.offsetHeight;
    document.body.style.cursor = 'nwse-resize';
  }

  /**
   * 停止调整悬浮窗大小
   */
  stopResize() {
    this.isResizing = false;
    document.body.style.cursor = 'default';
  }

  /**
   * 调整悬浮窗边界，确保在窗口大小变化时不出界
   */
  adjustFloatWindowBounds() {
    if (!this.floatContainer) return;
    
    // 获取屏幕边界
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const floatWidth = this.floatContainer.offsetWidth;
    const floatHeight = this.floatContainer.offsetHeight;
    
    // 检查并修正位置
    let left = parseInt(this.floatContainer.style.left) || 0;
    let top = parseInt(this.floatContainer.style.top) || 0;
    
    // 边界检查，确保悬浮窗不会超出屏幕
    left = Math.max(0, Math.min(left, screenWidth - floatWidth));
    top = Math.max(0, Math.min(top, screenHeight - floatHeight));
    
    // 更新位置
    this.floatContainer.style.left = `${left}px`;
    this.floatContainer.style.top = `${top}px`;
  }

  /**
   * 鼠标移动事件处理
   * @param {MouseEvent} e - 鼠标事件
   */
  onMouseMove(e) {
    if (this.isDragging && this.floatContainer) {
      // 计算新位置
      let x = e.clientX - this.dragStartX;
      let y = e.clientY - this.dragStartY;
      
      // 获取屏幕边界
      const screenWidth = window.innerWidth;
      const screenHeight = window.innerHeight;
      const floatWidth = this.floatContainer.offsetWidth;
      const floatHeight = this.floatContainer.offsetHeight;
      
      // 边界检查，确保悬浮窗不会超出屏幕
      x = Math.max(0, Math.min(x, screenWidth - floatWidth));
      y = Math.max(0, Math.min(y, screenHeight - floatHeight));
      
      // 更新位置
      this.floatContainer.style.left = `${x}px`;
      this.floatContainer.style.top = `${y}px`;
      this.floatContainer.style.right = 'auto';
    }
    
    if (this.isResizing && this.floatContainer) {
      // 计算新尺寸
      const deltaX = e.clientX - this.resizeStartX;
      const deltaY = e.clientY - this.resizeStartY;
      let newWidth = Math.max(200, this.resizeStartWidth + deltaX);
      let newHeight = Math.max(112, this.resizeStartHeight + deltaY);
      
      // 获取屏幕边界
      const screenWidth = window.innerWidth;
      const screenHeight = window.innerHeight;
      const floatLeft = parseInt(this.floatContainer.style.left) || 0;
      const floatTop = parseInt(this.floatContainer.style.top) || 0;
      
      // 边界检查，确保悬浮窗不会超出屏幕
      newWidth = Math.min(newWidth, screenWidth - floatLeft);
      newHeight = Math.min(newHeight, screenHeight - floatTop);
      
      // 更新尺寸
      this.floatContainer.style.width = `${newWidth}px`;
      this.floatContainer.style.height = `${newHeight}px`;
    }
  }

  /**
   * 切换到悬浮窗模式
   */
  switchToFloatMode() {
    if (!this.videoElement || !this.floatContainer || !this.floatVideoElement) return;
    
    // 保存视频状态
    const currentTime = this.videoElement.currentTime;
    const isPlaying = this.isPlaying;
    const volume = this.videoElement.volume;
    const src = this.videoElement.src;
    
    // 显示悬浮窗
    this.floatContainer.style.display = 'flex';
    
    // 确保悬浮窗初始位置在屏幕内
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const floatWidth = this.floatContainer.offsetWidth;
    const floatHeight = this.floatContainer.offsetHeight;
    
    // 检查并修正位置
    let left = parseInt(this.floatContainer.style.left) || 0;
    let top = parseInt(this.floatContainer.style.top) || 0;
    
    // 边界检查，确保悬浮窗不会超出屏幕
    left = Math.max(0, Math.min(left, screenWidth - floatWidth));
    top = Math.max(0, Math.min(top, screenHeight - floatHeight));
    
    // 更新位置
    this.floatContainer.style.left = `${left}px`;
    this.floatContainer.style.top = `${top}px`;
    
    // 复制视频状态到悬浮窗
    this.floatVideoElement.src = src;
    this.floatVideoElement.currentTime = currentTime;
    this.floatVideoElement.volume = volume;
    
    // 隐藏网页视频
    this.videoElement.style.display = 'none';
    if (this.placeholderElement) {
      this.placeholderElement.style.display = 'none';
    }
    
    // 显示悬浮窗模式提示
    if (this.floatModeIndicator) {
      this.floatModeIndicator.style.display = 'block';
    }
    
    // 恢复播放状态
    if (isPlaying) {
      this.floatVideoElement.play().catch(err => {
        console.error('播放失败:', err);
        this.isPlaying = false;
      });
    }
    
    // 更新状态
    this.isFloatMode = true;
    this.currentVideoElement = this.floatVideoElement;
  }

  /**
   * 切换到网页模式
   */
  switchToWebMode() {
    if (!this.videoElement || !this.floatContainer || !this.floatVideoElement) return;
    
    // 保存视频状态
    const currentTime = this.floatVideoElement.currentTime;
    const isPlaying = !this.floatVideoElement.paused;
    const volume = this.floatVideoElement.volume;
    
    // 隐藏悬浮窗
    this.floatContainer.style.display = 'none';
    
    // 恢复网页视频
    this.videoElement.style.display = 'block';
    if (this.placeholderElement) {
      this.placeholderElement.style.display = 'none';
    }
    
    // 隐藏悬浮窗模式提示
    if (this.floatModeIndicator) {
      this.floatModeIndicator.style.display = 'none';
    }
    
    // 恢复播放状态
    this.videoElement.currentTime = currentTime;
    this.videoElement.volume = volume;
    if (isPlaying) {
      this.videoElement.play().catch(err => {
        console.error('播放失败:', err);
        this.isPlaying = false;
      });
    }
    
    // 更新状态
    this.isFloatMode = false;
    this.currentVideoElement = this.videoElement;
  }

  /**
   * 切换悬浮窗模式
   */
  toggleFloatMode() {
    if (this.isFloatMode) {
      this.switchToWebMode();
    } else {
      this.switchToFloatMode();
    }
  }

  /**
   * 加载视频
   * @param {string} videoPath - 视频文件路径
   */
  loadVideo(videoPath) {
    if (!this.videoElement) return;
    
    // 重置视频状态
    this.videoElement.pause();
    this.videoElement.currentTime = 0;
    
    // 设置视频源
    this.videoElement.src = videoPath;
    
    // 同时更新悬浮窗视频
    if (this.floatVideoElement) {
      this.floatVideoElement.pause();
      this.floatVideoElement.currentTime = 0;
      this.floatVideoElement.src = videoPath;
      this.floatVideoElement.load();
    }
    
    // 尝试加载视频
    this.videoElement.load();
    
    // 监听视频可播放事件
    const canPlayHandler = () => {
      this.hidePlaceholder();
      this.videoElement.removeEventListener('canplay', canPlayHandler);
    };
    
    this.videoElement.addEventListener('canplay', canPlayHandler);
    
    // 监听加载失败事件
    const errorHandler = () => {
      console.error('无法加载视频:', videoPath);
      this.showPlaceholder();
      this.videoElement.removeEventListener('error', errorHandler);
    };
    
    this.videoElement.addEventListener('error', errorHandler);
    
    // 监听悬浮窗视频事件
    if (this.floatVideoElement) {
      this.floatVideoElement.addEventListener('canplay', canPlayHandler);
      this.floatVideoElement.addEventListener('error', errorHandler);
    }
  }

  /**
   * 播放/暂停视频
   */
  togglePlayPause() {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (!currentVideo) return;
    
    if (!currentVideo.paused) {
      currentVideo.pause();
      this.isPlaying = false;
    } else {
      currentVideo.play();
      this.isPlaying = true;
    }
  }

  /**
   * 播放视频
   */
  play() {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (currentVideo && currentVideo.paused) {
      currentVideo.play().catch(err => {
        console.error('播放失败:', err);
        this.isPlaying = false;
      });
      this.isPlaying = true;
    }
  }

  /**
   * 暂停视频
   */
  pause() {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (currentVideo && !currentVideo.paused) {
      currentVideo.pause();
      this.isPlaying = false;
    }
  }

  /**
   * 快进视频
   * @param {number} seconds - 快进秒数，默认为10秒
   */
  fastForward(seconds = 10) {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (!currentVideo) return;
    
    currentVideo.currentTime = Math.min(
      currentVideo.currentTime + seconds,
      currentVideo.duration
    );
  }

  /**
   * 快退视频
   * @param {number} seconds - 快退秒数，默认为10秒
   */
  rewind(seconds = 10) {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (!currentVideo) return;
    
    currentVideo.currentTime = Math.max(currentVideo.currentTime - seconds, 0);
  }

  /**
   * 切换全屏
   */
  toggleFullscreen() {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    if (!currentVideo) return;
    
    if (!this.isFullscreen) {
      // 进入全屏
      if (currentVideo.requestFullscreen) {
        currentVideo.requestFullscreen();
      } else if (currentVideo.mozRequestFullScreen) {
        currentVideo.mozRequestFullScreen();
      } else if (currentVideo.webkitRequestFullscreen) {
        currentVideo.webkitRequestFullscreen();
      } else if (currentVideo.msRequestFullscreen) {
        currentVideo.msRequestFullscreen();
      }
    } else {
      // 退出全屏
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
    }
  }

  /**
   * 设置视频音量
   * @param {number} volume - 音量值（0-1）
   */
  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume));
    
    if (this.videoElement) {
      this.videoElement.volume = this.volume;
    }
    
    if (this.floatVideoElement) {
      this.floatVideoElement.volume = this.volume;
    }
  }

  /**
   * 显示视频占位符
   */
  showPlaceholder() {
    if (this.placeholderElement) {
      this.placeholderElement.style.display = 'flex';
    }
    if (this.videoElement) {
      this.videoElement.style.display = 'none';
    }
  }

  /**
   * 隐藏视频占位符
   */
  hidePlaceholder() {
    if (this.placeholderElement) {
      this.placeholderElement.style.display = 'none';
    }
    if (this.videoElement) {
      this.videoElement.style.display = 'block';
    }
  }

  /**
   * 重置视频控制器
   */
  reset() {
    // 重置网页视频
    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.currentTime = 0;
    }
    
    // 重置悬浮窗视频
    if (this.floatVideoElement) {
      this.floatVideoElement.pause();
      this.floatVideoElement.currentTime = 0;
    }
    
    // 隐藏悬浮窗
    if (this.floatContainer) {
      this.floatContainer.style.display = 'none';
    }
    
    // 恢复网页视频显示
    if (this.videoElement) {
      this.videoElement.style.display = 'block';
    }
    
    // 显示占位符
    this.showPlaceholder();
    
    // 隐藏悬浮窗模式提示
    if (this.floatModeIndicator) {
      this.floatModeIndicator.style.display = 'none';
    }
    
    // 更新状态
    this.isPlaying = false;
    this.isFloatMode = false;
    this.currentVideoElement = this.videoElement;
  }

  /**
   * 获取视频当前状态
   * @returns {Object} 视频状态对象
   */
  getState() {
    const currentVideo = this.isFloatMode ? this.floatVideoElement : this.videoElement;
    return {
      isPlaying: this.isPlaying,
      currentTime: currentVideo ? currentVideo.currentTime : 0,
      duration: currentVideo ? currentVideo.duration : 0,
      volume: this.volume,
      isFullscreen: this.isFullscreen,
      isFloatMode: this.isFloatMode
    };
  }
}

// 导出VideoController类
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VideoController;
}