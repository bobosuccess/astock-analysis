#!/usr/bin/env python3
"""
自我总结脚本
- 分析当日操作
- 记录交易日志
- 生成改进建议
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_reader import get_config, get_task_config


def generate_summary():
    """生成自我总结"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    summary = f"""
📝 交易日志 - {today}

【今日操作】
- 买入：无
- 卖出：无
- 持仓调整：无

【情绪记录】
- 开盘情绪：待记录
- 盘中情绪：待记录
- 收盘情绪：待记录

【关键决策】
1. 今日无重大决策

【复盘反思】
- 做得好的：
- 需要改进：

【明日计划】
1. 关注大盘走势
2. 执行既定策略
3. 控制仓位风险

---
记录时间：{datetime.now().strftime("%H:%M")}
"""
    
    return summary


def main():
    """主函数"""
    print("=" * 50)
    print("📝 自我总结脚本启动")
    print("=" * 50)
    
    # 检查任务开关
    task_config = get_task_config('self_summary')
    if not task_config.get('enabled', True):
        print("⏸️ 自我总结任务已关闭，跳过")
        return
    
    # 生成总结
    summary = generate_summary()
    print("\n" + summary)
    
    # 保存到日志
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'reports', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"trading_log_{datetime.now().strftime('%Y%m')}.md")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(summary)
        f.write("\n---\n\n")
    
    print(f"📄 日志已追加: {log_file}")
    print("\n✅ 自我总结完成")


if __name__ == '__main__':
    main()
