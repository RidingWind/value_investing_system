import json

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Optional, Dict, Any


router = APIRouter(prefix="/financial/config", tags=["财务数据配置"])

def get_storage(request: Request):
    return request.app.state.financial_storage

# ---------- API 管理 ----------
@router.get("/apis")
async def list_apis(storage=Depends(get_storage)):
    return [a.__dict__ for a in storage.get_all_api_defs()]

@router.post("/apis")
async def save_api(data: Dict[str, Any], storage=Depends(get_storage)):
    return {"id": storage.save_api_def(data)}

@router.delete("/apis/{api_id}")
async def delete_api(api_id: int, storage=Depends(get_storage)):
    affected = storage.get_affected_indicators(api_id)
    storage.delete_api_def(api_id)
    return {"message": "删除成功", "affected_indicators": affected}

@router.post("/apis/probe")
async def probe_api_columns(function_name: str, params_json: str = "{}", storage=Depends(get_storage)):
    import akshare as ak
    import json
    func = getattr(ak, function_name, None)
    if not func:
        raise HTTPException(status_code=404, detail="函数不存在")
    kwargs = json.loads(params_json)
    df = func(**kwargs)
    if df is None or df.empty:
        return {"columns": []}
    return {"columns": list(df.columns)}

# ---------- 指标管理 ----------
@router.get("/indicators")
async def list_indicators(report_group: Optional[str] = None, storage=Depends(get_storage)):
    return [i.__dict__ for i in storage.get_all_indicators(report_group)]

@router.post("/indicators")
async def save_indicator(data: Dict[str, Any], storage=Depends(get_storage)):
    return {"id": storage.save_indicator(data)}

@router.delete("/indicators/{indicator_id}")
async def delete_indicator(indicator_id: int, storage=Depends(get_storage)):
    storage.delete_indicator(indicator_id)
    return {"message": "删除成功"}

@router.get("/indicators/{indicator_id}/deps")
async def get_indicator_deps(indicator_id: int, storage=Depends(get_storage)):
    return storage.get_indicator_deps(indicator_id)

# ---------- 依赖分析 ----------
@router.get("/deps/affected/{api_id}")
async def get_affected_indicators(api_id: int, storage=Depends(get_storage)):
    return storage.get_affected_indicators(api_id)
