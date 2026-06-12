from datetime import date, datetime
import time
import logging
import pandas as pd
from typing import Optional
from .indicator_engine import IndicatorEngine
from decimal import Decimal, InvalidOperation

from .models import ApiDef

logger = logging.getLogger(__name__)


def _mock_dataframe(function_name: str, symbol: str, period: str) -> pd.DataFrame:
    """根据 function_name 返回一张包含一行样例数据的 DataFrame。

    约定：列名尽量贴近真实 akshare 返回的列（如 ``OPERATE_INCOME``、``TOTAL_ASSETS`` 等），
    这样 ``seed.py`` 中预置的公式就能直接用上这些列。
    """
    # 将 period (如 "20260331") 解析成 ISO 日期，让 date_column 能匹配上
    try:
        period_dt = datetime.strptime(period, "%Y%m%d").date()
    except Exception:
        period_dt = date.today()
    iso_date = period_dt.isoformat()

    # 给每只股票不同的数值，保证测试时能区分
    seed = sum(ord(c) for c in symbol) % 100
    base = 1_000_000.0 + seed * 10_000

    if function_name == "mock_profit_sheet":
        return pd.DataFrame([{
            "REPORT_DATE": iso_date,
            "REPORT_TYPE": "1",
            "SECURITY_CODE": symbol,
            "OPERATE_INCOME": Decimal(str(base)),        # 营业收入
            "NETPROFIT": Decimal(str(base * 0.18)),       # 净利润
            "TOTAL_OPERATE_COST": Decimal(str(base * 0.7)),
            "OPERATE_PROFIT": Decimal(str(base * 0.22)),
        }])

    if function_name == "mock_balance_sheet":
        return pd.DataFrame([{
            "REPORT_DATE": iso_date,
            "REPORT_TYPE": "1",
            "SECURITY_CODE": symbol,
            "TOTAL_ASSETS": Decimal(str(base * 5)),         # 总资产
            "TOTAL_LIABILITIES": Decimal(str(base * 2.5)),  # 总负债
            "TOTAL_EQUITY": Decimal(str(base * 2.5)),       # 所有者权益
            "MONETARYFUNDS": Decimal(str(base * 0.3)),
        }])

    if function_name == "mock_cash_flow_sheet":
        return pd.DataFrame([{
            "REPORT_DATE": iso_date,
            "REPORT_TYPE": "1",
            "SECURITY_CODE": symbol,
            "NET_CASH_FLOW_OPERATE_ACTIVITY": Decimal(str(base * 0.2)),
            "NET_CASH_FLOW_INVEST_ACTIVITY": Decimal(str(base * (-0.05))),
            "NET_CASH_FLOW_FINANC_ACTIVITY": Decimal(str(base * 0.03)),
        }])

    if function_name == "mock_financial_indicators":
        return pd.DataFrame([{
            "日期": iso_date,
            "净资产收益率": Decimal(str(12.5 + (seed % 10))),
            "基本每股收益": Decimal(str(round(1.0 + seed / 100, 2))),
            "每股净资产": Decimal(str(round(8.5 + seed / 50, 2))),
            "毛利率": Decimal(str(32.0 + (seed % 10))),
        }])

    # 未知 mock 函数名 —— 返回空表，让上游优雅降级
    return pd.DataFrame()


