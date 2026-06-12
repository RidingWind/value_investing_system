import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from .fallback import FallbackDataSource
from app.core.params.service import ParameterService
from app.core.data.market.storage import DataStorage
#from decimal import Decimal, InvalidOperation
logger = logging.getLogger(__name__)

class DataScheduler:
    MAX_LOG_ENTRIES = 50

    def __init__(self, data_source: FallbackDataSource, param_service: ParameterService, database_url: str):
        self.data_source = data_source
        self.param_service = param_service
        self.storage = DataStorage(database_url)   # 关键添加
        self.scheduler = BackgroundScheduler()
        self.last_market_fetch = None
        self._fetch_logs: List[Dict] = []

    def start(self):
        market_cron = self.param_service.get("data.market.cron", "30 15 * * 1-5")
        self.scheduler.add_job(
            func=self._scheduled_market_fetch,
            trigger='cron',
            **self._parse_cron(market_cron)
        )
        self.scheduler.start()
        logger.info("数据调度器已启动")

    def _scheduled_market_fetch(self):
        """定时任务入口"""
        symbols = self.data_source.get_all_symbols()
        self.do_market_fetch(symbols, None, None, triggered_by="scheduled")

    # def do_market_fetch(self, trade_date, symbols, triggered_by: str):
    def do_market_fetch(
            self,
            symbols: List[str],
            start:Optional[date],
            end:Optional[date],
            triggered_by: str
    ):
        start_date = start if start is not None else date.today()
        end_date = end if end is not None else start_date
        log_entry = {
            "type": "market",
            "trigger": triggered_by,
            "start_date": start_date,
            "end_date": end_date,
            "status": "running",
            "record_count": 0,
            "store_count": 0,
            "error": None
        }
        try:
            df = self.data_source.fetch_daily_quote(symbols, start_date, end_date)
            logger.info(f"准备存储 {len(df)} 行数据，样例：\n{df.head(3)}")
            record_count = len(df)

            # 写入数据库
            if record_count > 0:
                source_name = self.data_source.primary.get_source_name()
                stored_count = self.storage.save_batch(df, source_name)
                log_entry["stored_count"] = stored_count
            else:
                log_entry["stored_count"] = 0

            self.last_market_fetch = date.today()
            log_entry["status"] = "success"
            log_entry["record_count"] = record_count
            logger.info(f"行情采集成功，获取 {record_count} 条，入库 {log_entry['stored_count']} 条")
            return df
        except Exception as e:
            log_entry["status"] = "error"
            log_entry["error"] = str(e)
            logger.error(f"行情采集失败: {e}")
            raise
        finally:
            log_entry["end_time"] = datetime.now().isoformat()
            # 插入到列表头部
            self._fetch_logs.insert(0, log_entry)
            # 控制长度
            if len(self._fetch_logs) > self.MAX_LOG_ENTRIES:
                self._fetch_logs = self._fetch_logs[:self.MAX_LOG_ENTRIES]

    def incremental_fetch(self, days_back: int = 30):
        """增量拉取最近 N 天的历史数据（用于首次启动时补充历史）"""
        symbols = self.data_source.get_all_symbols()
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        df = self.do_market_fetch(symbols, start_date, end_date,"incremental")
        logger.info(f"增量采集完成，共获取 {len(df)} 条历史数据")
        return df

    def get_recent_logs(self, limit: int = 20) -> List[Dict]:
        """返回最近的采集日志"""
        return self._fetch_logs[:limit]

    @staticmethod
    def _parse_cron(cron_expr: str):
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"非法 cron 表达式: {cron_expr}")
        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }