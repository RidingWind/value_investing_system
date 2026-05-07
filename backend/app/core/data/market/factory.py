from typing import List
from app.core.params.service import ParameterService
from .base import DataSource
from .tushare_adapter import TushareAdapter
from .akshare_adapter import AKShareAdapter
from .baostock_adapter import BaoStockAdapter

class DataSourceFactory:
    ADAPTERS = {
        "tushare": TushareAdapter,
        "akshare": AKShareAdapter,
        "baostock": BaoStockAdapter,
    }

    def __init__(self, param_service: ParameterService):
        self.param_service = param_service

    def create_primary(self) -> DataSource:
        source_name = self.param_service.get("data.primary_source", "akshare")
        return self._create(source_name)

    def create_backups(self) -> List[DataSource]:
        names = self.param_service.get("data.backup_sources", [])
        return [self._create(name) for name in names]

    def _create(self, name: str) -> DataSource:
        adapter_class = self.ADAPTERS.get(name)
        if not adapter_class:
            raise ValueError(f"未知数据源: {name}")
        return adapter_class(self.param_service)