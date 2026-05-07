from abc import ABC, abstractmethod
from fastapi import FastAPI
from app.core.params.service import ParameterService

class SubsystemPlugin(ABC):
    @abstractmethod
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:
        """初始化子系统"""
        pass

    @abstractmethod
    def register_routers(self, app: FastAPI) -> None:
        """注册路由"""
        pass

