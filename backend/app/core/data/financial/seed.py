"""财务子系统预设数据（API 定义、指标定义）"""
def seed_preset_data(storage):
    # 预设 API
    api_presets = [
        {
            "source": "akshare",
            "function_name": "stock_profit_sheet_by_report_em",
            "chinese_name": "利润表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'"
        },
        {
            "source": "akshare",
            "function_name": "stock_balance_sheet_by_report_em",
            "chinese_name": "资产负债表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'"
        },
        {
            "source": "akshare",
            "function_name": "stock_cash_flow_sheet_by_report_em",
            "chinese_name": "现金流量表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'"
        },
        {
            "source": "akshare",
            "function_name": "stock_financial_analysis_indicator_em",
            "chinese_name": "财务指标（东方财富）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "日期"
        }
    ]
    for api in api_presets:
        storage.save_api_def(api)

    # 预设指标（部分示例，实际需从文档补充完整）
    indicator_presets = [
        {
            "standard_field": "revenue",
            "chinese_name": "营业收入",
            "report_group": "income",
            "unit": "元",
            "formula": "api('stock_profit_sheet_by_report_em').col('OPERATE_INCOME')"
        },
        {
            "standard_field": "net_profit",
            "chinese_name": "净利润",
            "report_group": "income",
            "unit": "元",
            "formula": "api('stock_profit_sheet_by_report_em').col('NETPROFIT')"
        },
        {
            "standard_field": "total_assets",
            "chinese_name": "总资产",
            "report_group": "balance",
            "unit": "元",
            "formula": "api('stock_balance_sheet_by_report_em').col('TOTAL_ASSETS')"
        },
        {
            "standard_field": "total_liabilities",
            "chinese_name": "总负债",
            "report_group": "balance",
            "unit": "元",
            "formula": "api('stock_balance_sheet_by_report_em').col('TOTAL_LIABILITIES')"
        },
        {
            "standard_field": "roe",
            "chinese_name": "净资产收益率",
            "report_group": "indicator",
            "unit": "%",
            "formula": "float(api('stock_financial_analysis_indicator_em').col('净资产收益率')) if api('stock_financial_analysis_indicator_em').col('净资产收益率') else None"
        },
        {
            "standard_field": "eps",
            "chinese_name": "每股收益",
            "report_group": "indicator",
            "unit": "元",
            "formula": "api('stock_financial_analysis_indicator_em').col('基本每股收益')"
        }
    ]
    for ind in indicator_presets:
        storage.save_indicator(ind)