"""测试多数据源切换"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config_reader import get_data_source

def test_data_sources():
    print("=== 多数据源测试 ===\n")

    # 测试实时数据源
    sources = get_data_source("realtime")
    print(f"实时数据源优先级: {sources}")

    # 测试akshare
    print("\n--- 测试 akshare ---")
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        idx = df[df['名称'].isin(['上证指数', '深证成指', '创业板指'])]
        print(idx[['名称', '最新价', '涨跌幅']].to_string(index=False))
        print("✅ akshare 正常")
    except Exception as e:
        print(f"❌ akshare 失败: {e}")

    # 测试 baostock
    print("\n--- 测试 baostock ---")
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_history_k_data_plus(
            "sh.000001",
            "date,code,open,high,low,close,volume",
            start_date='2026-04-25',
            end_date='2026-04-25'
        )
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        bs.logout()
        print(data_list)
        print("✅ baostock 正常")
    except Exception as e:
        print(f"❌ baostock 失败: {e}")


if __name__ == "__main__":
    test_data_sources()
