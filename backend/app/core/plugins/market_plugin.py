import threading
from fastapi import FastAPI
from app.core.config import get_database_url
from app.core.plugins.base import SubsystemPlugin
from app.core.params.service import ParameterService
from app.core.data.market.factory import DataSourceFactory
from app.core.data.market.fallback import FallbackDataSource
from app.core.data.market.storage import DataStorage
from app.core.data.market.scheduler import DataScheduler

class MarketPlugin(SubsystemPlugin):
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:        # 处理数据库 URL 绝对路径（兼容 SQLite 相对路径）
        database_url = get_database_url()

        # 创建数据源工厂，生成主/备数据源
        factory = DataSourceFactory(param_service)
        primary = factory.create_primary()
        backups = factory.create_backups()
        data_source = FallbackDataSource(primary, backups)
        app.state.data_source = data_source

        # 初始化行情存储与调度器
        data_storage = DataStorage(database_url)
        app.state.data_storage = data_storage

        scheduler = DataScheduler(data_source, param_service, database_url)
        scheduler.start()
        app.state.data_scheduler = scheduler

        # 首次启动自动拉取近30天历史数据（若数据库为空）
        last_date = data_storage.get_last_trade_date()
        if last_date is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("数据库无行情数据，开始拉取近30天历史数据...")
            scheduler.incremental_fetch(days_back=30)

    def register_routers(self, app: FastAPI) -> None:
        from app.api.v1 import market
        app.include_router(market.router, prefix="/api/v1")