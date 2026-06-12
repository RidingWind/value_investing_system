"""财务子系统预设数据（API 定义、指标定义）

包含两套：
    1. online 版：依赖 akshare 的实时接口（需要外网 + akshare 安装）
    2. mock 版：离线数据源，返回稳定构造的样例数据（无外网也可使用）

两套数据并存：调用 ``GET /financial/summary`` 时会先尝试 online 版，
若其采集失败（无 akshare / 无外网）则由 ``DynamicFinancialAdapter`` 自动
返回空 DataFrame，系统仍能完成整个流程；而 mock 版在任何环境下都能
给出确定性结果，适合端到端测试。
"""


def seed_preset_data(storage):
    # ------- online API 定义（akshare） -------
    online_apis = [
        {
            "source": "akshare",
            "function_name": "stock_profit_sheet_by_report_em",
            "chinese_name": "利润表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "akshare",
            "function_name": "stock_balance_sheet_by_report_em",
            "chinese_name": "资产负债表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "akshare",
            "function_name": "stock_cash_flow_sheet_by_report_em",
            "chinese_name": "现金流量表（东方财富-按报告期）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "akshare",
            "function_name": "stock_financial_analysis_indicator_em",
            "chinese_name": "财务指标（东方财富）",
            "input_params": {"symbol": "{em_symbol}"},
            "date_column": "日期",
        },
    ]
    for api in online_apis:
        storage.save_api_def(api)

    # ------- mock API 定义（离线可用） -------
    mock_apis = [
        {
            "source": "mock",
            "function_name": "mock_profit_sheet",
            "chinese_name": "[离线] 利润表",
            "input_params": {"symbol": "{symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "mock",
            "function_name": "mock_balance_sheet",
            "chinese_name": "[离线] 资产负债表",
            "input_params": {"symbol": "{symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "mock",
            "function_name": "mock_cash_flow_sheet",
            "chinese_name": "[离线] 现金流量表",
            "input_params": {"symbol": "{symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        },
        {
            "source": "mock",
            "function_name": "mock_financial_indicators",
            "chinese_name": "[离线] 财务指标",
            "input_params": {"symbol": "{symbol}"},
            "date_column": "日期",
        },
    ]
    for api in mock_apis:
        storage.save_api_def(api)

    # ------- 指标定义 -------
    # 注意：公式里写的是 api('xxx').col('yyy')，IndicatorEngine 会
    #       将其翻译为对真实 row 列的取值（见 indicator_engine.py）。
    #       对于 mock 模式，列名与 online 版保持一致（OPERATE_INCOME 等），
    #       因此同一个公式能同时支持 online 与 mock。
    indicator_presets = [
        {
            "standard_field": "revenue",
            "chinese_name": "营业收入",
            "report_group": "income",
            "unit": "元",
            "formula": "api('stock_profit_sheet_by_report_em').col('OPERATE_INCOME')",
        },
        {
            "standard_field": "net_profit",
            "chinese_name": "净利润",
            "report_group": "income",
            "unit": "元",
            "formula": "api('stock_profit_sheet_by_report_em').col('NETPROFIT')",
        },
        {
            "standard_field": "total_assets",
            "chinese_name": "总资产",
            "report_group": "balance",
            "unit": "元",
            "formula": "api('stock_balance_sheet_by_report_em').col('TOTAL_ASSETS')",
        },
        {
            "standard_field": "total_liabilities",
            "chinese_name": "总负债",
            "report_group": "balance",
            "unit": "元",
            "formula": "api('stock_balance_sheet_by_report_em').col('TOTAL_LIABILITIES')",
        },
        {
            "standard_field": "roe",
            "chinese_name": "净资产收益率",
            "report_group": "indicator",
            "unit": "%",
            "formula": "float(api('stock_financial_analysis_indicator_em').col('净资产收益率')) if api('stock_financial_analysis_indicator_em').col('净资产收益率') else None",
        },
        {
            "standard_field": "eps",
            "chinese_name": "每股收益",
            "report_group": "indicator",
            "unit": "元",
            "formula": "api('stock_financial_analysis_indicator_em').col('基本每股收益')",
        },
        # ------- 离线可用的镜像指标（只依赖 mock_* API） -------
        {
            "standard_field": "mock_revenue",
            "chinese_name": "[离线] 营业收入",
            "report_group": "income",
            "unit": "元",
            "formula": "api('mock_profit_sheet').col('OPERATE_INCOME')",
        },
        {
            "standard_field": "mock_net_profit",
            "chinese_name": "[离线] 净利润",
            "report_group": "income",
            "unit": "元",
            "formula": "api('mock_profit_sheet').col('NETPROFIT')",
        },
        {
            "standard_field": "mock_total_assets",
            "chinese_name": "[离线] 总资产",
            "report_group": "balance",
            "unit": "元",
            "formula": "api('mock_balance_sheet').col('TOTAL_ASSETS')",
        },
        {
            "standard_field": "mock_roe",
            "chinese_name": "[离线] 净资产收益率",
            "report_group": "indicator",
            "unit": "%",
            "formula": "api('mock_financial_indicators').col('净资产收益率')",
        },
    ]
    for ind in indicator_presets:
        storage.save_indicator(ind)
