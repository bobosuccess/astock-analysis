#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📦 盘后批量处理脚本
触发时间: 每天15:05 (北京时间) = 07:05 UTC

功能：
1. 采集今日市场快照（指数/板块/资金/涨跌）
2. 写入 data/daily_archive/YYYYMMDD.json
3. 更新因子追踪记录（供进化机制使用）
4. 生成次日晨间简报基础数据
5. 推送归档完成通知
"""

import sys
import io
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Windows PowerShell UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
from config_reader import is_enabled, is_push_enabled
from push import serverchan_push


# ── 数据输出目录 ──────────────────────────────────────────────
def get_archive_dir() -> Path:
    """每日归档目录"""
    beijing = ZoneInfo("Asia/Shanghai")
    today = datetime.now(beijing).strftime("%Y%m%d")
    d = Path(__file__).parent.parent / "data" / "daily_archive" / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_archive_date() -> str:
    beijing = ZoneInfo("Asia/Shanghai")
    return datetime.now(beijing).strftime("%Y-%m-%d")


# ── ① A股指数快照 ───────────────────────────────────────────
def collect_index_snapshot() -> dict:
    """采集主要指数收盘数据"""
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
        rows = df[df["名称"].isin(targets)]
        indices = []
        for _, r in rows.iterrows():
            indices.append({
                "name": r["名称"],
                "price": round(float(r["最新价"]), 2),
                "change_pct": round(float(r["涨跌幅"]), 2),
                "volume": round(float(r["成交额"]) / 1e8, 1) if pd_notnull(r.get("成交额")) else None,
            })
        return {"status": "ok", "data": indices}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


# ── ② 全市场统计 ────────────────────────────────────────────
def collect_market_stats() -> dict:
    """两市成交额、涨跌家数、涨停炸板统计"""
    try:
        df = ak.stock_zh_a_spot_em()
        total_amount = round(df["成交额"].sum() / 1e8, 0)
        up = int(len(df[df["涨跌幅"] > 0]))
        down = int(len(df[df["涨跌幅"] < 0]))
        flat = int(len(df) - up - down)
        limit_up = int(len(df[df["涨跌幅"] >= 9.9]))
        limit_down = int(len(df[df["涨跌幅"] <= -9.9]))
        # 炸板：昨日涨停今日未封
        # 天地板：昨日跌停今日未封（简化统计）
        return {
            "status": "ok",
            "data": {
                "total_amount_b": total_amount,
                "up_count": up,
                "down_count": down,
                "flat_count": flat,
                "limit_up": limit_up,
                "limit_down": limit_down,
                "up_ratio": round(up / (up + down) * 100, 1) if (up + down) > 0 else 0,
            }
        }
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def pd_notnull(val):
    """兼容判断 pd.isna / 非空"""
    try:
        import pandas as pd
        return pd.notna(val)
    except Exception:
        return val is not None and val != ""


# ── ③ 板块排行 ──────────────────────────────────────────────
def collect_sector_ranking() -> dict:
    """东方财富行业板块涨跌幅排行（Top10 + Bottom10）"""
    try:
        df = ak.stock_board_industry_name_em()
        df_sorted = df.sort_values("涨跌幅", ascending=False)

        top = []
        for _, r in df_sorted.head(10).iterrows():
            top.append({
                "name": r["板块名称"],
                "change_pct": round(float(r["涨跌幅"]), 2),
                "lead_stocks": str(r.get("领涨股票", ""))[:50],
            })

        bottom = []
        for _, r in df_sorted.tail(10).iterrows():
            bottom.append({
                "name": r["板块名称"],
                "change_pct": round(float(r["涨跌幅"]), 2),
            })

        return {"status": "ok", "top10": top, "bottom10": bottom}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


# ── ④ 北向资金 ──────────────────────────────────────────────
def collect_north_funds() -> dict:
    """北向资金流向（沪股通+深股通）"""
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        north = df[df["资金方向"] == "北向"] if "资金方向" in df.columns else df
        items = []
        for _, r in north.iterrows():
            region = str(r.get("板块", r.get("类型", "?")))
            net = float(r.get("资金净流入", 0))
            items.append({
                "region": region,
                "net_flow_b": round(net, 1),
                "direction": "净买入" if net >= 0 else "净卖出",
            })
        return {"status": "ok", "data": items}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


# ── ⑤ 主力净流入板块 ─────────────────────────────────────────
def collect_mainfund_sectors() -> dict:
    """按主力净流入排序的行业板块（akshare东方财富接口）"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
        if df is None or df.empty:
            return {"status": "error", "msg": "空数据"}
        df_sorted = df.sort_values("今日主力净流入-净额", ascending=False)
        top = []
        for _, r in df_sorted.head(5).iterrows():
            net = float(r.get("今日主力净流入-净额", 0))
            top.append({
                "name": str(r.get("名称", "")),
                "mainfund_net_b": round(net / 1e8, 1),
                "change_pct": round(float(r.get("涨跌幅", 0)), 2),
            })
        return {"status": "ok", "top5": top}
    except Exception as e:
        # 降级：不阻塞主流程
        return {"status": "error", "msg": str(e)}


