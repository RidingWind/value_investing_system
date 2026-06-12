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
            start_date: Optional[date] = None,
            end_date: Optional[date] = None):
        """尝试主数据源，失败后依次降级到备份数据源（不做预健康检查，失败即切换）"""
        last_error = None
        for source in [self.primary] + self.backups:
            try:
                df = source.fetch_daily_quote(symbols, start_date, end_date)
                logger.info(f"成功从 {source.get_source_name()} 获取行情")
                return df
            except Exception as e:
                logger.warning(f"数据源 {source.get_source_name()} 获取行情失败: {e}")
                last_error = e
                continue
        raise RuntimeError(f"所有数据源均不可用: {last_error}")

    def get_all_symbols(self):
        for source in [self.primary] + self.backups:
            try:
                return source.get_all_symbols()
            except Exception:
                continue
        return []

    def check_health(self) -> bool:
        """简单的健康检查：任何一个数据源可以被访问就算健康"""
        for source in [self.primary] + list(self.backups):
            try:
                if source.check_health():
                    return True
            except Exception:
                continue
        return False

    def get_source_name(self) -> str:
        return f"fallback(primary={self.primary.get_source_name()})"