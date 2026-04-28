#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📋 晚间复盘脚本
触发时间: 每天20:00 (北京时间)
功能：持仓盈亏复盘 + 因子评分 + 明日交易计划
"""

import sys, io
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Windows PowerShell UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from config_reader import is_enabled, is_push_enabled, get_portfolio
from push import serverchan_push


def color_tag(val: float) -> str:
    if val > 0:
        return f"🔴 +{val:.2f}%"
    elif val < 0:
        return f"🟢 {val:.2f}%"
    return "⚪ 平"


def get_review_date() -> str:
    """计算复盘日期（09:30前=昨天，09:30后=当天）"""
    beijing = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing)
    cutoff = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < cutoff:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def get_market_review() -> str:
    """今日指数收盘"""
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
        rows = df[df["名称"].isin(targets)]
        lines = [f"• {r['名称']}: {r['最新价']:.2f} {color_tag(r['涨跌幅'])}"
                 for _, r in rows.iterrows()]
        return "\n".join(lines) if lines else "• 暂无数据"
    except Exception:
        return "• 数据获取失败"


def get_hot_sectors() -> str:
    """今日强势板块（申万行业涨幅榜前5）"""
    try:
        df = ak.sw_index_third_info()
        df_sorted = df.sort_values("涨跌幅", ascending=False).head(5)
        lines = [f"• {r['行业名称']}: {color_tag(r['涨跌幅'])}"
                 for _, r in df_sorted.iterrows()]
        return "\n".join(lines) if lines else "• 暂无数据"
    except Exception:
        return "• 板块数据获取失败"


def get_single_stock_price(code: str) -> tuple:
    """获取单只股票实时价格 (最新价, 涨跌幅)"""
    try:
        # 统一加后缀：沪市=1， 深市=0
        symbol = f"{code}.SH" if code.startswith(('6', '9')) else f"{code}.SZ"
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return float(row.iloc[0]["最新价"]), float(row.iloc[0]["涨跌幅"])
    except Exception:
        pass
    return None, None


def get_portfolio_review() -> str:
    """
    持仓复盘（自动读取 automation.yaml 配置）
    若未配置持仓，显示提示；已配置则显示盈亏
    """
    positions = get_portfolio()

    if not positions:
        return """📊 持仓复盘
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 未配置持仓
→ 请在 automation.yaml 的 portfolio.positions 添加你的持仓
→ 示例：
  positions:
    - code: "000001"
      name: "平安银行"
      shares: 1000
      cost: 12.50
      direction: "long"

💡 复盘思考:
1. 今日涨跌是否符合预期方向？
2. 五因子信号是否触发（F1技术/F3情报权重更高）？
3. 主力筹码是否有异动？"""

    lines = ["📊 持仓复盘", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    total_pnl = 0.0
    total_cost = 0.0

    for p in positions:
        code = p.get("code", "")
        name = p.get("name", code)
        shares = p.get("shares", 0)
        cost = p.get("cost", 0.0)
        direction = p.get("direction", "long")
        reason = p.get("reason", "")

        current_price, chg_pct = get_single_stock_price(code)

        if current_price is not None:
            if direction == "long":
                pnl_pct = (current_price - cost) / cost * 100
                pnl_amt = (current_price - cost) * shares
            else:  # short
                pnl_pct = (cost - current_price) / cost * 100
                pnl_amt = (cost - current_price) * shares

            total_cost += cost * shares
            total_pnl += pnl_amt

            pnl_tag = f"🔴 +{pnl_pct:.1f}%" if pnl_pct >= 0 else f"🟢 {pnl_pct:.1f}%"
            dir_tag = "多" if direction == "long" else "空"
            lines.append(
                f"• {name}({code}) [{dir_tag}]"
            )
            lines.append(f"  现价: {current_price:.2f} {color_tag(chg_pct)}")
            lines.append(f"  持仓: {shares}股 | 成本: {cost:.2f} | {pnl_tag}")
            if reason:
                lines.append(f"  理由: {reason}")
        else:
            lines.append(f"• {name}({code}) [{'多' if direction == 'long' else '空'}]")
            lines.append(f"  持仓: {shares}股 | 成本: {cost:.2f} | ⚠️价格获取失败")

    # 汇总
    if total_cost > 0:
        total_pnl_pct = total_pnl / total_cost * 100
        pnl_tag = f"🔴 总盈亏 +{total_pnl_pct:.1f}%" if total_pnl_pct >= 0 else f"🟢 总盈亏 {total_pnl_pct:.1f}%"
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"• 总盈亏: {'+' if total_pnl >= 0 else ''}{total_pnl:.0f}元 | {pnl_tag}")

    lines.append("")
    lines.append("💡 复盘思考:")
    lines.append("1. 今日涨跌是否符合预期方向？")
    lines.append("2. 五因子信号是否触发？")
    lines.append("3. 主力筹码是否有异动？")

    return "\n".join(lines)


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
    """明日交易计划"""
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
    if not is_enabled("evening_review"):
        print("[跳过] 晚间复盘开关已关闭 (master_switch=false)")
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