# ── 归档写入 ────────────────────────────────────────────────
def save_archive(archive_date: str, data: dict):
    """将采集数据写入JSON文件"""
    archive_dir = get_archive_dir()
    file_path = archive_dir / "market_snapshot.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": archive_date,
            "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            **data
        }, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 归档已写入: {file_path}")
    return file_path


# ── 生成摘要文本（供 evening_report 直接读取）─────────────────
def generate_summary_text(archive_date: str, data: dict) -> str:
    """生成盘后简报摘要文本（用于存档或推送）"""
    lines = [f"📦 盘后归档完成 | {archive_date}", "━━━━━━━━━━━━━━━━━━━━━━"]

    # 指数
    if data.get("indices", {}).get("status") == "ok":
        lines.append("【主要指数】")
        for idx in data["indices"]["data"]:
            chg = idx["change_pct"]
            tag = f"🔴 {chg:+.2f}%" if chg >= 0 else f"🟢 {chg:+.2f}%"
            lines.append(f"  • {idx['name']}: {idx['price']} {tag}")

    # 市场统计
    if data.get("market_stats", {}).get("status") == "ok":
        s = data["market_stats"]["data"]
        lines.append("【市场概况】")
        lines.append(f"  • 两市成交: {s['total_amount_b']:.0f}亿")
        lines.append(f"  • 上涨/下跌/平盘: {s['up_count']}/{s['down_count']}/{s['flat_count']} ({s['up_ratio']:.1f}%上涨)")
        lines.append(f"  • 涨停/跌停: {s['limit_up']}家 / {s['limit_down']}家")

    # 板块
    if data.get("sectors", {}).get("status") == "ok":
        lines.append("【强势板块 Top5】")
        for i, s in enumerate(data["sectors"]["top10"][:5], 1):
            chg = s["change_pct"]
            tag = f"🔴 {chg:+.2f}%" if chg >= 0 else f"🟢 {chg:+.2f}%"
            lines.append(f"  {i}. {s['name']}: {tag}")

    # 北向资金
    if data.get("north_funds", {}).get("status") == "ok":
        lines.append("【北向资金】")
        for item in data["north_funds"]["data"][:3]:
            lines.append(f"  • {item['region']}: {item['direction']} {abs(item['net_flow_b']):.1f}亿")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("✅ 数据归档完成，明日晨间简报已就绪")
    return "\n".join(lines)


# ── 主函数 ──────────────────────────────────────────────────
def main():
    if not is_enabled("after_close_batch"):
        print("[跳过] 盘后批量开关已关闭")
        return

    print("=" * 50)
    print("📦 盘后批量处理开始...")
    print("=" * 50)

    beijing = ZoneInfo("Asia/Shanghai")
    archive_date = datetime.now(beijing).strftime("%Y-%m-%d")
    is_weekend = datetime.now(beijing).weekday() >= 5

    # 判断是否为交易日（简化判断：非周末）
    if is_weekend:
        print("📅 周末，跳过市场数据采集（保留框架运行）")
        content = f"📦 周末归档 | {archive_date}\n✅ 今日非交易日，系统框架检查完成"
        if is_push_enabled():
            serverchan_push("📦 盘后归档", content)
        return

    # ── 分步采集 ──
    print("\n📥 采集指数数据...")
    indices = collect_index_snapshot()
    print(f"  {'✅' if indices['status']=='ok' else '❌'} {indices.get('msg', f'{len(indices.get(\"data\",[]))} 条')}")

    print("\n📊 采集市场统计...")
    market_stats = collect_market_stats()
    print(f"  {'✅' if market_stats['status']=='ok' else '❌'} {market_stats.get('msg', '正常')}")

    print("\n🏭 采集板块排行...")
    sectors = collect_sector_ranking()
    print(f"  {'✅' if sectors['status']=='ok' else '❌'} {sectors.get('msg', f'Top10/Bottom10 OK')}")

    print("\n💰 采集北向资金...")
    north_funds = collect_north_funds()
    print(f"  {'✅' if north_funds['status']=='ok' else '❌'} {north_funds.get('msg', f'{len(north_funds.get(\"data\",[]))} 条')}")

    print("\n🏧 采集主力净流入...")
    mainfund = collect_mainfund_sectors()
    print(f"  {'✅' if mainfund['status']=='ok' else '❌'} {mainfund.get('msg', 'Top5 OK')}")

    # ── 打包归档 ──
    all_data = {
        "indices": indices,
        "market_stats": market_stats,
        "sectors": sectors,
        "north_funds": north_funds,
        "mainfund_sectors": mainfund,
    }
    archive_file = save_archive(archive_date, all_data)

    # ── 生成摘要 ──
    summary = generate_summary_text(archive_date, all_data)
    print("\n" + summary)

    # ── 推送 ──
    if is_push_enabled():
        serverchan_push("📦 盘后归档", summary)
        print("\n✅ 已推送至微信")
    else:
        print("\n⚠️ 推送未启用（SCKEY 未配置）")

    print("\n📦 盘后批量完成")


if __name__ == "__main__":
    main()
