import re
from typing import List, Dict

class FormulaDependencyParser:
    # 公式中的引用语法：api('函数名').col('列名')
    PATTERN = r"api\('(\w+)'\)\.col\('(\w+)'\)"

    @classmethod
    def parse(cls, formula: str) -> List[Dict[str, str]]:
        """从公式字符串中提取所有 API 依赖"""
        if not formula:
            return []
        deps = []
        seen = set()
        for match in re.finditer(cls.PATTERN, formula):
            func_name = match.group(1)
            col_name = match.group(2)
            key = (func_name, col_name)
            if key not in seen:
                deps.append({'function_name': func_name, 'column_name': col_name})
                seen.add(key)
        return deps