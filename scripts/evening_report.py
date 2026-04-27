#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 晚间简报脚本
触发时间: 每天19:50 (北京时间)
功能：大盘数据 + 外盘概况 + 情报摘要 → 微信推送
"""

import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from config_reader import is_enabled, is_push_enabled
from push import serverchan_push


# ── 配色标记（微信不支持真正颜色，用 emoji 表示）──────────────────────
def color_tag(val: float) -> str:
    """涨: 🔴  跌: 🟢  平: ⚪"""
    if val > 0:
        return f"🔴 {val:+.2f}%"
    elif val < 0:
        return f"🟢 {val:+.2f}%"
    else:
        return f"⚪ 0.00%"


# ── A股主要指数 ─────────────────────────────────────────────────────
def get_zh_indices() -> str:
    """获取沪深主要指数实时行情"""
    try:
        df = ak.stock_zh_index_spot_em()
        # 过滤主要指数
        targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
        rows = df[df["名称"].isin(targets)]
        lines = []
        for _, row in rows.iterrows():
            name = row["名称"]
            price = row["最新价"]
            chg = row["涨跌幅"]
            lines.append(f"• {name}: {price:.2f} {color_tag(chg)}")
        return "\n".join(lines) if lines else "• 数据获取失败"
    except Exception as e:
        return f"• 指数数据获取失败: {e}"


# ── 外盘数据 ─────────────────────────────────────────────────────────
def get_us_indices() -> str:
    """获取美股期货/收盘数据"""
    try:
        df = ak.index_global_spot_em()
        targets = ["纳斯达克", "标普500", "道琼斯", "英国富时", "日经225"]
        rows = df[df["名称"].isin(targets)]
        lines = []
        for _, row in rows.iterrows():
            name = row["名称"]
            price = row["最新价"]
            chg = row["涨跌幅"]
            lines.append(f"• {name}: {price:.2f} {color_tag(chg)}")
        return "\n".join(lines) if lines else "• 暂无数据"
    except Exception as e:
        return f"• 美股数据获取失败: {e}"


# ── 大盘成交额 ───────────────────────────────────────────────────────
def get_market_turnover() -> str:
    """获取两市成交额"""
    try:
        df = ak.stock_zh_a_spot_em()
        total = df["成交额"].sum() / 1e8  # 转换为亿元
        up = len(df[df["涨跌幅"] > 0])
        down = len(df[df["涨跌幅"] < 0])
        flat = len(df) - up - down
        limit_up = len(df[df["涨跌幅"] >= 9.9])
        limit_down = len(df[df["涨跌幅"] <= -9.9])
        return (f"• 两市成交额: {total:.0f}亿\n"
                f"• 上涨/下跌/平盘: {up}/{down}/{flat}\n"
                f"• 涨停/跌停: {limit_up}家 / {limit_down}家")
    except Exception as e:
        return f"• 成交额数据获取失败: {e}"


# ── 今日情报摘要 ─────────────────────────────────────────────────────
def get_intelligence_summary() -> str:
    """从情报子系统读取今日情报"""
    beijing = ZoneInfo("Asia/Shanghai")
    today = datetime.now(beijing).strftime("%Y-%m-%d")
    yesterday = (datetime.now(beijing) - timedelta(days=1)).strftime("%Y-%m-%d")

    # 情报文件路径
    intel_file = (
        Path(__file__).parent.parent / "个人作战台" / "📡 数据子系统"
        / "📡 情报子系统" / "📊 情报分析" / "每日情报.md"
    )

    if intel_file.exists():
        content = intel_file.read_text(encoding="utf-8")
        # 提取今日或昨日情报块
        lines = content.split("\n")
        block = []
        capture = False
        for line in lines:
            if today in line or yesterday in line:
                capture = True
                block = [line]
            elif capture:
                if line.startswith("---") and len(block) > 1:
                    break
                block.append(line)
        if block:
            return "\n".join(block)

    return "📰 情报暂无更新，请检查情报收集是否正常运行"


# ── 日期计算 ─────────────────────────────────────────────────────────
def get_report_date() -> str:
    """晚间简报显示当天日期"""
    beijing = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing)
    # 19:50 = 当天（收盘已完成）
    return now.strftime("%Y-%m-%d")


# ── 主函数 ───────────────────────────────────────────────────────────
def main():
    if not is_enabled("evening_report"):
        print("[跳过] 晚间简报开关已关闭")
        return

    print("=" * 50)
    print("📊 生成晚间简报 (19:50)...")
    print("=" * 50)

    # 1. A股指数
    zh_indices = get_zh_indices()
    # 2. 外盘
    us_indices = get_us_indices()
    # 3. 成交额/涨跌家数
    turnover = get_market_turnover()
    # 4. 情报摘要
    intelligence = get_intelligence_summary()

    report_date = get_report_date()

    content = f"""📊 晚间简报 | {report_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【A股指数】
{zh_indices}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【外盘行情】
{us_indices}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【市场概况】
{turnover}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【情报摘要】
{intelligence}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 20:00 复盘时段开始
📋 任务：持仓复盘 → 明日计划 → 因子评分"""

    print("\n" + content)

    if is_push_enabled():
        serverchan_push("📊 晚间简报", content)
        print("\n✅ 已推送至微信")
    else:
        print("\n⚠️ 推送未启用（请检查 SCKEY 配置）")


if __name__ == "__main__":
    main()
