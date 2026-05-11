from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import logging
from datetime import datetime, timedelta
import akshare as ak

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["搜索"])

# 数据库连接（复用项目的 engine，这里简单示意）
from app.config import get_database_url
engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)

MAX_CACHE_AGE_HOURS = 24

def _fetch_and_store_stock_list():
    """从 akshare 获取最新股票列表，并全量写入数据库"""
    try:
        df = ak.stock_info_a_code_name()
        from pypinyin import lazy_pinyin
        df['pinyin'] = df['name'].apply(lambda x: ''.join([c[0].upper() for c in lazy_pinyin(x)]))
        df['exchange'] = df['code'].apply(lambda x: 'SH' if x.startswith('6') else 'SZ')
    except Exception as e:
        logger.error(f"从 akshare 获取股票列表失败: {e}")
        return False

    session = SessionLocal()
    try:
        # 清空旧数据
        session.execute(text("DELETE FROM stock_list"))
        for _, row in df.iterrows():
            session.execute(
                text("INSERT INTO stock_list (code, name, pinyin, exchange, updated_at) VALUES (:code, :name, :pinyin, :exchange, :now)"),
                {
                    "code": row['code'],
                    "name": row['name'],
                    "pinyin": row['pinyin'],
                    "exchange": row['exchange'],
                    "now": datetime.utcnow()
                }
            )
        session.commit()
        logger.info(f"股票列表已更新，共 {len(df)} 条")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"写入股票列表失败: {e}")
        return False
    finally:
        session.close()

def _get_stock_list_from_db():
    """从数据库获取股票列表，返回 DataFrame"""
    session = SessionLocal()
    try:
        rows = session.execute(text("SELECT code, name, pinyin, exchange FROM stock_list")).fetchall()
        if not rows:
            return pd.DataFrame(columns=['code', 'name', 'pinyin', 'exchange'])
        return pd.DataFrame(rows, columns=['code', 'name', 'pinyin', 'exchange'])
    finally:
        session.close()

def _is_cache_expired():
    """检查数据库中的列表是否过期（不存在或超过阈值）"""
    session = SessionLocal()
    try:
        row = session.execute(text("SELECT MAX(updated_at) FROM stock_list")).fetchone()
        if row is None or row[0] is None:
            return True
        last_update = row[0]
        if datetime.utcnow() - last_update > timedelta(hours=MAX_CACHE_AGE_HOURS):
            return True
        return False
    finally:
        session.close()

# 应用启动时执行一次（通过 FastAPI 的 lifespan 或手动调用）
async def init_stock_cache():
    if _is_cache_expired():
        logger.info("股票列表缓存过期，尝试更新...")
        success = _fetch_and_store_stock_list()
        if not success:
            logger.warning("更新股票列表失败，将使用旧数据（如有）")
    else:
        logger.info("股票列表缓存有效")

@router.get("/stocks")
async def search_stocks(keyword: str = Query(..., min_length=1)):
    """根据代码、名称或拼音首字母模糊查询A股"""
    cache = _get_stock_list_from_db()
    if cache.empty:
        return []

    keyword_upper = keyword.upper()
    mask = (
        cache['code'].str.contains(keyword_upper, na=False) |
        cache['name'].str.contains(keyword_upper, na=False) |
        cache['pinyin'].str.contains(keyword_upper, na=False)
    )
    matches = cache[mask].head(20)

    results = []
    for _, row in matches.iterrows():
        code = row['code']
        exchange = row['exchange'] if pd.notna(row['exchange']) else ('SH' if code.startswith('6') else 'SZ')
        standard_code = f"{code}.{exchange}"
        results.append({
            'code': code,
            'standard_code': standard_code,
            'name': row['name'],
            'pinyin': row['pinyin']
        })
    return results

# 手动刷新缓存的管理接口
@router.post("/stocks/refresh-cache")
async def refresh_stock_cache():
    success = _fetch_and_store_stock_list()
    if success:
        return {"message": "股票列表已刷新"}
    else:
        raise HTTPException(status_code=502, detail="无法从 akshare 获取最新股票列表")