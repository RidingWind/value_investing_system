from fastapi import APIRouter, Query, HTTPException, Request
from sqlalchemy import text
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["搜索"])

MAX_CACHE_AGE_HOURS = 24
STOCK_LIST_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS stock_list (
    code VARCHAR(10) NOT NULL,
    name VARCHAR(64),
    pinyin VARCHAR(64),
    exchange VARCHAR(4),
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (code)
);
"""


def _get_engine(request: Request):
    for attr in ("data_storage", "financial_storage"):
        storage = getattr(request.app.state, attr, None)
        if storage is not None and getattr(storage, "engine", None) is not None:
            return storage.engine
    raise HTTPException(status_code=503, detail="数据库尚未初始化")


def _ensure_table(engine):
    with engine.connect() as conn:
        conn.execute(text(STOCK_LIST_TABLE_DDL))
        conn.commit()


def _lazy_pinyin_first_letter(name: str) -> str:
    """轻量拼音首字母；优先使用 pypinyin，不可用时退化为空字符串。"""
    try:
        from pypinyin import lazy_pinyin
        return "".join([c[0].upper() for c in lazy_pinyin(name or "")])
    except Exception:
        return ""


def _fetch_and_store_stock_list(request: Request) -> bool:
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        df["pinyin"] = df["name"].apply(_lazy_pinyin_first_letter)
        df["exchange"] = df["code"].apply(lambda x: "SH" if str(x).startswith("6") else "SZ")
    except Exception as e:
        logger.error(f"从 akshare 获取股票列表失败: {e}")
        return False

    engine = _get_engine(request)
    _ensure_table(engine)
    now = datetime.utcnow()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM stock_list"))
            for _, row in df.iterrows():
                conn.execute(
                    text(
                        "INSERT INTO stock_list (code, name, pinyin, exchange, updated_at) "
                        "VALUES (:code, :name, :pinyin, :exchange, :now)"
                    ),
                    {
                        "code": str(row["code"]),
                        "name": row["name"],
                        "pinyin": row["pinyin"],
                        "exchange": row["exchange"],
                        "now": now,
                    },
                )
        logger.info(f"股票列表已更新，共 {len(df)} 条")
        return True
    except Exception as e:
        logger.error(f"写入股票列表失败: {e}")
        return False


def _get_stock_list_from_db(request: Request) -> pd.DataFrame:
    engine = _get_engine(request)
    _ensure_table(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT code, name, pinyin, exchange FROM stock_list")
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["code", "name", "pinyin", "exchange"])
    return pd.DataFrame(rows, columns=["code", "name", "pinyin", "exchange"])


def _is_cache_expired(request: Request) -> bool:
    engine = _get_engine(request)
    _ensure_table(engine)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT MAX(updated_at) FROM stock_list")).fetchone()
        if row is None or row[0] is None:
            return True
        last_update = row[0]
        if isinstance(last_update, str):
            last_update = datetime.fromisoformat(last_update.replace("Z", ""))
        if datetime.utcnow() - last_update > timedelta(hours=MAX_CACHE_AGE_HOURS):
            return True
        return False
    except Exception as e:
        logger.warning(f"检查股票列表缓存过期失败: {e}")
        return True


async def init_stock_cache():
    """应用启动时预热缓存；若存储未就绪则跳过，首次 API 调用时再尝试。"""
    try:
        # 延迟导入以避免循环依赖 / 未初始化状态下直接访问 app.state
        from app.main import app as _app
    except Exception:
        _app = None

    if _app is None:
        logger.info("app 尚未就绪，跳过股票列表预热")
        return

    try:
        if _is_cache_expired(_FAKEREQUEST(_app)):
            logger.info("股票列表缓存过期，尝试更新...")
            success = _fetch_and_store_stock_list(_FAKEREQUEST(_app))
            if not success:
                logger.warning("更新股票列表失败，将在首次搜索时重试")
        else:
            logger.info("股票列表缓存有效")
    except Exception as e:
        logger.warning(f"预热股票列表失败: {e}")


class _FAKEREQUEST:
    """最小化的 Request 替身，仅暴露 app.state 给内部函数使用。"""

    def __init__(self, app):
        self.app = app


@router.get("/stocks")
async def search_stocks(request: Request, keyword: str = Query(..., min_length=1)):
    """根据代码、名称或拼音首字母模糊查询 A 股"""
    # 若缓存过期则先刷新
    if _is_cache_expired(request):
        _fetch_and_store_stock_list(request)

    cache = _get_stock_list_from_db(request)
    if cache.empty:
        return []

    keyword_upper = keyword.upper()
    mask = (
        cache["code"].astype(str).str.contains(keyword_upper, na=False)
        | cache["name"].astype(str).str.contains(keyword_upper, na=False)
        | cache["pinyin"].astype(str).str.contains(keyword_upper, na=False)
    )
    matches = cache[mask].head(20)

    results = []
    for _, row in matches.iterrows():
        code = str(row["code"])
        exchange = row["exchange"] if pd.notna(row["exchange"]) else (
            "SH" if code.startswith("6") else "SZ"
        )
        results.append(
            {
                "code": code,
                "standard_code": f"{code}.{exchange}",
                "name": row["name"],
                "pinyin": row["pinyin"],
            }
        )
    return results


@router.post("/stocks/refresh-cache")
async def refresh_stock_cache(request: Request):
    success = _fetch_and_store_stock_list(request)
    if success:
        return {"message": "股票列表已刷新"}
    raise HTTPException(status_code=502, detail="无法从 akshare 获取最新股票列表")
