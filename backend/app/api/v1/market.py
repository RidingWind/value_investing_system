from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import date

from app.core.data.market.storage import DataStorage
from app.core.data.market.scheduler import DataScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["行情数据"])

# ---------- 依赖项 ----------
def get_storage(request: Request) -> DataStorage:
    return request.app.state.data_storage

def get_scheduler(request: Request) -> DataScheduler:
    return request.app.state.data_scheduler

def get_data_source(request: Request):
    return request.app.state.data_source

# ---------- 请求/响应模型 ----------
class SourceStatus(BaseModel):
    name: str
    healthy: bool
    last_fetch: Optional[str] = None

class StatusResponse(BaseModel):
    primary: SourceStatus
    backups: List[SourceStatus] = []

class TriggerMarketRequest(BaseModel):
    trade_date: Optional[str] = None

class SymbolListResponse(BaseModel):
    count: int
    symbols: List[str]

class SymbolRangeOut(BaseModel):
    symbol: str
    start_date: Optional[date]
    end_date: Optional[date]
    record_count: int

class SummaryOut(BaseModel):
    total_records: int
    start_date: Optional[date]
    end_date: Optional[date]
    symbol_count: int

class FetchRequest(BaseModel):
    symbols: List[str]
    start_date: Optional[date] = None
    end_date: Optional[date] = None

# ---------- 数据源状态 ----------
_HEALTH_TIMEOUT = 5  # 每个数据源健康检查的超时时间（秒）


def _safe_check_health(source) -> bool:
    """在独立线程中检查健康，超时返回 False"""
    import threading

    result = {"ok": False}

    def _run():
        try:
            result["ok"] = bool(source.check_health())
        except Exception:
            result["ok"] = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(_HEALTH_TIMEOUT)
    if t.is_alive():
        return False
    return result["ok"]


@router.get("/status")
async def get_status(
    data_source=Depends(get_data_source),
    scheduler=Depends(get_scheduler),
):
    """获取各数据源健康状态"""
    primary = data_source.primary
    backups = data_source.backups

    primary_status = {
        "name": primary.get_source_name(),
        "healthy": _safe_check_health(primary),
        "last_fetch": str(scheduler.last_market_fetch) if scheduler.last_market_fetch else None,
    }

    backup_statuses = []
    for backup in backups:
        backup_statuses.append(
            {
                "name": backup.get_source_name(),
                "healthy": _safe_check_health(backup),
                "last_fetch": None,
            }
        )

    return {"primary": primary_status, "backups": backup_statuses}


# ---------- 股票列表 ----------
@router.get("/symbols")
async def get_symbols(data_source=Depends(get_data_source)):
    """获取可用股票列表（带超时保护）"""
    import threading

    symbols = []

    def _run():
        try:
            symbols.extend(list(data_source.get_all_symbols() or []))
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(10)
    return {"count": len(symbols), "symbols": symbols[:200]}

# ---------- 行情数据总览 ----------
@router.get("/summary", response_model=SummaryOut)
async def data_summary(storage=Depends(get_storage)):
    """获取数据库总体行情数据概况"""
    return storage.get_summary()

# ---------- 股票数据区间 ----------
@router.get("/range/{symbol}", response_model=SymbolRangeOut)
async def symbol_data_range(symbol: str, storage=Depends(get_storage)):
    """查询某只股票在库中的数据区间及记录数"""
    result = storage.get_symbol_range(symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="未找到该股票的数据")
    return result

# ---------- 手动补全行情 ----------
@router.post("/fetch")
async def fetch_data(req: FetchRequest, scheduler=Depends(get_scheduler)):
    """手动触发指定股票和时间区间的行情采集"""
    if not req.symbols:
        raise HTTPException(status_code=400, detail="股票列表不能为空")
    start = req.start_date or date.today()
    end = req.end_date or date.today()

    try:
        df = scheduler.do_market_fetch(req.symbols,start, end, "manual")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{req.symbols}:{start}-{end} 采集失败: {e}")
    return {"message": f"采集完成，共获取 {len(df)} 条记录"}

# ---------- 采集日志 ----------
@router.get("/logs")
async def get_fetch_logs(
    limit: int = Query(20, ge=1, le=100),
    scheduler=Depends(get_scheduler)
):
    """获取最近的行情采集日志"""
    logs = scheduler.get_recent_logs(limit)
    return {"logs": logs}

@router.get("/daily/{symbol}")
async def daily_chart_data(
    symbol: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    freq: str = Query("daily"),
    storage = Depends(get_storage)
):
    data = storage.get_daily_data(symbol, start_date, end_date, freq)
    return data