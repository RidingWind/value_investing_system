import os

# 定义目录和文件的路径（相对于脚本所在目录）
STRUCTURE = {
    "backend": {
        "app": {
            "__init__.py": "",
            "main.py": '''from fastapi import FastAPI

app = FastAPI(title="价值投资自动化选股系统", version="3.0")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
''',
            "core": {
                "__init__.py": "",
                "config.py": '''import os
import yaml
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    database_url: str = "postgresql://user:pass@localhost/vinvest"

    class Config:
        env_file = ".env"

def load_yaml_config(path: str = "config/default_config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

settings = Settings()
''',
                "params": {
                    "__init__.py": "",
                    "service.py": '''from abc import ABC, abstractmethod
from typing import Any, List, Callable
from dataclasses import dataclass
from enum import Enum

class ParamScope(Enum):
    BUSINESS = "business"
    TECHNICAL = "technical"

@dataclass
class ParameterDef:
    key: str
    scope: ParamScope
    default_value: Any
    value_type: type
    description: str = ""
    validator: Callable = None
    hot_reloadable: bool = True

class ParameterService(ABC):
    @abstractmethod
    def register(self, param_def: ParameterDef):
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, operator: str = "system") -> bool:
        pass

    @abstractmethod
    def subscribe(self, keys: List[str], callback: Callable):
        pass
''',
                    "redis_impl.py": "# Redis实现（待完善）\n",
                    "definitions.py": "# 参数注册定义（待完善）\n",
                },
                "data": {
                    "__init__.py": "",
                },
                # 其他 core 子模块可按需扩展
            },
            "models": {
                "__init__.py": "",
            },
            "api": {
                "v1": {
                    "__init__.py": "",
                }
            },
            "services": {
                "__init__.py": "",
            },
            "utils": {
                "__init__.py": "",
            },
        },
        "requirements.txt": '''fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.10
redis==5.2.0
apscheduler==3.10.4
pandas==2.2.3
numpy==2.1.3
tushare==1.4.9
akshare==1.14.98
baostock==0.8.8
yfinance==0.2.48
transformers==4.46.0
sentence-transformers==3.2.0
chromadb==0.5.18
pydantic==2.9.2
python-dotenv==1.0.1
pyyaml==6.0.2
''',
        ".env": '''# 环境变量配置文件
REDIS_HOST=localhost
REDIS_PORT=6379
DATABASE_URL=postgresql://user:password@localhost/vinvest
''',
    },
    "config": {
        "default_config.yaml": '''# 默认配置文件
redis:
  host: localhost
  port: 6379

data:
  tushare_token: ""
  primary_source: tushare
  backup_sources: ["akshare", "baostock"]
  market_cron: "30 15 * * 1-5"

knowledge:
  vector_db_path: "./chroma_db"
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2"

backtest:
  commission: 0.0003
  slippage: 0.001

portfolio:
  initial_capital: 100000
  cash_permanent_floor: 0.05

output:
  report_dir: "./reports"
''',
    },
    "README.md": "# 价值投资自动化选股与组合管理系统\n\n## 项目结构\n\n```\nvalue_investing_system/\n├── backend/          # 后端 FastAPI 应用\n├── config/           # 配置文件\n└── README.md\n```\n\n## 快速开始\n\n1. 创建虚拟环境并安装依赖：\n```bash\ncd backend\npython -m venv venv\nsource venv/bin/activate  # Windows: venv\\Scripts\\activate\npip install -r requirements.txt\n```\n\n2. 运行开发服务器：\n```bash\npython -m app.main\n```\n\n访问 http://127.0.0.1:8000/docs 查看 API 文档。\n",
}


def create_structure(base_path, structure):
    for name, content in structure.items():
        path = os.path.join(base_path, name)
        if isinstance(content, dict):
            # 是目录
            os.makedirs(path, exist_ok=True)
            create_structure(path, content)
        else:
            # 是文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已创建文件: {path}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    create_structure(base_dir, STRUCTURE)
    print("\n✅ 项目目录结构创建完成！")