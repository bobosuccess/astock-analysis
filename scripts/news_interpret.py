#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📰 AI新闻解读脚本
触发时间: 每天19:30 (北京时间)
功能：
1. 抓取财联社实时电报 + 东方财富财经新闻
2. 过滤高相关度新闻（政策/宏观/行业/公司）
3. 调用 Groq API 做情绪判断 + 方向建议（无 API 时输出结构化摘要）
4. 微信推送
"""

import sys
import io
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

# Windows PowerShell UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
import requests
from config_reader import is_enabled, is_push_enabled
from push import serverchan_push


# ── 配置 ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# 关键词过滤（提高新闻相关度）
POLICY_KEYWORDS = ["央行", "证监会", "银保监", "财政部", "国务院", "发改委", "政治局",
                   "货币", "财政", "降准", "降息", "LPR", "逆回购", "监管", "政策"]
SECTOR_KEYWORDS = ["板块", "行业", "产业", "赛道", "景气", "景气度", "订单", "产能", "扩产"]
RISK_KEYWORDS = ["风险", "警示", "立案", "调查", "处罚", "退市", "ST", "违约", "暴雷"]


# ── 工具：AI 解读 ────────────────────────────────────────────
def call_groq(prompt: str) -> str:
    """调用 Groq API，返回 AI 回复文本"""
    if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY":
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位专业的A股分析师，风格简洁直接，给出明确判断，不说废话。\n"
                    "输出格式：\n"
                    "1. 今日情绪：[看多/偏多/中性/偏空/看空] — 一句话原因\n"
                    "2. 重点关注：[1-2句话]\n"
                    "3. 操作建议：[谨慎/观望/轻仓/标准仓] — 一句话原因\n"
                    "不要过度分析，不要说'仅供参考'。"
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 400,
    }

    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  ⚠️ Groq API 调用失败: {e}")
        return None


# ── ① 财联社实时电报 ────────────────────────────────────────
def fetch_cls_telegraph() -> list:
    """财联社电报（akshare: stock_info_global_cls）"""
    try:
        df = ak.stock_info_global_cls(symbol="最新")
        if df is None or df.empty:
            return []
        items = []
        for _, row in df.head(20).iterrows():
            title = str(row.get("标题", ""))
            content = str(row.get("内容", ""))[:200]
            if len(title) < 8:
                continue
            items.append({
                "title": title,
                "content": content,
                "source": "财联社",
            })
        return items
    except Exception as e:
        print(f"  ⚠️ 财联社电报获取失败: {e}")
        return []


# ── ② 东方财富财经新闻 ──────────────────────────────────────
def fetch_eastmoney_news() -> list:
    """东方财富财经新闻（直接HTTP抓取，避免akshare编码问题）"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.eastmoney.com",
        }
        resp = requests.get(
            "https://news.eastmoney.com/list/gn-list.json",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        json_data = resp.json()
        news_list = json_data.get("List", json_data.get("list", []))
        items = []
        for row in news_list[:15]:
            title = str(row.get("Title", row.get("title", "")))
            content = str(row.get("Summary", row.get("digest", "")))[:200]
            if len(title) < 8:
                continue
            items.append({
                "title": title,
                "content": content,
                "source": "东方财富",
            })
        return items
    except Exception as e:
        print(f"  ⚠️ 东方财富新闻获取失败: {e}")
        return []


# ── ③ 新闻过滤 + 分类 ───────────────────────────────────────
def classify_news(news: list) -> dict:
    """按关键词分类新闻"""
    policy, sector, risk, general = [], [], [], []

    for item in news:
        title = item["title"]
        text = title + " " + item["content"]

        if any(kw in text for kw in POLICY_KEYWORDS):
            policy.append(item)
        elif any(kw in text for kw in SECTOR_KEYWORDS):
            sector.append(item)
        elif any(kw in text for kw in RISK_KEYWORDS):
            risk.append(item)
        else:
            general.append(item)

    return {
        "policy": policy[:5],
        "sector": sector[:5],
        "risk": risk[:5],
        "general": general[:5],
    }


# ── ④ 构建 AI Prompt ────────────────────────────────────────
def build_prompt(classified: dict) -> str:
    """构造 AI 分析 Prompt"""
    lines = ["## 今日财经要闻\n"]

    sections = [
        ("🔴 政策面", classified.get("policy", [])),
        ("🟠 行业/板块", classified.get("sector", [])),
        ("⚠️ 风险事件", classified.get("risk", [])),
        ("📰 一般新闻", classified.get("general", [])),
    ]

    for title, items in sections:
        if items:
            lines.append(f"\n{title}:")
            for item in items[:3]:
                lines.append(f"- {item['title']}")

    lines.append("\n请根据以上新闻，分析今日A股市场情绪，给出明确判断。")
    return "\n".join(lines)


# ── ⑤ 生成报告 ──────────────────────────────────────────────
def generate_report(classified: dict, ai_interpretation: str | None) -> str:
    """生成最终推送报告"""
    beijing = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing)
    report_date = now.strftime("%Y-%m-%d")
    report_time = now.strftime("%H:%M")

    lines = [f"📰 AI新闻解读 | {report_date} {report_time}"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 政策面
    policy = classified.get("policy", [])
    if policy:
        lines.append("\n【🔴 政策面】")
        for item in policy[:4]:
            lines.append(f"• {item['title']}")
    else:
        lines.append("\n【🔴 政策面】暂无重要政策消息")

    # 行业板块
    sector = classified.get("sector", [])
    if sector:
        lines.append("\n【🟠 行业动态】")
        for item in sector[:4]:
            lines.append(f"• {item['title']}")
    else:
        lines.append("\n【🟠 行业动态】暂无重要行业消息")

    # 风险事件
    risk = classified.get("risk", [])
    if risk:
        lines.append("\n【⚠️ 风险警示】")
        for item in risk[:3]:
            lines.append(f"• {item['title']}")

    # AI 解读
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("\n【🧠 AI 解读】")
    if ai_interpretation:
        lines.append(ai_interpretation)
    else:
        lines.append("⚠️ AI 解读功能未启用（请配置 GROQ_API_KEY）")
        all_news = policy + sector + risk + classified.get("general", [])
        if all_news:
            lines.append("\n📋 今日要点：")
            for item in all_news[:5]:
                truncated = item['title'][:40] + ('...' if len(item['title']) > 40 else '')
                lines.append(f"• {truncated}")
            lines.append("\n💡 建议：关注政策面变化，跟踪主线板块动向")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⏰ 19:50 晚间简报即将推送")

    return "\n".join(lines)


# ── 主函数 ──────────────────────────────────────────────────
def main():
    if not is_enabled("news_interpret"):
        print("[跳过] 新闻解读开关已关闭 (master_switch=false)")
        return

    print("=" * 50)
    print("📰 AI新闻解读开始...")
    print("=" * 50)

    # ① 抓取新闻
    print("\n📥 采集财联社电报...")
    cls_news = fetch_cls_telegraph()
    print(f"  ✅ 获取 {len(cls_news)} 条")

    print("\n📥 采集东方财富新闻...")
    em_news = fetch_eastmoney_news()
    print(f"  {'✅' if em_news else '⚠️'} 获取 {len(em_news)} 条")

    # 合并 + 去重
    all_news = {item["title"]: item for item in cls_news + em_news}
    all_news_list = list(all_news.values())
    print(f"\n  📊 去重后共 {len(all_news_list)} 条")

    if not all_news_list:
        print("❌ 新闻采集失败，跳过")
        return

    # ② 分类
    classified = classify_news(all_news_list)
    important_count = sum(len(v) for v in classified.values())
    print(f"  🎯 高相关度新闻: {important_count} 条")

    # ③ AI 解读
    print("\n🧠 调用 AI 解读...")
    if GROQ_API_KEY and GROQ_API_KEY != "YOUR_GROQ_API_KEY":
        prompt = build_prompt(classified)
        ai_result = call_groq(prompt)
        print(f"  {'✅' if ai_result else '❌'} AI 解读{'成功' if ai_result else '失败'}")
    else:
        print("  ⚠️ 未配置 GROQ_API_KEY，跳过 AI 解读（输出结构化摘要）")
        ai_result = None

    # ④ 生成报告
    report = generate_report(classified, ai_result)
    print("\n" + report)

    # ⑤ 推送
    if is_push_enabled():
        serverchan_push("📰 AI新闻解读", report)
        print("\n✅ 已推送至微信")
    else:
        print("\n⚠️ 推送未启用（push_notification layer = false）")

    print("\n📰 新闻解读完成")


if __name__ == "__main__":
    main()
