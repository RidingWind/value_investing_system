
import akshare as ak
import pandas as pd
from datetime import date
from typing import List, Optional
from .base import DataSource, STANDARD_COLUMNS
from app.core.params.service import ParameterService
import logging

logger = logging.getLogger(__name__)

class AKShareAdapter(DataSource):

    def __init__(self, param_service: ParameterService):
        super().__init__(param_service)
        self.source_name = "akshare"
        self._all_symbols_cache = None

    @staticmethod
    def _normalize_symbol(raw_code: str) -> str:
        """统一格式：600000.SH, 000001.SZ, 920000.BJ"""
        if '.' in raw_code:
            return raw_code  # 已经是标准格式
        # akshare 返回的代码如 'sh600000', 'sz000001', 'bj920000'
        if raw_code.startswith('sh'):
            return raw_code[2:] + '.SH'
        elif raw_code.startswith('sz'):
            return raw_code[2:] + '.SZ'
        elif raw_code.startswith('bj'):
            return raw_code[2:] + '.BJ'
        else:
            return raw_code  # 未知格式，保持原样

    def fetch_daily_quote(
            self,
            symbols: List[str],
            start_date: Optional[date] = None,
            end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        获取日线行情（前复权）
        参数：
            symbols: 股票代码列表，支持带后缀或不带后缀，方法内部会统一格式
            trade_date: 目标日期，默认为今天
        返回：
            DataFrame 包含标准字段 + adj_factor（暂为1.0）
        """
        # 处理默认值
        sd = start_date if start_date is not None else date.today()
        ed = end_date if end_date is not None else sd
        start_str = sd.strftime('%Y%m%d')
        end_str = ed.strftime('%Y%m%d')

        all_frames = []
        for symbol in symbols:
            # 1. 统一股票代码格式（如 600000.SH）
            std_symbol = self._normalize_symbol(symbol)
            # 2. 提取纯数字部分，供 akshare API 调用
            code = std_symbol.split('.')[0]

            # try:
            logger.info(f"code: {code}; symbol: {std_symbol};start_date: {start_str};end_date: {end_str}")
            hist = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust="qfq"  # 前复权
            )
            if hist is not None and not hist.empty:
                # logger.info(f"hist: {hist}")
                # 重新设置标准格式的 symbol
                hist['symbol'] = std_symbol
                all_frames.append(hist)
            # except Exception:
            #     logger.warning(f"{symbol} 行情获取失败")
            #     continue

        if not all_frames:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ['adj_factor'])

        df = pd.concat(all_frames, ignore_index=True)
        # 字段映射
        df = df.rename(columns={
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '日期': 'trade_date'
        })
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # 添加复权因子（akshare 前复权接口未直接提供复权因子，暂设为1.0）
        df['adj_factor'] = 1.0
        df['source'] = self.source_name
        # 确保列顺序
        df = df[STANDARD_COLUMNS + ['adj_factor'] + ['source']]
        return df

    def get_all_symbols(self) -> List[str]:
        if self._all_symbols_cache is not None:
            return self._all_symbols_cache
        try:
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                raw_codes = df['代码'].tolist()
                self._all_symbols_cache = [self._normalize_symbol(c) for c in raw_codes]
            else:
                self._all_symbols_cache = []
        except Exception:
            self._all_symbols_cache = []
        return self._all_symbols_cache

    def check_health(self) -> bool:
        try:
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                return True
            return False
        except Exception:
            return False

    def get_source_name(self) -> str:
        return self.source_name