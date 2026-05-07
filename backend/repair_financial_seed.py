"""修复财务种子数据：清空并重建所有指标和依赖关系"""
import sys

sys.path.insert(0, 'backend')

from app.core.config import get_database_url
from app.core.data.financial.storage import FinancialStorage


def main():
    storage = FinancialStorage(get_database_url())
    session = storage.Session()

    try:
        # 1. 清空现有指标和依赖，保留API定义
        from app.core.data.financial.models import IndicatorDef, IndicatorApiDep
        session.query(IndicatorApiDep).delete()
        session.query(IndicatorDef).delete()
        session.commit()
        print("已清空旧的指标和依赖数据。")

        # 2. 定义完整的预设指标
        indicators = [
            # 利润表
            {"standard_field": "revenue", "chinese_name": "营业收入", "report_group": "income", "unit": "元",
             "formula": "Decimal(row.get('OPERATE_INCOME')) if row.get('OPERATE_INCOME') else None"},
            {"standard_field": "operating_profit", "chinese_name": "营业利润", "report_group": "income", "unit": "元",
             "formula": "Decimal(row.get('OPERATE_PROFIT')) if row.get('OPERATE_PROFIT') else None"},
            {"standard_field": "net_profit", "chinese_name": "净利润", "report_group": "income", "unit": "元",
             "formula": "Decimal(row.get('NETPROFIT')) if row.get('NETPROFIT') else None"},
            {"standard_field": "recurring_net_profit", "chinese_name": "扣非净利润", "report_group": "income",
             "unit": "元",
             "formula": "Decimal(row.get('PARENT_NETPROFIT')) if row.get('PARENT_NETPROFIT') else None"},

            # 资产负债表
            {"standard_field": "total_assets", "chinese_name": "总资产", "report_group": "balance", "unit": "元",
             "formula": "Decimal(row.get('TOTAL_ASSETS')) if row.get('TOTAL_ASSETS') else None"},
            {"standard_field": "total_liabilities", "chinese_name": "总负债", "report_group": "balance", "unit": "元",
             "formula": "Decimal(row.get('TOTAL_LIABILITIES')) if row.get('TOTAL_LIABILITIES') else None"},
            {"standard_field": "total_equity", "chinese_name": "股东权益", "report_group": "balance", "unit": "元",
             "formula": "Decimal(row.get('TOTAL_PARENT_EQUITY')) if row.get('TOTAL_PARENT_EQUITY') else None"},
            {"standard_field": "cash_and_equivalents", "chinese_name": "货币资金", "report_group": "balance",
             "unit": "元",
             "formula": "Decimal(row.get('CASH_DEPOSIT_PBC')) if row.get('CASH_DEPOSIT_PBC') else None"},

            # 现金流量表
            {"standard_field": "operating_cash_flow", "chinese_name": "经营现金流", "report_group": "cashflow",
             "unit": "元",
             "formula": "Decimal(row.get('NETCASH_OPERATE')) if row.get('NETCASH_OPERATE') else None"},

            # 主要财务指标
            {"standard_field": "roe", "chinese_name": "净资产收益率", "report_group": "indicator", "unit": "%",
             "formula": "Decimal(row.get('净资产收益率')) if row.get('净资产收益率') else None"},
            {"standard_field": "roa", "chinese_name": "总资产收益率", "report_group": "indicator", "unit": "%",
             "formula": "Decimal(row.get('总资产报酬率')) if row.get('总资产报酬率') else None"},
            {"standard_field": "gross_margin", "chinese_name": "毛利率", "report_group": "indicator", "unit": "%",
             "formula": "Decimal(row.get('营业毛利率')) if row.get('营业毛利率') else None"},
            {"standard_field": "net_margin", "chinese_name": "净利率", "report_group": "indicator", "unit": "%",
             "formula": "Decimal(row.get('营业净利率')) if row.get('营业净利率') else None"},
            {"standard_field": "eps", "chinese_name": "每股收益", "report_group": "indicator", "unit": "元",
             "formula": "Decimal(row.get('基本每股收益')) if row.get('基本每股收益') else None"},
        ]

        # 3. 插入指标并手动建立依赖
        from app.core.data.financial.models import ApiDef
        apis = {api.function_name: api for api in session.query(ApiDef).all()}
        print(f"已加载 {len(apis)} 个现有API定义。")

        for ind_data in indicators:
            # 插入指标
            ind = IndicatorDef(**ind_data)
            session.add(ind)
            session.flush()  # 获取 ind.id

            # 手动建立依赖：分析公式中引用的API列
            formula = ind_data.get("formula", "")
            # 简单的列名提取（与您的公式格式匹配）
            import re
            cols = re.findall(r"row\.get\('(\w+)'\)", formula)

            # 确定这个指标属于哪个API（报告期与API类型匹配）
            # 利润表指标默认关联 stock_profit_sheet_by_report_em
            # 资产负债表关联 stock_balance_sheet_by_report_em
            # 现金流量表关联 stock_cash_flow_sheet_by_report_em
            # 财务指标关联 stock_financial_analysis_indicator_em
            api_map = {
                "income": "stock_profit_sheet_by_report_em",
                "balance": "stock_balance_sheet_by_report_em",
                "cashflow": "stock_cash_flow_sheet_by_report_em",
                "indicator": "stock_financial_analysis_indicator_em"
            }
            api_func = api_map.get(ind_data["report_group"])
            if api_func and api_func in apis:
                for col in cols:
                    # 检查是否已存在，避免重复
                    existing = session.query(IndicatorApiDep).filter_by(
                        indicator_id=ind.id,
                        api_id=apis[api_func].id,
                        column_name=col
                    ).first()
                    if existing:
                        continue
                    # 插入依赖记录
                    dep = IndicatorApiDep(
                        indicator_id=ind.id,
                        api_id=apis[api_func].id,
                        column_name=col
                    )
                    session.add(dep)
                    print(f"  建立依赖: {ind.standard_field} -> {api_func}.{col}")
            else:
                print(f"  警告：未找到 {ind_data['report_group']} 对应的API，跳过依赖建立")

        print(f"成功插入 {len(indicators)} 个指标，并建立全部依赖关系。")
        session.commit()

    except Exception as e:
        session.rollback()
        print(f"修复失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()