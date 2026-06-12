import logging
import threading
from fastapi import FastAPI
from app.core.config import get_database_url
from app.core.plugins.base import SubsystemPlugin
from app.core.params.service import ParameterService
from app.core.data.market.factory import DataSourceFactory
from app.core.data.market.fallback import FallbackDataSource
from app.core.data.market.storage import DataStorage
from app.core.data.market.scheduler import DataScheduler

logger = logging.getLogger(__name__)


class MarketPlugin(SubsystemPlugin):
    def init_app(self, app: FastAPI, infra_config: dict, param_service: ParameterService = None) -> None:
        database_url = get_database_url()

        factory = DataSourceFactory(param_service)
        primary = factory.create_primary()
        backups = factory.create_backups()
        data_source = FallbackDataSource(primary, backups, param_service)
        app.state.data_source = data_source

        data_storage = DataStorage(database_url)
        app.state.data_storage = data_storage

        scheduler = DataScheduler(data_source, param_service, database_url)
        scheduler.start()
        app.state.data_scheduler = scheduler

        # 首次启动：在后台线程拉取少量代表性股票，避免阻塞启动
        last_date = data_storage.get_last_trade_date()
        if last_date is None:
            logger.info("数据库无行情数据，将在后台拉取少量代表性股票近30天数据...")

            def _warmup():
                try:
                    sample_symbols = [
                        "600519.SH", "000001.SZ", "000858.SZ", "601318.SH", "600036.SH",
                    ]
                    try:
                        all_symbols = data_source.get_all_symbols() or []
                        if all_symbols:
                            # 仅保留我们认识的代码，避免格式问题
                            existing = set(sample_symbols)
                            for s in all_symbols[:20]:
                                if len(existing) >= 10:
                                    break
                                existing.add(s)
                            sample_symbols = list(existing)[:10]
                    except Exception as e:
                        logger.warning(f"获取全量股票列表失败，使用默认样例: {e}")

                    scheduler.do_market_fetch(sample_symbols, None, None, "warmup")
                    logger.info("代表性股票行情预热完成")
                except Exception as e:
                    logger.warning(f"代表性股票行情预热失败: {e}")

            threading.Thread(target=_warmup, daemon=True).start()

    def register_routers(self, app: FastAPI) -> None:
        from app.api.v1 import market
        app.include_router(market.router, prefix="/api/v1")