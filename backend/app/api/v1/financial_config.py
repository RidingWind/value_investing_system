from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional, Dict, Any
from app.core.data.financial.dynamic_adapter import DynamicFinancialAdapter


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

@router.post("/apis/{api_id}/refresh-columns")
async def refresh_api_columns(api_id: int, storage=Depends(get_storage)):
    api_def = storage.get_api_def(api_id)
    if not api_def:
        raise HTTPException(status_code=404, detail="API 定义不存在")

    # 构建适配器实例，param_service 可传 None（适配器内部未使用）
    adapter = DynamicFinancialAdapter(storage, param_service=None)

    # 候选股票列表（可根据实际调整）
    candidates = [
        ("000001.SZ", "20260331"),
        ("600519.SH", "20251231"),
        ("000001.SZ", "20251231"),
    ]

    # 临时移除日期筛选，确保获得所有列
    saved_date_column = api_def.date_column
    api_def.date_column = ''   # 空字符串会让筛选跳过

    last_error = None
    try:
        for sym, period in candidates:
            try:
                df = adapter._call_api(api_def, sym, period)
                if df is not None and not df.empty:
                    columns = df.columns.tolist()
                    # 恢复后更新数据库
                    api_def.date_column = saved_date_column
                    storage.save_api_def({"id": api_id, "output_columns": columns})
                    return {"columns": columns}
            except Exception as e:
                last_error = e
                continue

        # 所有候选都失败
        error_msg = "无法获取样例数据"
        if last_error:
            error_msg += f": {last_error}"
        raise HTTPException(status_code=404, detail=error_msg)
    finally:
        # 确保恢复原来的日期列
        api_def.date_column = saved_date_column

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
    # 移除不应由前端更新的自动管理字段
    for field in ["created_at", "updated_at"]:
        data.pop(field, None)

    deps = data.pop("deps", None)   # 提取依赖列表
    indicator_id = storage.save_indicator(data, deps=deps)  # 原有的保存指标（会自动解析 formula 更新依赖）
    # # 如果前端明确传递了 deps，则用新依赖覆盖自动解析的依赖
    # if deps is not None:
    #     storage.update_indicator_deps(indicator_id, deps)
    return {"id": indicator_id}

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

@router.put("/indicators/{indicator_id}/deps")
async def update_indicator_deps(indicator_id: int, deps: list, storage=Depends(get_storage)):
    storage.update_indicator_deps(indicator_id, deps)
    return {"message": "依赖更新成功"}