from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Callable, Optional, Dict


class ParamScope(Enum):
    BUSINESS = "business"
    TECHNICAL = "technical"


@dataclass
class ParameterDef:
    key: str
    scope: ParamScope
    default_value: Any
    value_type: type
    description: str = ""
    validator: Optional[Callable] = None
    hot_reloadable: bool = True


class ParameterService(ABC):
    """参数服务抽象接口"""

    @abstractmethod
    def register(self, param_def: ParameterDef) -> None:
        """注册参数定义（系统启动时调用）"""
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取参数当前值（优先从本地热缓存读取）"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, operator: str = "system") -> bool:
        """更新参数值，触发验证、持久化、发布变更事件"""
        pass

    @abstractmethod
    def subscribe(self, keys: List[str], callback: Callable) -> None:
        """订阅参数变更，当参数更新时回调"""
        pass

    @abstractmethod
    def get_history(self, key: str, limit: int = 50) -> List[Dict]:
        """获取参数的变更历史（最近 N 条）"""
        pass