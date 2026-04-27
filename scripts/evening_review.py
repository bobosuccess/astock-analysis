#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📋 晚间复盘脚本
触发时间: 每天20:00 (北京时间)
功能：持仓复盘 + 因子评分 + 明日交易计划
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from config_reader import is_enabled, is_push_enabled
from push import serverchan_push


def color_tag(val: float) -> str:
    if val > 0:
        return f"🔴 +{val:.2f}%"
    elif val < 0:
        return f"🟢 {val:.2f}%"
    return "⚪ 平"


def get_review_date() -> str:
    """
    计算复盘日期
    - 20:00定时运行 → 当天（已收盘）
    - 早上手动触发 → 昨天（当天未开盘）
    """
    beijing = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing)
    cutoff = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < cutoff:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def get_market_review() -> str:
    """今日市场复盘（指数表现 + 热点板块）"""
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
        rows = df[df["名称"].isin(targets)]
        lines = []
        for _, row in rows.iterrows():
            lines.append(
                f"• {row['名称']}: {row['最新价']:.2f} {color_tag(row['涨跌幅'])}"
            )
        return "\n".join(lines) if lines else "• 暂无数据"
    except Exception as e:
        return f"• 数据获取失败"


def get_hot_sectors() -> str:
    """获取今日强势板块"""
    try:
        # 申万行业涨幅榜
        df = ak.sw_index_third_info()
        df_sorted = df.sort_values("涨跌幅", ascending=False).head(5)
        lines = []
        for _, row in df_sorted.iterrows():
            lines.append(
                f"• {row['行业名称']}: {color_tag(row['涨跌幅'])}"
            )
        return "\n".join(lines) if lines else "• 暂无数据"
    except Exception:
        return "• 板块数据获取失败"


def get_portfolio_review() -> str:
    """
    持仓复盘
    ⚠️ TODO: 替换为你的真实持仓数据
    格式参考：
    • 股票名称(代码): 持仓X手, 盈亏Y%, 持仓理由
    • 今日操作: 买入/卖出/持有不动
    """
    return """📊 持仓复盘
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 请在 automation.yaml 的 portfolio 字段填入你的持仓
⚠️ 或直接在个人作战台 持仓管理.md 中更新

示例格式：
• 宁德时代(300750): 持有100手, 今日+1.2%, 锂电池龙头
• 比亚迪(002594): 持有50手, 今日-0.5%, 新能源整车

💡 复盘思考:
1. 今日涨跌是否符合预期方向？
2. 五因子信号是否触发（F1技术/F3情报权重更高）？
3. 主力筹码是否有异动？"""


def get_factor_review() -> str:
    """
    因子评分复盘
    ⚠️ TODO: 对照今日行情，评估各因子命中情况
    """
    return """📐 因子评分复盘（今日）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• F1 技术因子: 命中率 ___% / 方向对否: ✓/✗
• F2 市场因子: 成交量判断对否: ✓/✗
• F3 情报因子: 大V观点验证: ✓/✗
• F4 板块因子: 板块轮动判断: ✓/✗
• F5 基本面因子: 业绩/估值验证: ✓/✗

📊 今日综合信心星级: ★☆☆☆☆"""


def get_trading_plan() -> str:
    """
    明日交易计划
    ⚠️ TODO: 晚间简报情报确认后再填写
    """
    return """📋 明日交易计划
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 方向: 多头 / 空头 / 观望（待情报确认）
• 首选标的: ___（理由：___）
• 入场条件: 价格达到 ___ 元 + 成交量放量
• 止损位: ___ 元（-___%）
• 仓位: ___ 成仓

⚠️ 前置条件:
□ 晚间简报情报支持此方向？
□ 外盘（纳指/原油）未出现系统性利空？
□ 今日复盘因子评分 ≥ 3星？"""


def main():
    if not is_enabled("evening_report"):
        print("[跳过] 晚间复盘开关已关闭")
        return

    print("=" * 50)
    print("📋 生成晚间复盘 (20:00)...")
    print("=" * 50)

    review_date = get_review_date()
    market = get_market_review()
    sectors = get_hot_sectors()
    portfolio = get_portfolio_review()
    factor_review = get_factor_review()
    plan = get_trading_plan()

    content = f"""📋 晚间复盘 | {review_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【今日指数收盘】
{market}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【今日强势板块】
{sectors}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{portfolio}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{factor_review}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{plan}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 复盘完成
📝 记得在操盘日志中记录决策过程"""

    print("\n" + content)

    if is_push_enabled():
        serverchan_push("📋 晚间复盘", content)
        print("\n✅ 已推送至微信")
    else:
        print("\n⚠️ 推送未启用")


if __name__ == "__main__":
    main()
