import math
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class IndicatorEngine:
    ALLOWED_NAMES = {
        'row': None,       # 运行时动态注入
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
        'Decimal': Decimal,  # 新增
        'decimal': Decimal,  # 别名
        'InvalidOperation': InvalidOperation,  # 异常
    }

    @classmethod
    def compute(cls, formula: str, row: dict):
        if not formula:
            return None
        allowed = dict(cls.ALLOWED_NAMES)
        allowed['row'] = row
        try:
            return eval(formula, {"__builtins__": {}}, allowed)
        except Exception as e:
            logger.error(f"指标计算公式执行错误: {formula}, 错误: {e}")
            return None