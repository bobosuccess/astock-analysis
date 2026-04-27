#!/usr/bin/env python3
"""
晚间复盘脚本
- 盘后数据分析
- 生成复盘报告
- 推送Server酱
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_reader import get_config, get_task_config
from push import push_to_wechat


def generate_evening_report():
    """生成晚间复盘报告"""
    config = get_config()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 读取自选股
    watchlist_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'watchlist.json')
    try:
        with open(watchlist_path, 'r', encoding='utf-8') as f:
            watchlist = json.load(f)
    except FileNotFoundError:
        watchlist = {"stocks": []}
    
    # 生成报告（简化版，实际应调用akshare获取数据）
    report = f"""
📊 晚间复盘报告 - {today}

【自选股概况】
共关注 {len(watchlist.get('stocks', []))} 只股票

【今日市场】
上证指数：待获取
深证成指：待获取
创业板指：待获取

【持仓分析】
待完善...

【明日关注】
1. 关注大盘走势
2. 跟踪自选股异动
3. 查看龙虎榜数据

---
生成时间：{datetime.now().strftime("%H:%M")}
"""
    
    return report


def main():
    """主函数"""
    print("=" * 50)
    print("🌙 晚间复盘脚本启动")
    print("=" * 50)
    
    # 检查任务开关
    task_config = get_task_config('evening_report')
    if not task_config.get('enabled', True):
        print("⏸️ 晚间复盘任务已关闭，跳过")
        return
    
    # 生成报告
    report = generate_evening_report()
    print("\n" + report)
    
    # 推送
    if os.getenv('SCKEY'):
        result = push_to_wechat("📊 晚间复盘", report)
        if result:
            print("✅ 推送成功")
        else:
            print("❌ 推送失败")
    else:
        print("⚠️ 未配置SCKEY，跳过推送")
    
    # 保存报告
    report_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"evening_report_{datetime.now().strftime('%Y%m%d')}.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"📄 报告已保存: {report_file}")
    
    print("\n✅ 晚间复盘完成")


if __name__ == '__main__':
    main()
