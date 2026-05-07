import datetime
from typing import List, Dict

import pandas as pd
import logging

from dateutil.relativedelta import relativedelta

from app.core.data.financial.dynamic_adapter import DynamicFinancialAdapter
from app.core.data.financial.storage import FinancialStorage

logger = logging.getLogger(__name__)

class FinancialScheduler:
    MAX_RECENT_PERIODS = 6

    def __init__(self, adapter: DynamicFinancialAdapter, storage: FinancialStorage):
        self.adapter = adapter
        self.storage = storage
        self._fetch_logs = []

    def fetch_one_stock(self, symbol: str, num_quarters: int = None) -> dict:
        if num_quarters is None:
            num_quarters = self.MAX_RECENT_PERIODS
        periods = self._get_recent_periods(num_quarters)

        total_stored = 0
        for period in periods:
            try:
                all_indicators = self.storage.get_all_indicators()
                # 直接获取窄表
                narrow_df = self.adapter.fetch_indicators(all_indicators, symbol, period)

                if narrow_df is not None and not narrow_df.empty:
                    # 确保 end_date 类型为 date
                    # narrow_df['end_date'] = pd.to_datetime(narrow_df['end_date']).dt.date
                    stored = self.storage.save_indicator_data(narrow_df)
                    total_stored += stored
            except Exception as e:
                logger.warning(f"{symbol} {period} 采集失败: {e}")

        log_entry = {
            "symbol": symbol,
            "periods": len(periods),
            "stored": total_stored,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self._fetch_logs.insert(0, log_entry)
        if len(self._fetch_logs) > 50:
            self._fetch_logs = self._fetch_logs[:50]
        return {"total_stored": total_stored}

    # def fetch_one_stock(self, symbol: str, num_quarters: int = None) -> dict:
    #     if num_quarters is None:
    #         num_quarters = self.MAX_RECENT_PERIODS
    #     periods = self._get_recent_periods(num_quarters)
    #
    #     total_stored = 0
    #     for period in periods:
    #         try:
    #             all_indicators = self.storage.get_all_indicators()
    #             # logger.info(f"all_ind:{all_indicators}")
    #             df = self.adapter.fetch_indicators(all_indicators, symbol, period)
    #             # logger.info(f"df:{df}")
    #             if df is not None and not df.empty:
    #                 rows = []
    #                 for _, row in df.iterrows():
    #                     for ind in all_indicators:
    #                         val = row.get(ind.standard_field)
    #                         if val is not None:
    #                             rows.append({
    #                                 'symbol': symbol,
    #                                 'end_date': datetime.datetime.strptime(period, '%Y%m%d').date(),
    #                                 'report_group': ind.report_group,
    #                                 'indicator_name': ind.standard_field,
    #                                 'value': str(val)  # 统一字符串
    #                             })
    #                 if rows:
    #                     narrow_df = pd.DataFrame(rows)
    #                     stored = self.storage.save_financial_data_batch(narrow_df)
    #                     total_stored += stored
    #         except Exception as e:
    #             logger.warning(f"{symbol} {period} 采集失败: {e}")
    #
    #     log_entry = {
    #         "symbol": symbol,
    #         "periods": len(periods),
    #         "stored": total_stored,
    #         "timestamp": datetime.datetime.now().isoformat(),
    #     }
    #     self._fetch_logs.insert(0, log_entry)
    #     if len(self._fetch_logs) > 50:
    #         self._fetch_logs = self._fetch_logs[:50]
    #     return {"total_stored": total_stored}

    def get_recent_logs(self, limit: int = 20) -> List[Dict]:
        return self._fetch_logs[:limit]

    @staticmethod
    def _get_recent_periods(n: int) -> List[str]:
        today = datetime.date.today()
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        last_period = datetime.date(today.year, quarter_month, 1) - datetime.timedelta(days=1)
        periods = []
        for i in range(n):
            d = last_period - relativedelta(months=3 * i)
            periods.append(d.strftime("%Y%m%d"))
        return periods