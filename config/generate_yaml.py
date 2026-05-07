import openpyxl
import yaml
import os
import sys
import shutil
import time
from collections import OrderedDict


def load_old_params(yaml_path):
    """加载旧的参数文件，返回以 key 为键的字典"""
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        params_list = data.get('parameters', [])
        return {p['key']: p for p in params_list}
    return {}


def excel_to_params(excel_path):
    """从 Excel 读取参数，返回以 key 为键的字典"""
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb['Parameters']
    params_dict = OrderedDict()
    for row in ws.iter_rows(min_row=2, values_only=True):
        key, value, p_type, scope, desc, hot_reload = row
        if not key:
            continue

        # 类型转换，确保与 YAML 加载后的数据类型一致
        try:
            if p_type in ('int', 'float') and value is not None:
                value = eval(p_type)(value)
            elif p_type == 'bool':
                value = str(value).lower() in ('true', '1', 'yes')
            elif p_type in ('list', 'dict') and isinstance(value, str):
                try:
                    import ast
                    value = ast.literal_eval(value)
                except:
                    value = eval(value)  # 备用
        except Exception as e:
            print(f"警告：参数 [{key}] 的值转换失败，保留原始字符串。错误: {e}")

        param = {
            'key': key,
            'value': value,
            'type': p_type,
            'scope': scope,
            'description': desc,
            'hot_reloadable': str(hot_reload).lower() == 'true'
        }
        params_dict[key] = param
    return params_dict


def compare_params(old_params, new_params):
    """比较新旧参数，返回新增、删除、变更集合"""
    old_keys = set(old_params.keys())
    new_keys = set(new_params.keys())
    added = new_keys - old_keys
    removed = old_keys - new_keys
    common = old_keys & new_keys
    modified = []
    for key in sorted(common):
        old_param = old_params[key]
        new_param = new_params[key]
        diffs = {}
        fields_to_compare = ['value', 'type', 'scope', 'description', 'hot_reloadable']
        for field in fields_to_compare:
            old_val = old_param.get(field)
            new_val = new_param.get(field)
            if old_val != new_val:
                diffs[field] = {'旧值': old_val, '新值': new_val}
        if diffs:
            modified.append((key, diffs))
    return added, removed, modified


def backup_yaml(yaml_path, backup_dir):
    """如果 YAML 文件存在，则备份到指定目录"""
    if not os.path.exists(yaml_path):
        return None

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # 生成带时间戳的备份文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"parameters_yaml_{timestamp}.bak")

    shutil.copy2(yaml_path, backup_file)
    print(f"✅ 已备份旧版本至: {backup_file}")

    # 清理旧备份，只保留最近10个
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith('.bak')],
        reverse=True
    )
    for old_backup in backups[10:]:
        os.remove(os.path.join(backup_dir, old_backup))
        print(f"🗑️  已清理旧备份: {old_backup}")

    return backup_file


def generate_yaml_with_diff(excel_path, yaml_path):
    """主流程：备份旧 YAML -> 加载旧参数 -> 读取 Excel -> 比对 -> 生成新 YAML"""

    # 1. 备份旧版本
    backup_dir = os.path.join(os.path.dirname(yaml_path), "backups")
    backup_yaml(yaml_path, backup_dir)

    # 2. 加载旧参数
    old_params = load_old_params(yaml_path)

    # 3. 从 Excel 读取新参数
    new_params = excel_to_params(excel_path)

    # 4. 对比差异
    added, removed, modified = compare_params(old_params, new_params)

    # 5. 输出差异报告
    print("\n" + "=" * 50)
    print("      参数变更差异报告")
    print("=" * 50)
    has_diff = False
    if added:
        has_diff = True
        print(f"\n✅ 新增参数 ({len(added)}):")
        for key in sorted(added):
            print(f"   + {key}")
    if removed:
        has_diff = True
        print(f"\n❌ 删除参数 ({len(removed)}):")
        for key in sorted(removed):
            print(f"   - {key}")
    if modified:
        has_diff = True
        print(f"\n✏️  修改参数 ({len(modified)}):")
        for key, diffs in modified:
            print(f"   • {key}:")
            for field, change in diffs.items():
                print(f"      {field}: {change['旧值']} → {change['新值']}")
    if not has_diff:
        print("\n✅ 参数无任何变更。")
    print("=" * 50 + "\n")

    # 6. 生成新的 YAML 文件
    output_data = {
        'version': '3.0',
        'parameters': list(new_params.values())
    }
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"✅ 已生成新 YAML 文件: {yaml_path}")


if __name__ == '__main__':
    # 默认路径：脚本所在目录（即 config/）
    base_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file = os.path.join(base_dir, '系统参数配置表.xlsm')
    yaml_file = os.path.join(base_dir, 'parameters.yaml')

    if not os.path.exists(excel_file):
        print(f"❌ 错误：找不到 Excel 文件 {excel_file}")
        sys.exit(1)

    generate_yaml_with_diff(excel_file, yaml_file)