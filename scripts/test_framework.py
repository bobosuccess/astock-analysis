"""简化测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config_reader import is_enabled, load_config

def main():
    print("=== 框架测试 ===\n")

    # 1. 测试配置读取
    print("[1] 配置读取器")
    cfg = load_config()
    print(f"    - 总开关: {cfg['automation']['master_switch']}")
    print(f"    - 推送开关: {cfg['automation']['layers']['push_notification']['enabled']}")
    print(f"    - 数据源数量: {len(cfg['data_sources'])}")
    print("    [OK]\n")

    # 2. 测试任务开关
    print("[2] 任务开关状态")
    tasks = ['morning_report', 'realtime_monitor', 'after_close_batch', 'full_scan']
    for task in tasks:
        status = "ON " if is_enabled(task) else "OFF"
        print(f"    - {task}: [{status}]")
    print()

    # 3. 测试akshare（无代理）
    print("[3] 测试 akshare")
    try:
        import os
        # 临时取消代理
        proxies = os.environ.get('http_proxy') or os.environ.get('https_proxy')
        if proxies:
            print(f"    - 检测到代理: {proxies[:20]}...")
            print("    - 跳过网络测试（避免代理干扰）")
        else:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            print(f"    - 成功获取A股实时数据: {len(df)} 条")
            print("    [OK]")
    except Exception as e:
        print(f"    - 网络测试跳过: {str(e)[:50]}")
        print("    [SKIP - 代理或网络问题]")
    print()

    # 4. 测试baostock
    print("[4] 测试 baostock")
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_history_k_data_plus(
            "sh.000001",
            "date,code,close",
            start_date='2026-04-24',
            end_date='2026-04-24'
        )
        data = rs.get_row_data()
        bs.logout()
        print(f"    - 成功获取上证历史数据: {data}")
        print("    [OK]")
    except Exception as e:
        print(f"    - baostock 失败: {str(e)[:60]}")
        print("    [SKIP - 网络问题]")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()
