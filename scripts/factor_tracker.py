#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 因子命中率追踪分析脚本
分析每笔交易的因子命中情况，计算命中率并建议权重调整

使用方法：
  python scripts/factor_tracker.py analyze          # 分析所有交易
  python scripts/factor_tracker.py analyze --days 30 # 分析近30天
  python scripts/factor_tracker.py evolve            # 输出进化建议
  python scripts/factor_tracker.py record            # 交互式录入新交易
  python scripts/factor_tracker.py report            # 生成月度报告
"""

import sys, io
import os, json, yaml
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ── 路径配置 ────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
OBSIDIAN_VAULT = Path(os.environ.get(
    "OBSIDIAN_VAULT",
    "C:/Users/Jenny King/Documents/Jenny"
))
TRACKING_DIR = ROOT / "data" / "factor_tracking"
TRACKING_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_CONFIG = ROOT / "factor_config.json"

# ── 因子配置（与决策因子体系v4.1同步）──────────────────────
DEFAULT_FACTORS = {
    "F1": {"name": "技术指标", "short_weight": 0.35, "long_weight": 0.20},
    "F2": {"name": "市场感知", "short_weight": 0.20, "long_weight": 0.10},
    "F3": {"name": "情报分析", "short_weight": 0.25, "long_weight": 0.30},
    "F4": {"name": "板块题材", "short_weight": 0.20, "long_weight": 0.15},
    "F5": {"name": "基本面",   "short_weight": 0.00, "long_weight": 0.25},
}

# 命中标准（各因子判断"预测正确"的条件）
HIT_RULES = {
    "F1": {
        "short": lambda d: d.get("price_change_3d", 0) * d.get("direction", 1) > 0,
        "long":  lambda d: d.get("price_change_20d", 0) * d.get("direction", 1) > 0,
        "field": ["tech_signal", "direction"],
    },
    "F2": {
        "short": lambda d: d.get("index_direction", 0) * d.get("direction", 1) >= 0,
        "long":  lambda d: d.get("index_direction", 0) * d.get("direction", 1) >= 0,
        "field": ["market_env"],
    },
    "F3": {
        "short": lambda d: d.get("catalyst_effect", 0) > 0 or d.get("news_direction", 0) * d.get("direction", 1) > 0,
        "long":  lambda d: d.get("policy_effect", 0) > 0,
        "field": ["catalyst", "policy_direction"],
    },
    "F4": {
        "short": lambda d: d.get("sector_change", 0) > 0,
        "long":  lambda d: d.get("sector_change", 0) > 0,
        "field": ["sector", "theme_strength"],
    },
    "F5": {
        "short": lambda d: True,  # 短线不参考F5
        "long":  lambda d: d.get("fundamental_score", 0) >= 3,
        "field": ["fundamental_score"],
    },
}

# 进化阈值
EVOLVE_BOOST_THRESHOLD = 0.60   # 命中率>60% → 建议增加权重
EVOLVE_CUT_THRESHOLD    = 0.40   # 命中率<40% → 建议减少权重
EVOLVE_BOOST_STEP       = 0.05   # 每次调整步长
EVOLVE_MIN_SAMPLES      = 5      # 最小样本量才触发进化


# ── 数据文件操作 ─────────────────────────────────────────
def get_trade_log_path():
    date_str = datetime.now().strftime("%Y%m%d")
    return TRACKING_DIR / f"trades_{date_str}.json"

def load_factors_config():
    if FACTOR_CONFIG.exists():
        with open(FACTOR_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "factors": {k: {**v, "current_short": v["short_weight"], "current_long": v["long_weight"]}
                    for k, v in DEFAULT_FACTORS.items()},
        "last_evolve_date": None,
        "evolve_history": [],
    }

def save_factors_config(cfg):
    with open(FACTOR_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_all_trades(days=365):
    cutoff = datetime.now() - timedelta(days=days)
    trades = []
    for f in TRACKING_DIR.glob("trades_*.json"):
        try:
            date_str = f.stem.replace("trades_", "")
            trade_date = datetime.strptime(date_str, "%Y%m%d")
            if trade_date < cutoff:
                continue
            with open(f, "r", encoding="utf-8") as fh:
                trades.extend(json.load(fh))
        except Exception:
            pass
    return trades


# ── 命中率计算 ────────────────────────────────────────────
def calc_factor_hit_rate(trades, factor_id, strategy):
    """
    计算某个因子在某种策略下的命中率。
    strategy: 'short' | 'long'
    """
    field = HIT_RULES[factor_id]["field"]
    rule  = HIT_RULES[factor_id][strategy]
    key   = f"{strategy}_hit"

    # 过滤出该策略且有该因子记录的交易
    relevant = [t for t in trades
                if t.get("strategy") == strategy
                and factor_id in t.get("factor_scores", {})
                and t.get("outcome", {}).get("has_outcome", False)]

    if len(relevant) < EVOLVE_MIN_SAMPLES:
        return None, len(relevant)

    hits = sum(1 for t in relevant if t["outcome"].get(key, False))
    return hits / len(relevant), len(relevant)


def analyze_all(trades, strategy="short"):
    """计算所有因子的命中率"""
    cfg = load_factors_config()
    results = {}
    for fid, finfo in cfg["factors"].items():
        rate, n = calc_factor_hit_rate(trades, fid, strategy)
        current = finfo.get(f"current_{strategy}", finfo.get(f"{strategy}_weight", 0))
        results[fid] = {
            "name":     finfo["name"],
            "hit_rate": rate,
            "samples":  n,
            "current_weight": current,
            "direction": "—",
            "suggested_weight": current,
            "reason": "",
        }
        if rate is not None and n >= EVOLVE_MIN_SAMPLES:
            if rate >= EVOLVE_BOOST_THRESHOLD:
                delta = EVOLVE_BOOST_STEP
                results[fid]["direction"] = "⬆️ 提升"
                results[fid]["suggested_weight"] = round(min(current + delta, 0.50), 2)
                results[fid]["reason"] = f"命中率{int(rate*100)}%≥60%，建议+{int(delta*100)}%"
            elif rate <= EVOLVE_CUT_THRESHOLD:
                delta = EVOLVE_BOOST_STEP
                results[fid]["direction"] = "⬇️ 降低"
                results[fid]["suggested_weight"] = round(max(current - delta, 0.00), 2)
                results[fid]["reason"] = f"命中率{int(rate*100)}%≤40%，建议-{int(delta*100)}%"
            else:
                results[fid]["direction"] = "➡️ 维持"
                results[fid]["reason"] = f"命中率{int(rate*100)}%在正常区间"

    # 计算加权得分
    total_suggested = sum(r["suggested_weight"] for r in results.values())
    for r in results.values():
        if total_suggested > 0:
            r["suggested_pct"] = f"{r['suggested_weight']/total_suggested*100:.0f}%"
        else:
            r["suggested_pct"] = "—"

    return results


# ── 进化输出 ──────────────────────────────────────────────
def generate_evolve_suggestions(trades, strategy="short"):
    results = analyze_all(trades, strategy)

    lines = [
        f"## 📊 因子进化分析报告 | {datetime.now().strftime('%Y-%m-%d')} | {strategy.upper()}策略",
        "",
        "### 命中率追踪",
        "",
        "| 因子 | 名称 | 命中率 | 样本量 | 当前权重 | 建议 | 建议权重 | 原因 |",
        "|------|------|--------|--------|-----------|------|----------|------|",
    ]
    for fid, r in results.items():
        rate_str = f"{int(r['hit_rate']*100)}%" if r["hit_rate"] is not None else "—"
        lines.append(
            f"| {fid} | {r['name']} | {rate_str} | {r['samples']} | "
            f"{int(r['current_weight']*100)}% | {r['direction']} | "
            f"{int(r['suggested_weight']*100)}% | {r['reason']} |"
        )

    # 判断整体是否需要进化
    need_evolve = any(
        r["direction"] != "—" and r["direction"] != "➡️ 维持"
        and r["samples"] >= EVOLVE_MIN_SAMPLES
        for r in results.values()
    )

    lines.append("")
    lines.append("### 进化建议")
    if need_evolve:
        lines.append("> ⚠️ 检测到因子命中率显著变化，建议更新权重配置。")
        lines.append("")
        lines.append("**执行步骤：**")
        lines.append("1. 确认上方建议后，更新 `因子命中率追踪/因子配置.json` 中的 `current_short` / `current_long`")
        lines.append("2. 在决策因子体系中同步更新权重表")
        lines.append("3. 记录本次进化：`scripts/factor_tracker.py evolve` 会自动写入历史")
    else:
        lines.append("> ✅ 各因子命中率稳定，暂无需调整。")

    return "\n".join(lines), need_evolve


def run_evolve(trades, strategy="short"):
    """执行进化：更新因子配置"""
    cfg = load_factors_config()
    results = analyze_all(trades, strategy)

    updated = []
    for fid, r in results.items():
        if r["direction"] in ("⬆️ 提升", "⬇️ 降低"):
            key = f"current_{strategy}"
            old = cfg["factors"][fid][key]
            new = r["suggested_weight"]
            cfg["factors"][fid][key] = new
            updated.append(f"{fid} {r['name']}: {int(old*100)}% → {int(new*100)}% ({r['reason']})")

    if updated:
        cfg["evolve_history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "strategy": strategy,
            "changes": updated,
        })
        cfg["last_evolve_date"] = datetime.now().strftime("%Y-%m-%d")
        save_factors_config(cfg)

    return updated


# ── 交互式录入 ───────────────────────────────────────────
def interactive_record():
    """交互式录入新交易"""
    print("📝 因子命中率追踪 - 录入新交易")
    print("=" * 40)

    trade = {
        "stock":     input("股票代码 (如 000001.SZ): ").strip(),
        "date":      input("交易日期 (YYYY-MM-DD): ").strip() or datetime.now().strftime("%Y-%m-%d"),
        "strategy":  input("策略类型 (short/long): ").strip() or "short",
        "direction": 1 if input("方向 (买入=1 / 做空=-1): ").strip() in ("", "1") else -1,
        "factor_scores": {},
        "outcome":   {},
    }

    print("\n因子评分 (0-100, 空=未参考):")
    for fid in DEFAULT_FACTORS:
        val = input(f"  {fid} {DEFAULT_FACTORS[fid]['name']}: ").strip()
        if val:
            trade["factor_scores"][fid] = int(val)

    print("\nOutcome (完成后填):")
    trade["outcome"]["price_change_3d"]  = float(input("  3日内涨跌幅(%) (空=未结算): ").strip() or 0) or None
    trade["outcome"]["price_change_20d"] = float(input("  20日内涨跌幅(%) (空=未结算): ").strip() or 0) or None
    trade["outcome"]["has_outcome"] = trade["outcome"]["price_change_3d"] is not None

    # 计算因子命中
    for fid, finfo in DEFAULT_FACTORS.items():
        if fid not in trade["factor_scores"]:
            continue
        strategy = trade["strategy"]
        rule = HIT_RULES.get(fid, {}).get(strategy)
        if rule and trade["outcome"]["has_outcome"]:
            try:
                trade["outcome"][f"{strategy}_hit"] = rule(trade["outcome"])
            except Exception:
                pass

    # 追加到当日文件
    log_path = get_trade_log_path()
    existing = []
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.append(trade)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到 {log_path.name}")
    return trade


# ── 主入口 ────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="因子命中率追踪分析")
    parser.add_argument("cmd", choices=["analyze", "evolve", "record", "report"],
                        help="命令: analyze=分析 | evolve=执行进化 | record=录入 | report=月度报告")
    parser.add_argument("--days", type=int, default=90, help="分析最近N天（默认90天）")
    parser.add_argument("--strategy", choices=["short", "long", "both"], default="both",
                        help="策略类型（默认both）")
    args = parser.parse_args()

    trades = load_all_trades(args.days)

    if args.cmd == "record":
        interactive_record()
    elif args.cmd == "analyze":
        for s in (["short", "long"] if args.strategy == "both" else [args.strategy]):
            report, _ = generate_evolve_suggestions(trades, s)
            print(report)
            print()
    elif args.cmd == "evolve":
        for s in (["short", "long"] if args.strategy == "both" else [args.strategy]):
            updated = run_evolve(trades, s)
            if updated:
                print(f"✅ {s.upper()} 权重已更新:")
                for u in updated:
                    print(f"  • {u}")
            else:
                print(f"ℹ️  {s.upper()} 无需调整")
    elif args.cmd == "report":
        print("📊 月度因子进化报告")
        print("=" * 50)
        for s in ["short", "long"]:
            report, _ = generate_evolve_suggestions(trades, s)
            print(report)
            print()


if __name__ == "__main__":
    main()
