from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import date

from app.core.data.financial.storage import FinancialStorage
from app.core.data.financial.scheduler import FinancialScheduler

router = APIRouter(prefix="/financial", tags=["财务数据管理"])

# ---------- 依赖项 ----------
def get_storage(request: Request) -> FinancialStorage:
    return request.app.state.financial_storage

def get_scheduler(request: Request) -> FinancialScheduler:
    return request.app.state.financial_scheduler


# ---------- 响应模型 ----------
class SummaryOut(BaseModel):
    income_records: int
    balance_records: int
    cashflow_records: int
    indicator_records: int

class SymbolRangeOut(BaseModel):
    symbol: str
    start_date: Optional[str]
    end_date: Optional[str]
    record_count: int

class FetchRequest(BaseModel):
    symbols: List[str]  # 股票代码列表
    quarters: int = 6  # 获取最近几季度数据

class FetchResult(BaseModel):
    message: str
    details: List[Dict]

class LogEntry(BaseModel):
    symbol: str
    periods: int
    stored: int
    timestamp: str

# ---------- 接口 ----------
@router.get("/range/{symbol}", response_model=SymbolRangeOut)
async def symbol_data_range(symbol: str, storage=Depends(get_storage)):
    """查询某只股票财务数据的报告期区间"""
    result = storage.get_symbol_range(symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="未找到该股票的财务数据")
    return SymbolRangeOut(**result)

@router.get("/summary")
async def financial_summary(storage=Depends(get_storage)):
    summary = storage.get_summary()
    return {
        "income_records": summary.get("income_records", 0),
        "balance_records": summary.get("balance_records", 0),
        "cashflow_records": summary.get("cashflow_records", 0),
        "indicator_records": summary.get("indicator_records", 0),
    }

@router.post("/fetch")
async def fetch_financials(req: FetchRequest, scheduler=Depends(get_scheduler)):
    details = []
    for sym in req.symbols:
        try:
            result = scheduler.fetch_one_stock(sym, req.quarters)
            details.append({"symbol": sym, "status": "success", "stored": result["total_stored"]})
        except Exception as e:
            details.append({"symbol": sym, "status": "error", "error": str(e)})
    return {"message": f"采集完成", "details": details}

@router.get("/logs", response_model=List[LogEntry])
async def fetch_logs(
        limit: int = Query(20, ge=1, le=100),
        scheduler=Depends(get_scheduler)
):
    """获取财务数据采集日志"""
    return scheduler.get_recent_logs(limit)