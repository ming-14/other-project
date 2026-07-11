"""!
@file core/lifecycle.py
@brief 生命周期接口与混合基类

定义所有可初始化/销毁组件的统一生命周期协议，
以及提供默认实现的LifecycleMixin。
"""

from abc import ABC, abstractmethod
from core import log_manager

_logger = log_manager.get_logger('core.lifecycle')


class Lifecycle(ABC):
    """!@brief 生命周期协议

    所有需要初始化/销毁的组件必须实现此接口。
    生命周期顺序：create -> startup -> [running] -> shutdown -> destroy
    """

    @abstractmethod
    def on_create(self) -> None:
        """!@brief 创建阶段：分配资源、注册依赖"""
        ...

    @abstractmethod
    def on_startup(self) -> None:
        """!@brief 启动阶段：开始运行、连接外部系统"""
        ...

    @abstractmethod
    def on_shutdown(self) -> None:
        """!@brief 关闭阶段：停止运行、断开连接"""
        ...

    @abstractmethod
    def on_destroy(self) -> None:
        """!@brief 销毁阶段：释放资源、取消注册"""
        ...


class LifecycleMixin(Lifecycle):
    """!@brief 生命周期混合基类

    提供默认的空实现，子类可选择性覆盖需要的阶段。
    """

    def on_create(self) -> None:
        pass

    def on_startup(self) -> None:
        pass

    def on_shutdown(self) -> None:
        pass

    def on_destroy(self) -> None:
        pass


class Updatable(ABC):
    """!@brief 可更新协议

    每帧被调用的组件实现此接口。
    """

    @abstractmethod
    def on_update(self, delta_time: float) -> None:
        """!@brief 每帧更新

        @param delta_time 距上一帧的秒数
        """
        ...


class Renderable(ABC):
    """!@brief 可渲染协议

    需要参与渲染管线的组件实现此接口。
    """

    @abstractmethod
    def on_render(self, context: dict) -> None:
        """!@brief 渲染回调

        @param context 渲染上下文，包含buffer/player/hits等
        """
        ...


class Tickable(ABC):
    """!@brief 固定时间步更新协议

    需要以固定频率更新的组件（如物理模拟）实现此接口。
    """

    @abstractmethod
    def on_fixed_update(self, fixed_delta: float) -> None:
        """!@brief 固定时间步更新

        @param fixed_delta 固定时间步长（秒）
        """
        ...


class Initializable(ABC):
    """!@brief 可初始化协议（轻量级，仅init/destroy）"""

    @abstractmethod
    def initialize(self) -> None:
        ...

    @abstractmethod
    def dispose(self) -> None:
        ...
