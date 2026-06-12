import pandas as pd
from datetime import date, timedelta
from typing import List, Optional
import tushare as ts

from .base import DataSource, STANDARD_COLUMNS
from app.core.params.service import ParameterService


class TushareAdapter(DataSource):
    def __init__(self, param_service: ParameterService):
        super().__init__(param_service)
        token = self.param_service.get("data.tushare.token", "")
        ts.set_token(token)
        self.pro = ts.pro_api()
        self.source_name = "tushare"
        self._stock_basic_available = None  # 缓存权限检测结果

    def fetch_daily_quote(
            self,
            symbols: List[str],
            start_date: Optional[date] = None,
            end_date: Optional[date] = None
    ) -> pd.DataFrame:
        # 将 symbols 转换为 ts_code 列表（若已带后缀则直接使用）
        tscodes = [s if '.' in s else self._symbol_to_tscode(s) for s in symbols]

        # 处理默认值
        sd = start_date if start_date is not None else date.today()
        ed = end_date if end_date is not None else sd
        start_str = sd.strftime('%Y%m%d')

        df_accum = pd.DataFrame()
        # 调用 daily 接口，指定前复权
        while sd <= ed:
            df = self.pro.daily(ts_code=','.join(tscodes), trade_date=start_str, adj='qfq')
            if df is None or df.empty:
                continue

            # 字段映射
            df = df.rename(columns={
                'ts_code': 'symbol',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
                'amount': 'amount'
            })
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
            # 添加复权因子（tushare 的 daily 接口不直接提供，暂设为1.0）
            df['adj_factor'] = 1.0
            df['source'] = self.source_name
            # 保持标准列顺序
            df = df[STANDARD_COLUMNS + ['adj_factor'] + ['source']]
            sd = sd + timedelta(days=1)
            start_str = sd.strftime('%Y%m%d')
            df_accum = df_accum.append(df, ignore_index=True)
        return df_accum

    def get_all_symbols(self) -> List[str]:
        """
        尝试获取股票列表。
        - 积分 >= 2000：正常调用 stock_basic
        - 积分不足：返回空列表（此时应使用备用数据源）
        """
        # 首次调用时检测权限
        if self._stock_basic_available is None:
            self._check_stock_basic_permission()

        if not self._stock_basic_available:
            # 积分不足，返回空列表，让 FallbackDataSource 切换到备用源
            return []

        try:
            stocks = self.pro.stock_basic(
                exchange='', list_status='L',
                fields='ts_code'
            )
            return stocks['ts_code'].tolist()
        except Exception:
            return []


    def check_health(self) -> bool:
        """
        使用 daily 接口检测连通性（仅需 120 积分），不依赖 stock_basic（需 2000 积分）。
        用一只常见股票（平安银行）的最近一天行情来验证。
        """
        try:
            # 使用一个必定存在的交易日（昨天或前天）
            test_date = date.today()
            # 往前推到最近的交易日（简单处理：跳过周末）
            while test_date.weekday() >= 5:  # 5=周六, 6=周日
                test_date = test_date - timedelta(days=1)

            df = self.pro.daily(
                ts_code='000001.SZ',
                trade_date=test_date.strftime('%Y-%m-%d')
            )
            # 能正常返回即可（即使是空 DataFrame 也说明接口连通）
            return df is not None
        except Exception:
            return False


    def get_source_name(self) -> str:
        return self.source_name

    @staticmethod
    def _symbol_to_tscode(symbol: str) -> str:
        """转换代码格式：000001 -> 000001.SZ"""
        if '.' in symbol:
            return symbol
        if symbol.startswith('6'):
            return f"{symbol}.SH"
        return f"{symbol}.SZ"

    def _check_stock_basic_permission(self):
        """检测 stock_basic 接口权限"""
        try:
            self.pro.stock_basic(list_status='L', limit=1)
            self._stock_basic_available = True
        except Exception:
            self._stock_basic_available = False