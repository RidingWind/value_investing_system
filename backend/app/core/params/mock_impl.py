"""
Redis 参数服务实现
支持参数热更新、发布订阅、审计日志
"""
import json
import threading
import time
from typing import Any, Dict, List, Callable, Optional

import redis

from .service import ParameterService, ParameterDef

class MockParameterService(ParameterService):
    def __init__(self):
        self._definitions = {}
        self._values = {}
        self._history = []
    def register(self, param_def: ParameterDef):
        self._definitions[param_def.key] = param_def
        if param_def.key not in self._values:
            self._values[param_def.key] = param_def.default_value
    def get(self, key: str, default=None):
        return self._values.get(key, default)
    def set(self, key: str, value, operator="system"):
        if key not in self._definitions: return False
        param_def = self._definitions[key]
        if not isinstance(value, param_def.value_type): raise TypeError
        if param_def.validator and not param_def.validator(value): raise ValueError
        self._values[key] = value
        self._history.append({"key":key,"value":value,"operator":operator,"timestamp":time.time()})
        return True
    def subscribe(self, keys, callback): pass
    def get_history(self, key, limit=50):
        return [e for e in self._history if e["key"]==key][-limit:]