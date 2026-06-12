"""
纯内存实现的 ParameterService —— 当 Redis 不可用时的回退。

注意：进程重启后所有值回到默认；不支持跨进程的热更新（只有同一进程内
有效）。对 E2E 测试 / 单机开发环境已足够。
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List

from .service import ParameterDef, ParameterService


class InMemoryParameterService(ParameterService):
    def __init__(self) -> None:
        self._definitions: Dict[str, ParameterDef] = {}
        self._values: Dict[str, Any] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # -------- register / get / set --------
    def register(self, param_def: ParameterDef) -> None:
        self._definitions[param_def.key] = param_def
        if param_def.key not in self._values:
            self._values[param_def.key] = param_def.default_value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._values:
            return self._values[key]
        if key in self._definitions:
            return self._definitions[key].default_value
        return default

    def set(self, key: str, value: Any, operator: str = "system") -> bool:
        if key not in self._definitions:
            return False
        param_def = self._definitions[key]
        if not isinstance(value, param_def.value_type):
            raise TypeError(
                f"参数 {key} 类型错误，期望 {param_def.value_type.__name__}，"
                f"实际 {type(value).__name__}"
            )
        if param_def.validator is not None and not param_def.validator(value):
            raise ValueError(f"参数 {key} 校验失败，值: {value}")

        self._values[key] = value
        self._audit_log.append({
            "key": key,
            "value": value,
            "operator": operator,
            "timestamp": time.time(),
        })
        for cb in self._subscribers.get(key, []):
            try:
                cb(key, value)
            except Exception:
                pass
        return True

    # -------- subscribe / history --------
    def subscribe(self, keys: List[str], callback: Callable) -> None:
        for key in keys:
            self._subscribers.setdefault(key, []).append(callback)

    def get_history(self, key: str, limit: int = 50) -> List[Dict]:
        return [entry for entry in self._audit_log[-limit:] if entry.get("key") == key]

    def list_all_audit_logs(self) -> List[Dict]:
        # 倒序：最新的在前
        return list(reversed(self._audit_log))

    # -------- 额外：让 API 层能列出参数 --------
    def list_definitions(self) -> List[ParameterDef]:
        return list(self._definitions.values())
