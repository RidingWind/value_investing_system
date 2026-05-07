from app.core.config import get_database_url
from app.core.data.financial.storage import FinancialStorage

storage = FinancialStorage(get_database_url())
session = storage.Session()

# 清空旧依赖
from app.core.data.financial.models import IndicatorApiDep, IndicatorDef, ApiDef

session.query(IndicatorApiDep).delete()

def main():
    # 获取所有指标
    indicators = session.query(IndicatorDef).all()
    apis = {api.function_name: api for api in session.query(ApiDef).all()}

    # 为每个指标重新建立依赖
    for ind in indicators:
        # 提取公式中引用的列名
        import re
        cols = re.findall(r"row\.get\(\"(\w+)\"\)", ind.formula or "")
        # 根据 report_group 确定对应的 API
        api_map = {
            "income": "stock_profit_sheet_by_report_em",
            "balance": "stock_balance_sheet_by_report_em",
            "cashflow": "stock_cash_flow_sheet_by_report_em",
            "indicator": "stock_financial_analysis_indicator_em"
        }
        api_func = api_map.get(ind.report_group)
        if api_func and api_func in apis:
            for col in set(cols):
                dep = IndicatorApiDep(
                    indicator_id=ind.id,
                    api_id=apis[api_func].id,
                    column_name=col
                )
                session.add(dep)
    session.commit()
    print("依赖关系重建完成。")

if __name__ == '__main__':
    main()