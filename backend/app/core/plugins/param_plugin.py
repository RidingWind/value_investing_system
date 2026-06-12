import logging
import redis
from fastapi import FastAPI
from app.core.plugins.base import SubsystemPlugin
from app.core.params.redis_impl import RedisParameterService
from app.core.params.memory_impl import InMemoryParameterService
from app.core.params.definitions import register_all_parameters
from app.core.params.service import ParameterService

logger = logging.getLogger(__name__)


class ParamPlugin(SubsystemPlugin):
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:
        redis_cfg = (infra_config or {}).get("redis", {}) or {}
        host = redis_cfg.get("host", "localhost")
        port = int(redis_cfg.get("port", 6379))

        param_svc: ParameterService
        try:
            redis_client = redis.Redis(host=host, port=port, decode_responses=True,
                                        socket_connect_timeout=2, socket_timeout=2)
            # 做一次真实的命令检查，避免「对象创建成功但连不上」的情况
            redis_client.ping()
            param_svc = RedisParameterService(redis_client)
            logger.info(f"[params] 使用 Redis 参数服务 ({host}:{port})")
        except Exception as e:
            logger.warning(
                f"[params] 无法连接 Redis ({host}:{port}) —— {e}，"
                f"切换为 InMemoryParameterService（进程重启后值回到默认）"
            )
            param_svc = InMemoryParameterService()

        register_all_parameters(param_svc)
        app.state.param_service = param_svc

    def register_routers(self, app: FastAPI) -> None:
        from app.api.v1 import params, audit
        app.include_router(params.router, prefix="/api/v1")
        app.include_router(audit.router, prefix="/api/v1")