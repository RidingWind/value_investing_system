from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    database_url: str = "postgresql://user:pass@localhost/vinvest"

    class Config:
        env_file = ".env"

def get_project_root() -> Path:
    """自动查找项目根目录（包含 config/default_config.yaml 的目录）"""
    current = Path(__file__).resolve().parent
    # 向上查找，直到找到 config 目录
    while current.parent != current:
        if (current / "config" / "default_config.yaml").exists():
            print(f"[DEBUG] 项目根目录 = {current}")
            return current
        current = current.parent
    raise FileNotFoundError("未找到项目根目录，请确保 config/default_config.yaml 存在")

def load_yaml_config(path: str = "config/default_config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ---------- 加载基础设施配置 ----------
def load_infra_config() -> dict:
    config_path = get_project_root() / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_database_url() -> str:
    """返回处理后的数据库连接URL，自动将相对路径转换为绝对路径"""
    config = load_infra_config()
    db_url = config.get("database", {}).get("url", "sqlite:///./data/vinvest.db")
    print(f"[DEBUG] 原始 database.url = {db_url}")

    if db_url.startswith("sqlite:///./"):
        relative_path = db_url[len("sqlite:///./"):]
        project_root = get_project_root()
        abs_db_path = project_root / relative_path
        # 确保 data 目录存在
        abs_db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{abs_db_path}"
        print(f"[DEBUG] 转换后绝对路径 = {db_url}")

    return db_url

settings = Settings()
