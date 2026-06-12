"""独立测试 AKShare 财务接口，打印实际返回的列名和样例数据"""
import akshare as ak
import pandas as pd
import baostock as bao

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)
pd.set_option('display.max_colwidth', 50)

def test_report_sina(code_str, report_type):
    """测试新浪报表接口"""
    stock = f"sz{code_str}" if not code_str.startswith('6') else f"sh{code_str}"
    print(f"\n{'='*60}")
    print(f"测试 stock_financial_report_sina: stock={stock}, symbol={report_type}")
    print(f"{'='*60}")
    try:
        df = ak.stock_financial_report_sina(stock=stock, symbol=report_type)
        print(f"形状: {df.shape}")
        print(f"\n列名:")
        for i, col in enumerate(df.columns):
            print(f"  [{i}] '{col}'")
        print(f"\n前2行数据:")
        print(df.head(2).to_string())
        return df
    except Exception as e:
        print(f"错误: {e}")
        return None

def test_financial_indicator(code_str):
    """测试财务指标接口"""
    print(f"\n{'='*60}")
    print(f"测试 stock_financial_analysis_indicator: symbol={code_str}")
    print(f"{'='*60}")
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code_str, start_year=2024)
        print(f"形状: {df.shape}")
        print(f"\n列名:")
        for i, col in enumerate(df.columns):
            print(f"  [{i}] '{col}'")
        print(f"\n前2行数据:")
        print(df.head(2).to_string())
        return df
    except Exception as e:
        print(f"错误: {e}")
        return None


def test_em(symbol):
    # df = ak.stock_balance_sheet_by_report_em('SH600000')
    # 测试函数是否存在
    print(hasattr(ak, 'stock_financial_analysis_indicator_em'))  # 应为 True

    # 测试调用并查看返回
    try:
        df = ak.stock_financial_analysis_indicator_em(symbol=symbol)
        print(type(df))
        if df is not None and not df.empty:
            print(df.head())
        else:
            print("返回空数据")
    except Exception as e:
        print(f"调用失败: {e}")

def test_bao(symbol):
    all_frames = []
    lg = bao.login()
    lg = bao.query_history_k_data_plus(
        'sz.000001',
        "date,open,high,low,close,volume,amount",
        start_date="2026-05-08", end_date="2026-05-08",frequency="d",adjustflag="2")
    if lg.error_code != '0':
        print("failed")
    data_list = []
    while lg.next():
        data_list.append(lg.get_row_data())
    if data_list:
        df_part = pd.DataFrame(data_list, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
        all_frames.append(df_part)
    print(all_frames)

def test_zh():
    try:
        df = ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20260508", end_date='20260508',adjust="qfq" )
        print(type(df))
    except Exception as e:
        print(e)

if __name__ == '__main__':
    # 测试 000001（平安银行）和 600000（浦发银行）
    for code in ['000001.SZ', '600000.SH']:
        # test_report_sina(code, '利润表')
        # test_report_sina(code, '资产负债表')
        # test_report_sina(code, '现金流量表')
        # test_financial_indicator(code)
        test_zh()