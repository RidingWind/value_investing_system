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


class RedisParameterService(ParameterService):
    """基于 Redis 的参数服务实现，支持热加载和变更订阅"""

    def __init__(
        self,
        redis_client: redis.Redis,
        namespace: str = "params",
        audit_log_key: str = "params:audit",
    ):
        self.redis = redis_client
        self.namespace = namespace
        self.audit_log_key = audit_log_key

        self._local_cache: Dict[str, Any] = {}
        self._definitions: Dict[str, ParameterDef] = {}
        self._subscribers: Dict[str, List[Callable]] = {}

        self._pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(f"{self.namespace}:events")

        self._listener_thread = threading.Thread(target=self._listen, daemon=True)
        self._listener_thread.start()

    def register(self, param_def: ParameterDef) -> None:
        self._definitions[param_def.key] = param_def

        stored = self.redis.hget(self._values_key(), param_def.key)
        if stored is not None:
            value = json.loads(stored)
        else:
            value = param_def.default_value
            self._persist(param_def.key, value)

        if param_def.hot_reloadable:
            self._local_cache[param_def.key] = value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._local_cache:
            return self._local_cache[key]

        stored = self.redis.hget(self._values_key(), key)
        if stored is not None:
            value = json.loads(stored)
            if key in self._definitions and self._definitions[key].hot_reloadable:
                self._local_cache[key] = value
            return value

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

        self._persist(key, value)
        self._log_audit(key, value, operator)

        event = {
            "key": key,
            "value": value,
            "operator": operator,
            "timestamp": time.time(),
        }
        self.redis.publish(f"{self.namespace}:events", json.dumps(event))

        return True

    def subscribe(self, keys: List[str], callback: Callable) -> None:
        for key in keys:
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(callback)

    def get_history(self, key: str, limit: int = 50) -> List[Dict]:
        logs = self.redis.lrange(self.audit_log_key, -limit, -1)
        history = []
        for log in logs:
            entry = json.loads(log)
            if entry.get("key") == key:
                history.append(entry)
        return history

    def _values_key(self) -> str:
        return f"{self.namespace}:values"

    def _persist(self, key: str, value: Any) -> None:
        self.redis.hset(self._values_key(), key, json.dumps(value))
        if key in self._definitions and self._definitions[key].hot_reloadable:
            self._local_cache[key] = value

    def _log_audit(self, key: str, value: Any, operator: str) -> None:
        log_entry = {
            "key": key,
            "value": value,
            "operator": operator,
            "timestamp": time.time(),
        }
        self.redis.rpush(self.audit_log_key, json.dumps(log_entry))

    def _listen(self) -> None:
        for message in self._pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                key = data["key"]
                new_value = data["value"]

                if key in self._definitions and self._definitions[key].hot_reloadable:
                    self._local_cache[key] = new_value

                if key in self._subscribers:
                    for callback in self._subscribers[key]:
                        try:
                            callback(key, new_value)
                        except Exception as e:
                            print(f"参数变更回调执行失败 key={key}: {e}")

            except Exception as e:
                print(f"处理参数变更消息失败: {e}")