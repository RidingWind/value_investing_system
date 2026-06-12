import math
import re
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class _ApiColumnProxy:
    """让 `api('xxx').col('yyy')` 能在 eval 中求值成真实列值。

    规则：
    - 若 ``row['yyy']`` 存在，返回其值（通常是 Decimal / None）。
    - 若不存在，返回 ``None``。
    """

    __slots__ = ("_row", "_func_name")

    def __init__(self, row: dict, func_name: str = ""):
        self._row = row
        self._func_name = func_name

    def col(self, column_name: str):
        if column_name in self._row:
            return self._row[column_name]
        # 兼容中文列名带空格/换行的情况：尝试模糊匹配
        for key in self._row:
            if isinstance(key, str) and key.strip() == column_name:
                return self._row[key]
        return None


def _make_api_lookup(row: dict):
    def api(func_name: str = ""):
        return _ApiColumnProxy(row, func_name)
    return api


class IndicatorEngine:
    ALLOWED_NAMES = {
        'abs': abs,
        'round': round,
        'max': max,
        'min': min,
        'float': float,
        'int': int,
        'str': str,
        'bool': bool,
        'len': len,
        'math': math,
        'Decimal': Decimal,
        'decimal': Decimal,
        'InvalidOperation': InvalidOperation,
    }

    @classmethod
    def compute(cls, formula: str, row: dict):
        if not formula:
            return None
        # 空白公式 / 数字常量，直接返回 —— 兼容 save_indicator 里 ``formula: "1"``
        stripped = formula.strip()
        if _is_numeric(stripped):
            try:
                return Decimal(stripped)
            except (InvalidOperation, ValueError):
                pass
        allowed = dict(cls.ALLOWED_NAMES)
        allowed['row'] = row
        allowed['api'] = _make_api_lookup(row)
        try:
            value = eval(stripped, {"__builtins__": {}}, allowed)
        except Exception as e:
            logger.error(f"指标计算公式执行错误: {formula}, 错误: {e}")
            return None

        if value is None:
            return None
        # 将常见数值类型规范化为 Decimal，便于存储比较
        if isinstance(value, bool):
            return Decimal(int(value))
        if isinstance(value, (int, float)):
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                return None
        if isinstance(value, Decimal):
            return value
        # 字符串 / 其它：尝试转 Decimal，失败就原样返回
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None


_NUMERIC_RE = re.compile(r'^\s*-?\d+(\.\d+)?\s*$')


def _is_numeric(s: str) -> bool:
    return bool(_NUMERIC_RE.match(s))
