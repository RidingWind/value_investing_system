import baostock as bs
import pandas as pd
from datetime import date, datetime
from typing import List, Optional

from .base import DataSource, STANDARD_COLUMNS
from app.core.params.service import ParameterService


class BaoStockAdapter(DataSource):
    """BaoStock 适配器，支持前复权行情，返回统一标准字段"""

    def __init__(self, param_service: ParameterService):
        super().__init__(param_service)
        self.source_name = "baostock"
        self._logged_in = False

    def _login(self):
        if not self._logged_in:
            bs.login()
            self._logged_in = True

    def _logout(self):
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    # ---------- 符号格式转换 ----------
    @staticmethod
    def _to_standard(code: str) -> str:
        """将 baostock 格式（sh.600000）转为标准格式（600000.SH）"""
        if '.' in code:
            parts = code.split('.')
            if len(parts) == 2 and parts[0] in ('sh', 'sz', 'bj'):
                return parts[1] + '.' + parts[0].upper()
        # 若已是标准格式（包含 .SH/.SZ），直接返回
        if '.' in code and code.split('.')[1].upper() in ('SH', 'SZ', 'BJ'):
            return code
        return code   # 未识别的格式，原样返回

    @staticmethod
    def _to_baostock(symbol: str) -> str:
        """将标准格式（600000.SH）转为 baostock 格式（sh.600000）"""
        if '.' in symbol:
            code, market = symbol.split('.')
            return market.lower() + '.' + code
        # 不带后缀，根据代码猜测
        if symbol.startswith('6'):
            return 'sh.' + symbol
        return 'sz.' + symbol

    # ---------- 核心接口实现 ----------
    def fetch_daily_quote(self, symbols: List[str], trade_date: Optional[date] = None) -> pd.DataFrame:
        self._login()
        if trade_date is None:
            trade_date = date.today()
        date_str = trade_date.strftime('%Y-%m-%d')

        all_frames = []
        for sym in symbols:
            std_symbol = self._to_standard(sym)       # 统一成 600000.SH 格式
            baostock_code = self._to_baostock(std_symbol)  # 转成 sh.600000 用于查询
            try:
                rs = bs.query_history_k_data_plus(
                    baostock_code,
                    "date,open,high,low,close,volume,amount",
                    start_date=date_str,
                    end_date=date_str,
                    frequency="d",
                    adjustflag="2"      # 前复权
                )
                if rs.error_code != '0':
                    continue
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if data_list:
                    df_part = pd.DataFrame(data_list, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
                    df_part['symbol'] = std_symbol
                    all_frames.append(df_part)
            except Exception:
                continue

        if not all_frames:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ['adj_factor'])

        df = pd.concat(all_frames, ignore_index=True)
        df = df.rename(columns={'date': 'trade_date'})
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # 添加复权因子（baostock 不直接提供，暂设为1.0）
        df['adj_factor'] = 1.0
        df = df[STANDARD_COLUMNS + ['adj_factor']]
        return df

    def get_all_symbols(self) -> List[str]:
        """获取全部 A 股代码，返回标准格式列表"""
        self._login()
        symbols = []
        for market in ('sh', 'sz'):
            rs = bs.query_stock_basic(market=market)
            while rs.next():
                row = rs.get_row_data()
                # row[0] 格式：sh.600000
                std = self._to_standard(row[0])
                symbols.append(std)
        return symbols

    def check_health(self) -> bool:
        try:
            self._login()
            rs = bs.query_stock_basic(code_name="上证50")
            return rs.error_code == '0'
        except Exception:
            return False

    def get_source_name(self) -> str:
        return self.source_name

    def __del__(self):
        self._logout()