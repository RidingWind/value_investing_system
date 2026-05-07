from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import date, timedelta

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
@router.get("/status", response_model=StatusResponse)
async def get_status(
    data_source=Depends(get_data_source),
    scheduler=Depends(get_scheduler)
):
    """获取各数据源健康状态"""
    primary = data_source.primary
    backups = data_source.backups

    primary_status = SourceStatus(
        name=primary.get_source_name(),
        healthy=primary.check_health(),
        last_fetch=str(scheduler._last_market_fetch) if scheduler._last_market_fetch else None
    )

    backup_statuses = []
    for backup in backups:
        backup_statuses.append(
            SourceStatus(
                name=backup.get_source_name(),
                healthy=backup.check_health(),
                last_fetch=None
            )
        )

    return StatusResponse(primary=primary_status, backups=backup_statuses)

# ---------- 手动触发采集 ----------
@router.post("/trigger")
async def trigger_market_fetch(
    req: TriggerMarketRequest = None,
    scheduler=Depends(get_scheduler)
):
    """手动触发一次当日行情采集"""
    try:
        trade_date = None
        if req and req.trade_date:
            from datetime import datetime
            trade_date = datetime.strptime(req.trade_date, "%Y-%m-%d").date()
        logger.info(f"开始采集行情，日期：{trade_date}")
        df = scheduler.trigger_market_fetch(trade_date)
        return {"message": f"采集成功，获取 {len(df)} 条记录"}
    except Exception as e:
        logger.exception("行情采集失败")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- 股票列表 ----------
@router.get("/symbols", response_model=SymbolListResponse)
async def get_symbols(data_source=Depends(get_data_source)):
    """获取可用股票列表"""
    try:
        symbols = data_source.get_all_symbols()
        return SymbolListResponse(count=len(symbols), symbols=symbols[:100])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    start = req.start_date or date.today().replace(day=1)
    end = req.end_date or date.today()

    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            try:
                df = scheduler._do_market_fetch(current, req.symbols, triggered_by="manual_partial")
                total += len(df) if df is not None else 0
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"{current} 采集失败: {e}")
        current += timedelta(days=1)
    return {"message": f"采集完成，共获取 {total} 条记录"}

# ---------- 采集日志 ----------
@router.get("/logs")
async def get_fetch_logs(
    limit: int = Query(20, ge=1, le=100),
    scheduler=Depends(get_scheduler)
):
    """获取最近的行情采集日志"""
    logs = scheduler.get_recent_logs(limit)
    return {"logs": logs}