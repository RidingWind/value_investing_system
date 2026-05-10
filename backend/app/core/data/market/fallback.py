import logging
from typing import List, Optional
from datetime import date
from .base import DataSource
from app.core.params.service import ParameterService

logger = logging.getLogger(__name__)


class FallbackDataSource(DataSource):
    """多数据源故障转移封装"""
    def __init__(self, primary: DataSource, backups: List[DataSource], param_service: ParameterService):
        super().__init__(param_service)
        self.primary = primary
        self.backups = backups

    def fetch_daily_quote(
            self,
            symbols,
            start_date:Optional[date]=None,
            end_date:Optional[date]=None):
        for source in [self.primary] + self.backups:
            if not source.check_health():
                logger.warning(f"数据源 {source.get_source_name()} 不健康，跳过")
                continue
            try:
                df = source.fetch_daily_quote(symbols, start_date, end_date)
                logger.info(f"成功从 {source.get_source_name()} 获取行情")
                return df
            except Exception as e:
                logger.warning(f"数据源 {source.get_source_name()} 获取行情失败: {e}")
                continue
        raise RuntimeError("所有数据源均不可用")

    def get_all_symbols(self):
        for source in [self.primary] + self.backups:
            if source.check_health():
                try:
                    return source.get_all_symbols()
                except Exception:
                    continue
        raise RuntimeError("无法获取股票列表")

    def check_health(self) -> bool:
        return self.primary.check_health() or any(b.check_health() for b in self.backups)

    def get_source_name(self) -> str:
        return f"fallback(primary={self.primary.get_source_name()})"