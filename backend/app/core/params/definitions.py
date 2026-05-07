"""
参数定义注册模块
从 config/parameters.yaml 加载参数清单，并注册到参数服务
"""
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.core.params.service import ParameterDef, ParamScope, ParameterService


def _str_to_type(type_name: str) -> type:
    """将字符串类型名转换为 Python 类型"""
    type_mapping = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }
    return type_mapping.get(type_name, str)


def _parse_scope(scope_str: str) -> ParamScope:
    """解析参数字段"""
    if scope_str == "business":
        return ParamScope.BUSINESS
    elif scope_str == "technical":
        return ParamScope.TECHNICAL
    else:
        raise ValueError(f"未知的参数范围: {scope_str}")


def load_parameters_from_yaml(yaml_path: str = None) -> List[Dict[str, Any]]:
    """
    从 YAML 文件加载参数定义列表。
    默认路径为项目根目录下的 config/parameters.yaml
    """
    if yaml_path is None:
        # 从当前文件向上查找项目根目录
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent  # 向上5级到 value_investing_system
        yaml_path = project_root / "config" / "parameters.yaml"
    else:
        yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"参数配置文件不存在: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    parameters = data.get("parameters", [])
    return parameters


def register_all_parameters(
    param_service: ParameterService,
    yaml_path: str = None,
    override_existing: bool = False
) -> None:
    """
    从 parameters.yaml 批量注册所有参数。

    Args:
        param_service: 参数服务实例
        yaml_path: 自定义 YAML 文件路径，默认使用 config/parameters.yaml
        override_existing: 是否覆盖 Redis 中已存在的参数值（默认不覆盖，保留已有值）
    """
    params_list = load_parameters_from_yaml(yaml_path)

    for item in params_list:
        key = item["key"]
        value = item["value"]
        type_name = item["type"]
        scope_str = item["scope"]
        description = item.get("description", "")
        hot_reloadable = item.get("hot_reloadable", True)

        # 类型转换
        value_type = _str_to_type(type_name)
        scope = _parse_scope(scope_str)

        # 可选：自定义校验器（针对特定参数可在此扩展）
        validator = None

        # 创建参数定义对象
        param_def = ParameterDef(
            key=key,
            scope=scope,
            default_value=value,
            value_type=value_type,
            description=description,
            validator=validator,
            hot_reloadable=hot_reloadable,
        )

        # 注册到参数服务
        param_service.register(param_def)

        # 如果需要强制覆盖 Redis 中的值，可以在这里调用 set
        # if override_existing:
        #     param_service.set(key, value, operator="system_init")