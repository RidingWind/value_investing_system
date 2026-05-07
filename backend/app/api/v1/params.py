from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime

router = APIRouter(prefix="/params", tags=["参数管理"])

# 依赖：从 app.state 获取参数服务
def get_param_service(request: Request):
    return request.app.state.param_service

# 响应模型
class ParamOut(BaseModel):
    key: str
    value: Any
    type: str
    scope: str
    description: str = ""
    hot_reloadable: bool = True

class ParamUpdate(BaseModel):
    value: Any
    reason: str = Field(..., min_length=1, description="修改原因")

class HistoryOut(BaseModel):
    key: str
    value: Any
    operator: str
    timestamp: float
    reason: Optional[str] = None

@router.get("", response_model=List[ParamOut])
async def list_params(param_service=Depends(get_param_service)):
    """获取所有已注册参数的最新值"""
    # 从 param_service._definitions 中获取所有 key，并读取当前值
    result = []
    for key, param_def in param_service._definitions.items():
        current_value = param_service.get(key)
        result.append(ParamOut(
            key=key,
            value=current_value,
            type=param_def.value_type.__name__,
            scope=param_def.scope.value,
            description=param_def.description,
            hot_reloadable=param_def.hot_reloadable
        ))
    return result

@router.put("/{key}")
async def update_param(key: str, update: ParamUpdate, request: Request, param_service=Depends(get_param_service)):
    """修改参数值（需填写原因），修改后自动记录审计日志并热推送"""
    # 从请求上下文中获取操作人（可从JWT token解析，此处先用占位）
    operator = getattr(request.state, 'username', 'web_admin')
    try:
        success = param_service.set(key, update.value, operator=operator)
        if not success:
            raise HTTPException(status_code=404, detail="参数不存在或不允许修改")
        return {"message": "更新成功", "key": key, "value": update.value}
    except TypeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{key}/history", response_model=List[HistoryOut])
async def get_param_history(key: str, limit: int = 50, param_service=Depends(get_param_service)):
    """获取参数变更历史（最近N条）"""
    history = param_service.get_history(key, limit)
    # 转为响应格式
    return [HistoryOut(**entry) for entry in history]