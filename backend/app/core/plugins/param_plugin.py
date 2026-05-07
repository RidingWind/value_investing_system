import redis
from fastapi import FastAPI
from app.core.plugins.base import SubsystemPlugin
from app.core.params.redis_impl import RedisParameterService
from app.core.params.definitions import register_all_parameters
from app.core.params.service import ParameterService

class ParamPlugin(SubsystemPlugin):
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:
        redis_client = redis.Redis(
            host=infra_config['redis']['host'],
            port=infra_config['redis']['port'],
            decode_responses=True
        )
        param_svc = RedisParameterService(redis_client)
        register_all_parameters(param_svc)
        app.state.param_service = param_svc

    def register_routers(self, app: FastAPI) -> None:
        from app.api.v1 import params, audit
        app.include_router(params.router, prefix="/api/v1")
        app.include_router(audit.router, prefix="/api/v1")