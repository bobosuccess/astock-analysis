#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📋 晚间复盘脚本
触发时间: 每天20:00 (北京时间)
功能：交易计划 + 持仓复盘 + 明日预判
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_reader import is_enabled, is_push_enabled
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def get_review_date():
    """
    计算复盘日期
    - 20:00定时运行 → 当天（已收盘）
    - 早上手动触发 → 昨天（当天未开盘）
    规则：北京时间 09:30 前视为"昨天"，之后视为"今天"
    """
    beijing = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing)
    cutoff = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < cutoff:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")
from push import serverchan_push


def get_portfolio_review():
    """
    持仓复盘
    TODO: 接入持仓数据或用户输入
    """
    return """📊 持仓复盘
━━━━━━━━━━━━━━━━━
• 标的A: 持有中，+2.3%
• 标的B: 持有中，-0.8%
• 今日操作: 无

💡 复盘思考:
- 主力行为是否符合预期?
- 因子信号是否触发?"""


def get_trading_plan():
    """
    明日交易计划
    TODO: 根据当日信号生成
    """
    return """📋 明日计划
━━━━━━━━━━━━━━━━━
• 观察标的: 待定
• 入场条件: 待定
• 止损位: 待定

⚠️ 前置条件:
- 晚间简报情报是否支持?"""


def main():
    if not is_enabled("evening_report"):
        print("[跳过] 晚间复盘开关已关闭")
        return

    print("=" * 50)
    print("执行晚间复盘 (20:00)...")
    print("=" * 50)

    # 1. 持仓复盘
    portfolio = get_portfolio_review()

    # 2. 交易计划
    plan = get_trading_plan()

    # 3. 组装复盘内容
    review_date = get_review_date()
    content = """📋 晚间复盘 | {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{portfolio}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{plan}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 复盘完成
📝 记得填写操盘日志""".format(
        date=review_date,
        portfolio=portfolio,
        plan=plan
    )

    # 推送
    if is_push_enabled():
        serverchan_push("📋 晚间复盘", content)

    print("✅ 晚间复盘已完成")
    print("\n" + content)


if __name__ == "__main__":
    main()
