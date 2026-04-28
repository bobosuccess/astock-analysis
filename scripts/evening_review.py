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
    """今日强势/弱势板块（东方财富行业涨幅榜前5）"""
    try:
        df = ak.stock_board_industry_name_em()
        df_sorted = df.sort_values("涨跌幅", ascending=False)

        lines_top = df_sorted.head(5)
        lines_bottom = df_sorted.tail(5)

        result_lines = ["强势板块:"]
        for _, r in lines_top.iterrows():
            chg = float(r["涨跌幅"])
            result_lines.append(f"  • {r['板块名称']}: {color_tag(chg)}")

        result_lines.append("弱势板块:")
        for _, r in lines_bottom.iterrows():
            chg = float(r["涨跌幅"])
            result_lines.append(f"  • {r['板块名称']}: {color_tag(chg)}")

        return "\n".join(result_lines)
    except Exception as e:
        return f"• 板块数据获取失败 ({e})"


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
    因子评分复盘（真实数据）
    读取 automation.yaml 中的因子配置，输出当前权重
    """
    lines = ["📐 因子权重配置（短线策略）", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    factors = [
        ("F1", "技术因子", 35, "K线形态/量价配合/均线排列"),
        ("F2", "市场因子", 20, "大盘成交量/北向资金"),
        ("F3", "情报因子", 25, "大V信号/政策消息"),
        ("F4", "板块因子", 20, "板块轮动/资金流向"),
        ("F5", "基本面", 0,  "业绩/估值（短线参考）"),
    ]

    for code, name, weight, note in factors:
        bar = "█" * (weight // 5) + "░" * (20 - weight // 5)
        lines.append(f"• {code} {name}: [{bar}] {weight}%")
        lines.append(f"  参考：{note}")

    lines.append("")
    lines.append("📌 复盘时手动填写命中率：")
    lines.append("  → 命中：F1/F3/F4 本周是否与行情方向一致？")
    lines.append("  → 偏差：记录本周权重偏离实际的程度")
    lines.append("")
    lines.append("💡 进化触发条件：命中率≥60%+样本≥5 → 权重+5%")

    return "\n".join(lines)


def get_trading_plan() -> str:
    """
    明日交易计划（基于今日行情数据）
    """
    lines = ["📋 明日交易计划", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    # 基于今日板块表现生成方向建议
    sector_df = None
    try:
        sector_df = ak.stock_board_industry_name_em()
    except Exception:
        pass

    if sector_df is not None:
        try:
            top_sector = sector_df.sort_values("涨跌幅", ascending=False).iloc[0]
            bottom_sector = sector_df.sort_values("涨跌幅", ascending=False).iloc[-1]
            top_chg = float(top_sector["涨跌幅"])
            bottom_chg = float(bottom_sector["涨跌幅"])

            if top_chg > 2.0:
                direction = "🟢 顺势做多主线板块"
            elif top_chg > 0.5:
                direction = "🟡 轻仓试探，聚焦主线"
            elif top_chg > -0.5:
                direction = "⚪ 震荡整理，观望为主"
            elif bottom_chg < -2.0:
                direction = "🔴 防御优先，等待情绪修复"
            else:
                direction = "🟠 控制仓位，等待方向明朗"

            lines.append(f"• 大盘方向参考: {direction}")
            lines.append(f"• 今日强势: {top_sector['板块名称']}({top_chg:+.2f}%)")
            lines.append(f"• 今日弱势: {bottom_sector['板块名称']}({bottom_chg:+.2f}%)")
        except Exception:
            lines.append("• 大盘方向参考: ⚠️ 数据处理失败")
            lines.append("• 建议：观望，等待明日开盘信号")
    else:
        lines.append("• 大盘方向参考: ⚠️ 数据获取失败")
        lines.append("• 建议：观望，等待明日开盘信号")

    # 北向资金参考
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        north_df = df[df["资金方向"] == "北向"]
        for _, row in north_df.iterrows():
            region = row.get("板块", row.get("类型", "?"))
            net = float(row.get("资金净流入", 0))
            sign = "净买入" if net >= 0 else "净卖出"
            lines.append(f"• 北向资金: {region} {sign} {abs(net):.1f}亿")
    except Exception:
        lines.append("• 北向资金: ⚠️ 数据获取失败")

    lines.append("")
    lines.append("• 方向: ___ / 首选标的: ___")
    lines.append("• 入场条件: 价格 + 成交量双重确认")
    lines.append("• 止损位: ___ 元（-___%）")
    lines.append("• 仓位: 轻仓试探 / 标准仓 / 重仓 ___")

    lines.append("")
    lines.append("⚠️ 前置确认清单:")
    lines.append("□ 09:25 开盘方向与今日收盘一致？")
    lines.append("□ 外盘（纳指/A50）无系统性利空？")
    lines.append("□ 大V晚间信号支持此方向？")
    lines.append("□ 持仓股无独立风险事件？")

    return "\n".join(lines)


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
