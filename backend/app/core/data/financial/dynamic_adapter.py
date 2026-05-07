from datetime import datetime
import time
import logging
import pandas as pd
import akshare as ak
from typing import Optional
from .indicator_engine import IndicatorEngine
from decimal import Decimal, InvalidOperation

from .models import ApiDef

logger = logging.getLogger(__name__)

class DynamicFinancialAdapter:
    @staticmethod
    def _standardize_symbol(ts_code: str) -> str:
        """将任何格式的股票代码统一为 '数字.大写交易所'，如 '000001.SZ'"""
        if not ts_code:
            return ts_code
        # 如果包含点号，拆分成代码和交易所
        if '.' in ts_code:
            code, exchange = ts_code.split('.')
            return f"{code.strip()}.{exchange.strip().upper()}"
        else:
            # 无后缀，根据代码推断（6开头为上海，其余深圳），但建议强制带后缀，此处兼容
            code = ts_code.strip()
            if code.startswith('6'):
                return f"{code}.SH"
            else:
                return f"{code}.SZ"

    def __init__(self, storage, param_service, source='akshare'):
        self.storage = storage
        self.param_service = param_service
        self.source = source
        self._api_cache = {}  # 缓存 API 定义

    def fetch_indicators(self, indicators, symbol, period):
        symbol = self._standardize_symbol(symbol)
        """批量计算传入指标的值"""
        if not indicators:
            return pd.DataFrame()

        # 收集所有需要的 API（去重）
        api_ids = set()
        for ind in indicators:
            # logger.info(f"indicator:{ind.standard_field}")
            deps = self.storage.get_indicator_deps(ind.id)
            # logger.info(f"deps:{deps}")
            for dep in deps:
                # logger.info(f"dep:{dep}")
                api_ids.add(dep['api_id'])

        # 构建 row 上下文
        row = {}
        # logger.info(f"api_ids:{api_ids}")
        for api_id in api_ids:
            api_def = self._get_cached_api(api_id)
            if api_def:
                df = self._call_api(api_def, symbol, period)
                if not df.empty:
                    for col in df.columns:
                        row[col] = self.storage.to_decimal_or_none(df.iloc[0][col])
                        # logger.info(row[col])

        # 逐指标计算
        records = []
        for ind in indicators:
            value = IndicatorEngine.compute(ind.formula, row)
            logger.info(f"ind.formula:{ind.formula}, value:{value}")

            # 过滤无效值
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
                'source': self.source
            })

        return pd.DataFrame(records)

    def _get_cached_api(self, api_id) -> Optional[ApiDef]:
        if api_id not in self._api_cache:
            self._api_cache[api_id] = self.storage.get_api_def(api_id)
        return self._api_cache[api_id]

    def _call_api(self, api_def, symbol, period) -> pd.DataFrame:
        kwargs = self._build_kwargs(api_def, symbol, period)
        logger.info(f"[API调用] 函数: {api_def.function_name}, 参数: {kwargs}")

        func = getattr(ak, api_def.function_name, None)
        if not func:
            logger.error(f"AKShare 函数不存在: {api_def.function_name}")
            return None
        try:
            time.sleep(0.3)
            df = func(**kwargs)

            # 记录返回形状和前几列
            # if df is not None and not df.empty:
            #     logger.info(
            #         f"[API响应] {api_def.function_name} 返回 {df.shape[0]} 行, 列: {list(df.columns)[:]}")  # 前20列
            #     logger.info(f"样例数据:\n{df.head(2).to_string()}")
            # else:
            #     logger.warning(f"[API响应] {api_def.function_name} 返回空数据")

            if df is None or df.empty:
                logger.info(f"{api_def.function_name} 返回空数据，股票 {symbol} 报告期 {period}")
                return pd.DataFrame()
            # 筛选日期
            if api_def.date_column and api_def.date_column in df.columns:
                target = f"{period[:4]}-{period[4:6]}-{period[6:]}"
                df[api_def.date_column] = df[api_def.date_column].astype(str)
                df = df[df[api_def.date_column] == target]
            # 可选筛选
            if api_def.filter_condition and api_def.filter_condition in df.columns:
                df = df.query(api_def.filter_condition)
            return df
        except Exception as e:
            logger.error(f"调用 {api_def.function_name} 失败: {e}")
            return pd.DataFrame()

    def _build_kwargs(self, api_def, symbol, period):
        params = {}
        for key, val in api_def.input_params.items():
            if isinstance(val, str):
                val = val.replace('{em_symbol}', self._to_em_symbol(symbol))
                val = val.replace('{symbol}', symbol)  # 直接使用带后缀的代码
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