class DynamicFinancialAdapter:
    @staticmethod
    def _standardize_symbol(ts_code: str) -> str:
        """将任何格式的股票代码统一为 '数字.大写交易所'，如 '000001.SZ'"""
        if not ts_code:
            return ts_code
        if '.' in ts_code:
            code, exchange = ts_code.split('.')
            return f"{code.strip()}.{exchange.strip().upper()}"
        code = ts_code.strip()
        if code.startswith('6'):
            return f"{code}.SH"
        return f"{code}.SZ"

    def __init__(self, storage, param_service, source='akshare'):
        self.storage = storage
        self.param_service = param_service
        self.source = source
        self._api_cache = {}  # 缓存 API 定义

    def fetch_indicators(self, indicators, symbol, period):
        symbol = self._standardize_symbol(symbol)
        if not indicators:
            return pd.DataFrame()

        api_ids = set()
        for ind in indicators:
            deps = self.storage.get_indicator_deps(ind.id)
            for dep in deps:
                api_ids.add(dep['api_id'])

        row = {}
        for api_id in api_ids:
            api_def = self._get_cached_api(api_id)
            if api_def:
                df = self._call_api(api_def, symbol, period)
                if df is not None and not df.empty:
                    for col in df.columns:
                        row[col] = self.storage.to_decimal_or_none(df.iloc[0][col])

        records = []
        for ind in indicators:
            value = IndicatorEngine.compute(ind.formula, row)
            if value is None:
                continue
            if isinstance(value, Decimal):
                if value.is_nan():
                    continue
            else:
                try:
                    value = Decimal(str(value))
                    if value.is_nan():
                        continue
                except (InvalidOperation, ValueError, TypeError):
                    continue

            records.append({
                'symbol': symbol,
                'end_date': datetime.strptime(period, '%Y%m%d').date(),
                'report_group': getattr(ind, 'report_group', 'indicator'),
                'indicator_name': ind.standard_field,
                'value': value,
                'source': self.source,
            })

        return pd.DataFrame(records)

    def _get_cached_api(self, api_id) -> Optional[ApiDef]:
        if api_id not in self._api_cache:
            self._api_cache[api_id] = self.storage.get_api_def(api_id)
        return self._api_cache[api_id]

    def _call_api(self, api_def, symbol, period) -> pd.DataFrame:
        """调用单一 API。对 ``mock_*`` 函数直接返回构造好的 DataFrame，对其它函数走 akshare。"""
        kwargs = self._build_kwargs(api_def, symbol, period)
        logger.info(f"[API调用] 函数: {api_def.function_name}, 参数: {kwargs}")

        func_name = (api_def.function_name or "").strip()

        # 离线 mock 分支 —— 无需外网、无需导入 akshare 也能跑
        if func_name.startswith("mock_"):
            df = _mock_dataframe(func_name, symbol, period)
            if df.empty:
                logger.info(f"{func_name} 返回空数据（未知 mock 函数名），股票 {symbol} 报告期 {period}")
                return pd.DataFrame()
            # 日期筛选
            if api_def.date_column and api_def.date_column in df.columns:
                target = f"{period[:4]}-{period[4:6]}-{period[6:]}"
                df = df.copy()
                df[api_def.date_column] = df[api_def.date_column].astype(str)
                df = df[df[api_def.date_column].str.startswith(target[:7]) | (df[api_def.date_column] == target)]
            # filter_condition 兼容：允许如 "REPORT_TYPE == '1'"
            if api_def.filter_condition and api_def.filter_condition:
                try:
                    df = df.query(api_def.filter_condition)
                except Exception:
                    pass
            return df

        # 在线 akshare 分支
        try:
            import akshare as ak
        except ImportError:
            logger.error(f"akshare 未安装，无法调用 {func_name}")
            return pd.DataFrame()

        func = getattr(ak, func_name, None)
        if not func:
            logger.error(f"akshare 函数不存在: {func_name}")
            return pd.DataFrame()
        try:
            time.sleep(0.3)
            df = func(**kwargs)
            if df is None or df.empty:
                logger.info(f"{func_name} 返回空数据，股票 {symbol} 报告期 {period}")
                return pd.DataFrame()
            if api_def.date_column and api_def.date_column in df.columns:
                target = f"{period[:4]}-{period[4:6]}-{period[6:]}"
                df[api_def.date_column] = df[api_def.date_column].astype(str)
                df = df[df[api_def.date_column] == target]
            if api_def.filter_condition and api_def.filter_condition in df.columns:
                df = df.query(api_def.filter_condition)
            return df
        except Exception as e:
            logger.error(f"调用 {func_name} 失败: {e}")
            return pd.DataFrame()

    def _build_kwargs(self, api_def, symbol, period):
        params = {}
        for key, val in (api_def.input_params or {}).items():
            if isinstance(val, str):
                val = val.replace('{em_symbol}', self._to_em_symbol(symbol))
                val = val.replace('{symbol}', symbol)
                val = val.replace('{period}', period)
            params[key] = val
        return params

    @staticmethod
    def _to_em_symbol(ts_code):
        code = ts_code.split('.')[0]
        return f"SH{code}" if code.startswith('6') else f"SZ{code}"

    @staticmethod
    def _clean_symbol(ts_code):
        return ts_code.split('.')[0]