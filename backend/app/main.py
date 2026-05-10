import sys
from pathlib import Path

# 将 backend 目录加入 sys.path，确保 app 包能被找到
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import logging
# import asyncio
# from app.api.v1.search import _load_cache   # 导入预热函数
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import load_infra_config
from app.core.plugins.param_plugin import ParamPlugin
from app.core.plugins.market_plugin import MarketPlugin
from app.core.plugins.financial_plugin import FinancialPlugin
from app.api.v1.search import router as search_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 插件实例化（模块级别，唯一实例）
param_plugin = ParamPlugin()
market_plugin = MarketPlugin()
financial_plugin = FinancialPlugin()

@asynccontextmanager
async def lifespan(app: FastAPI):
    infra_config = load_infra_config()

    # 1. 初始化参数服务（内部创建，不需要外部 param_service）
    param_plugin.init_app(app, infra_config)
    param_service = app.state.param_service

    # 2. 行情子系统
    market_plugin.init_app(app, infra_config, param_service)

    # 3. 财务子系统
    financial_plugin.init_app(app, infra_config, param_service)

    # # 4. 初始化搜索列表
    # # 预热股票搜索缓存（异步包装同步任务，避免阻塞事件循环）
    # loop = asyncio.get_running_loop()
    # await loop.run_in_executor(None, _load_cache)

    yield

app = FastAPI(title="价值投资自动化选股系统", version="3.0", lifespan=lifespan)

# CORS（类型警告忽略）
app.add_middleware(  # type: ignore[arg-type]
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api/v1")

# 注册路由
param_plugin.register_routers(app)
market_plugin.register_routers(app)
financial_plugin.register_routers(app)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)