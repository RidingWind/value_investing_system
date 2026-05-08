# backend/app/api/v1/search.py
from fastapi import APIRouter, Query
import akshare as ak
import pandas as pd
import logging
from typing import List
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["搜索"])

# 启动时加载缓存
_stock_cache: pd.DataFrame = None

def _get_stock_cache():
    global _stock_cache
    if _stock_cache is None:
        try:
            # 获取A股实时股票列表 (akshare接口)
            df = ak.stock_info_a_code_name()
            # 添加拼音首字母列（需安装 pypinyin）
            from pypinyin import lazy_pinyin
            df['pinyin'] = df['name'].apply(lambda x: ''.join([c[0].upper() for c in lazy_pinyin(x)]))
            _stock_cache = df[['code', 'name', 'pinyin']]
        except Exception as e:
            logger.error(f"加载股票列表失败: {e}")
            _stock_cache = pd.DataFrame(columns=['code', 'name', 'pinyin'])
    return _stock_cache

@router.get("/stocks")
async def search_stocks(keyword: str = Query(..., min_length=1)):
    """根据代码、名称或拼音首字母模糊查询A股，返回匹配的股票列表"""
    cache = _get_stock_cache()
    if cache.empty:
        return []

    keyword_upper = keyword.upper()
    # 匹配条件：代码、名称、拼音首字母包含关键字
    mask = (
        cache['code'].str.contains(keyword_upper, na=False) |
        cache['name'].str.contains(keyword_upper, na=False) |
        cache['pinyin'].str.contains(keyword_upper, na=False)
    )
    matches = cache[mask].head(20)  # 限制返回数量

    results = []
    for _, row in matches.iterrows():
        # 转换为标准代码格式（SZ/SH）
        code = row['code']
        exchange = 'SH' if code.startswith('6') else 'SZ'
        standard_code = f"{code}.{exchange}"
        results.append({
            'code': code,
            'standard_code': standard_code,
            'name': row['name'],
            'pinyin': row['pinyin']
        })
    return results