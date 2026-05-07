from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Optional
import pandas as pd

from app.core.params.service import ParameterService

# 标准字段映射，各适配器需要将原始数据转换为这些字段
STANDARD_COLUMNS = ['symbol', 'open', 'high', 'low', 'close', 'volume', 'amount', 'trade_date']


class DataSource(ABC):
    """数据源抽象基类"""
    def __init__(self, param_service: ParameterService):
        self.param_service = param_service

    @abstractmethod
    def fetch_daily_quote(self, symbols: List[str], trade_date: Optional[date] = None) -> pd.DataFrame:
        """获取日线行情，返回标准字段 DataFrame"""
        pass

    @abstractmethod
    def get_all_symbols(self) -> List[str]:
        """获取全部股票代码列表"""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """检查数据源是否可用"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """返回数据源名称"""
        pass