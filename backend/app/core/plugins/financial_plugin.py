"""财务数据采集子系统插件"""
import logging

from fastapi import FastAPI
from app.core.config import get_database_url
from app.core.params.service import ParameterService
from app.core.plugins.base import SubsystemPlugin
from app.core.data.financial.storage import FinancialStorage
from app.core.data.financial.dynamic_adapter import DynamicFinancialAdapter
from app.core.data.financial.scheduler import FinancialScheduler
from app.core.data.financial.seed import seed_preset_data

logger = logging.getLogger(__name__)

class FinancialPlugin(SubsystemPlugin):
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:
        database_url = get_database_url()
        storage = FinancialStorage(database_url)
        app.state.financial_storage = storage

        # 初始化预设数据（仅当api_def表为空时）
        if not storage.has_api_defs():
            seed_preset_data(storage)

        adapter = DynamicFinancialAdapter(storage, param_service)
        app.state.financial_adapter = adapter

        scheduler = FinancialScheduler(adapter, storage)
        app.state.financial_scheduler = scheduler

    def register_routers(self, app):
        from app.api.v1 import financial, financial_config
        app.include_router(financial.router, prefix="/api/v1")
        app.include_router(financial_config.router, prefix="/api/v1")