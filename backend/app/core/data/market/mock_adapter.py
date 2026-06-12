"""
纯内存模拟的行情数据源 —— 用于在没有外网/没有 akshare/baostock
依赖时，对「采集 → 存储 → 读取 → 聚合」整条链路做端到端回归测试。

返回的是符合随机游走的伪 OHLCV 数据，但字段/格式与真实适配器一致，
因此上层 storage / scheduler / API 感知不到差异。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd

from app.core.params.service import ParameterService
from app.core.data.market.base import DataSource, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


def _seeded_rand(seed_str: str) -> float:
    """把输入字符串哈希成 [0,1) 的浮点数 —— 保证同一只股票在相同日期下结果稳定。"""
    h = hashlib.md5(seed_str.encode("utf-8")).digest()
    val = int.from_bytes(h[:8], "big", signed=False) / (1 << 63) - 1.0  # [-1, 1)
    return (val + 1.0) / 2.0  # [0, 1)


def _date_range(start: date, end: date) -> List[date]:
    """返回闭区间内的工作日列表（周一~周五），避免周末噪声导致 API 测不出问题。"""
    days: List[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


class MockMarketAdapter(DataSource):
    """内存行情模拟器。

    使用方式：
        将 ``data.primary_source`` 设为 ``mock``（见 config/parameters.yaml），
        或直接在 ``DataSourceFactory`` 中使用。
    """

    SOURCE_NAME = "mock"

    _DEFAULT_SYMBOLS: List[str] = [
        "600519.SH",  # 贵州茅台
        "000001.SZ",  # 平安银行
        "600036.SH",  # 招商银行
        "000858.SZ",  # 五粮液
        "601318.SH",  # 中国平安
        "600276.SH",  # 恒瑞医药
        "000333.SZ",  # 美的集团
        "601166.SH",  # 兴业银行
        "000002.SZ",  # 万科A
        "600887.SH",  # 伊利股份
    ]

    def __init__(self, param_service: Optional[ParameterService] = None):
        super().__init__(param_service)
        # 每只股票的基础价格（锚定到真实感的范围，避免出现 0.00x 的不合理价）
        self._base_prices = {
            "600519.SH": 1680.0,
            "000001.SZ": 11.5,
            "600036.SH": 34.0,
            "000858.SZ": 145.0,
            "601318.SH": 48.0,
            "600276.SH": 42.0,
            "000333.SZ": 63.0,
            "601166.SH": 17.0,
            "000002.SZ": 8.8,
            "600887.SH": 26.0,
        }

    # ---------- DataSource 抽象接口 ----------

    def fetch_daily_quote(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        sd = start_date or date.today()
        ed = end_date or sd
        if sd > ed:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ["adj_factor", "source"])

        trading_days = _date_range(sd, ed)
        if not trading_days:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ["adj_factor", "source"])

        frames = []
        for sym in symbols:
            base = self._base_prices.get(sym, 20.0)
            prev_close = base
            rows = []
            for d in trading_days:
                r1 = _seeded_rand(f"{sym}-{d}-o")
                r2 = _seeded_rand(f"{sym}-{d}-h")
                r3 = _seeded_rand(f"{sym}-{d}-l")
                r4 = _seeded_rand(f"{sym}-{d}-c")
                rv = _seeded_rand(f"{sym}-{d}-v")
                ra = _seeded_rand(f"{sym}-{d}-a")

                # 每日波动 ~ 1%，保证是连续可接受的价格序列
                open_p = prev_close * (1.0 + (r1 - 0.5) * 0.02)
                close_p = prev_close * (1.0 + (r4 - 0.5) * 0.02)
                high_p = max(open_p, close_p) * (1.0 + r2 * 0.005)
                low_p = min(open_p, close_p) * (1.0 - r3 * 0.005)
                volume = int(1_000_000 * (0.5 + rv))
                amount = int(volume * close_p)

                rows.append({
                    "symbol": sym,
                    "open": round(open_p, 2),
                    "high": round(high_p, 2),
                    "low": round(low_p, 2),
                    "close": round(close_p, 2),
                    "volume": volume,
                    "amount": amount,
                    "trade_date": d,
                    "adj_factor": 1.0,
                    "source": self.SOURCE_NAME,
                })
                prev_close = close_p
            if rows:
                frames.append(pd.DataFrame(rows))

        if not frames:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ["adj_factor", "source"])

        df = pd.concat(frames, ignore_index=True)
        df = df[STANDARD_COLUMNS + ["adj_factor", "source"]]
        return df

    def get_all_symbols(self) -> List[str]:
        return list(self._DEFAULT_SYMBOLS)

    def check_health(self) -> bool:
        return True

    def get_source_name(self) -> str:
        return self.SOURCE_NAME
