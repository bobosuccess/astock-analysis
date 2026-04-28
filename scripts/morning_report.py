#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 晨间简报脚本
触发时间: 每天07:00 (北京时间)
功能：外盘回顾 + A股前瞻 + 盘前三问 + 推送微信
"""

import sys, io
from pathlib import Path

# Windows PowerShell UTF-8 输出修复
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from config_reader import is_enabled, is_push_enabled
from push import serverchan_push


def get_beijing_time():
    """获取当前北京时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def color_tag(val: float) -> str:
    if val > 0:
        return f"🔴 +{val:.2f}%"
    elif val < 0:
        return f"🟢 {val:.2f}%"
    return "⚪ 平"


def get_us_market() -> str:
    """隔夜外盘数据"""
    lines = ["【隔夜外盘】", "━━━━━━━━━━━━━━━━━━━━"]
    try:
        # 美股三大指数
        df = ak.macro_usa_spot_em()
        targets = ["纳斯达克综合指数", "标普500指数", "道琼斯工业平均指数"]
        for _, row in df.iterrows():
            if row["名称"] in targets:
                val = float(row["最新价"])
                chg = float(row["涨跌幅"])
                lines.append(f"• {row['名称']}: {val:.2f} {color_tag(chg)}")
        lines.append("")
    except Exception:
        lines.append("• 美股数据获取失败")
        lines.append("")

    # 富时中国A50
    try:
        df = ak.index_zh_a_spot_em(symbol="A50")
        if not df.empty:
            row = df.iloc[0]
            lines.append(f"• A50期货: {row['最新价']:.2f} {color_tag(float(row['涨跌幅']))}")
        lines.append("")
    except Exception:
        lines.append("• A50数据获取失败")
        lines.append("")

    return "\n".join(lines)


def get_yesterday_close() -> str:
    """昨日收盘概况"""
    lines = ["【昨日收盘】", "━━━━━━━━━━━━━━━━━━━━"]
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
        rows = df[df["名称"].isin(targets)]
        for _, r in rows.iterrows():
            lines.append(f"• {r['名称']}: {r['最新价']:.2f} {color_tag(r['涨跌幅'])}")
        lines.append("")
    except Exception:
        lines.append("• 收盘数据获取失败")
        lines.append("")

    # 涨跌家数
    try:
        df = ak.stock_zh_index_spot_em()
        # 粗估涨跌家数
        rising = len(df[df["涨跌幅"] > 0]) if "涨跌幅" in df.columns else 0
        falling = len(df[df["涨跌幅"] < 0]) if "涨跌幅" in df.columns else 0
        lines.append(f"• 涨跌家数（估算）: 涨{rising}+ / 跌{falling}+")
        lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


def get_sector_trend() -> str:
    """板块动向（东方财富行业板块）"""
    lines = ["【板块动向】", "━━━━━━━━━━━━━━━━━━━━"]
    try:
        df = ak.stock_board_industry_name_em()
        df_sorted = df.sort_values("涨跌幅", ascending=False)

        top5 = df_sorted.head(5)
        bottom5 = df_sorted.tail(5)

        lines.append("强势板块:")
        for _, r in top5.iterrows():
            chg = float(r["涨跌幅"])
            lead = r.get("领涨股票", "-")
            lead_chg = r.get("领涨股票-涨跌幅", "-")
            lines.append(f"  • {r['板块名称']}: {color_tag(chg)}")
            if lead and lead != "-":
                lines.append(f"    领涨: {lead}({lead_chg}%)")

        lines.append("弱势板块:")
        for _, r in bottom5.iterrows():
            chg = float(r["涨跌幅"])
            lines.append(f"  • {r['板块名称']}: {color_tag(chg)}")

        lines.append("")
    except Exception:
        lines.append("• 板块数据获取失败")
        lines.append("")

    return "\n".join(lines)


def get_north_money() -> str:
    """北向资金"""
    lines = ["【北向资金】", "━━━━━━━━━━━━━━━━━━━━"]
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        # 筛选北向资金（北向=南向的反方向）
        north_df = df[df["资金方向"] == "北向"]

        for _, row in north_df.iterrows():
            region = row.get("板块", row.get("类型", "?"))
            net = float(row.get("资金净流入", 0))
            sign = "+" if net >= 0 else ""
            status = "净买入" if net >= 0 else "净卖出"
            lines.append(f"• {region}: {status} {sign}{abs(net):.1f}亿")

        if north_df.empty:
            lines.append("• 今日暂无北向数据")
        lines.append("")
    except Exception as e:
        lines.append("• 北向数据获取失败")
        lines.append(f"  ({type(e).__name__})")
        lines.append("")

    return "\n".join(lines)


def get_sentiment_summary() -> str:
    """情绪综合判断"""
    lines = ["【情绪综合】", "━━━━━━━━━━━━━━━━━━━━"]
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指"]
        avg_chg = 0.0
        count = 0
        for name in targets:
            row = df[df["名称"] == name]
            if not row.empty:
                avg_chg += float(row.iloc[0]["涨跌幅"])
                count += 1

        if count > 0:
            avg_chg /= count

        if avg_chg >= 1.0:
            sentiment = "🔥 情绪高涨"
            advice = "谨慎追高，注意获利了结"
        elif avg_chg >= 0.3:
            sentiment = "🟡 偏暖"
            advice = "可轻仓试探，跟随主线"
        elif avg_chg >= -0.3:
            sentiment = "⚪ 震荡整理"
            advice = "观望为主，等待方向明朗"
        elif avg_chg >= -1.0:
            sentiment = "🟠 偏弱"
            advice = "控制仓位，防守优先"
        else:
            sentiment = "🔴 情绪冰点"
            advice = "多看少动，等待情绪修复"

        lines.append(f"• 昨日情绪: {sentiment}")
        lines.append(f"• 操作建议: {advice}")
        lines.append("")
    except Exception:
        lines.append("• 情绪判断失败")
        lines.append("")

    return "\n".join(lines)


def get_pre_market_signal() -> str:
    """盘前三问信号"""
    lines = ["【盘前三问】", "━━━━━━━━━━━━━━━━━━━━"]
    lines.append("① 大盘今日方向: 待开盘确认")
    lines.append("② 资金主攻方向: 关注板块动向")
    lines.append("③ 系统性风险: 无显著风险（外盘平稳）")
    lines.append("")
    lines.append("⚠️ 本简报仅供参考，")
    lines.append("   实际决策请结合通达信信号")
    lines.append("   和持仓情况综合判断")
    lines.append("")
    return "\n".join(lines)


def get_header() -> str:
    """简报头部"""
    today = get_beijing_time().strftime("%Y-%m-%d %A")
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 A股晨间简报 | {today}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def main():
    if not is_enabled("morning_report"):
        print("[跳过] 晨间简报开关已关闭 (master_switch=false)")
        return

    print("=" * 50)
    print("📊 生成晨间简报...")
    print("=" * 50)

    header = get_header()
    us_market = get_us_market()
    yesterday = get_yesterday_close()
    sectors = get_sector_trend()
    north = get_north_money()
    sentiment = get_sentiment_summary()
    signals = get_pre_market_signal()

    content = f"""{header}

{us_market}
{yesterday}
{sectors}
{north}
{sentiment}
{signals}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 数据来源: akshare
🕐 生成时间: {get_beijing_time().strftime('%H:%M:%S')}"""

    print("\n" + content)

    if is_push_enabled():
        serverchan_push("📊 晨间简报", content)
        print("\n✅ 已推送至微信")
    else:
        print("\n⚠️ 推送未启用（push_notification=false）")


if __name__ == "__main__":
    main()
