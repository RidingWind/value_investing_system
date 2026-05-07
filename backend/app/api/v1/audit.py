from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Any
import json

router = APIRouter(prefix="/audit", tags=["审计日志"])


class AuditLogOut(BaseModel):
    key: str
    value: Any
    operator: str
    timestamp: float
    reason: Optional[str] = None


class AuditLogResponse(BaseModel):
    items: List[AuditLogOut]
    total: int
    page: int
    page_size: int


@router.get("/logs", response_model=AuditLogResponse)
async def get_audit_logs(
        request: Request,
        key: Optional[str] = Query(None),
        operator: Optional[str] = Query(None),
        start_time: Optional[float] = Query(None),
        end_time: Optional[float] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100)
):
    """全局审计日志查询，支持多条件筛选和分页"""
    param_service = request.app.state.param_service
    # 从Redis审计列表中获取所有日志（limit可根据实际情况调整）
    all_logs = param_service.redis.lrange(param_service.audit_log_key, 0, -1)

    items = []
    for log_str in reversed(all_logs):  # 最新在前
        entry = json.loads(log_str)
        # 过滤条件
        if key and entry.get("key") != key:
            continue
        if operator and entry.get("operator") != operator:
            continue
        if start_time and entry.get("timestamp", 0) < start_time:
            continue
        if end_time and entry.get("timestamp", 0) > end_time:
            continue
        items.append(AuditLogOut(
            key=entry.get("key", ""),
            value=entry.get("value"),
            operator=entry.get("operator", "unknown"),
            timestamp=entry.get("timestamp", 0),
            reason=entry.get("reason")
        ))

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return AuditLogResponse(
        items=items[start:end],
        total=total,
        page=page,
        page_size=page_size
    )