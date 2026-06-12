"""
数据源工厂：按需加载适配器，避免无外网 / 缺依赖时整体启动失败。

`ADAPTERS` 存的是模块路径字符串，只在真正 `_create` 时才 import。
因此当某个外部数据源（tushare/baostock/akshare）未装包时，
只要未被调用，整个子系统不会崩；只有实际请求那个数据源的 `create 才报错。
"""
from __future__ import annotations

import logging
from typing import List, Type

from app.core.params.service import ParameterService
from app.core.data.market.base import DataSource

logger = logging.getLogger(__name__)


class DataSourceFactory:
    # 模块路径 -> class name；按需导入，避免缺失包整体失败
    ADAPTERS: dict[str, str] = {
        "tushare": "app.core.data.market.tushare_adapter:TushareAdapter",
        "akshare": "app.core.data.market.akshare_adapter:AKShareAdapter",
        "baostock": "app.core.data.market.baostock_adapter:BaoStockAdapter",
        "mock": "app.core.data.market.mock_adapter:MockMarketAdapter",
    }

    def __init__(self, param_service: ParameterService):
        self.param_service = param_service

    def create_primary(self) -> DataSource:
        source_name = self.param_service.get("data.primary_source", "mock")
        logger.info(f"primary source_name: {source_name}")
        return self._create(source_name)

    def create_backups(self) -> List[DataSource]:
        names = self.param_service.get("data.backup_sources", [])
        result: List[DataSource] = []
        for name in names:
            if name not in self.ADAPTERS:
                logger.warning(f"跳过未知的备用数据源: {name}")
                continue
            try:
                result.append(self._create(name))
            except Exception as e:
                logger.warning(f"加载备用数据源 {name} 失败: {e}")
        return result

    def _create(self, name: str) -> DataSource:
        path = self.ADAPTERS.get(name)
        if not path:
            raise ValueError(f"未知数据源: {name}，可选: {list(self.ADAPTERS.keys())}")
        cls = self._load_class(path)
        return cls(self.param_service)

    @staticmethod
    def _load_class(dotted_path: str) -> Type[DataSource]:
        """把 `pkg.mod:ClassName` 解析为实际的类对象。"""
        module_path, class_name = dotted_path.split(":")
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
