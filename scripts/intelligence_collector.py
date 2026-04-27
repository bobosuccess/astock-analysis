#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📡 情报收集器 v1.0
功能：从微信公众号抓取大V文章 + 生成情报摘要

依赖：
- akshare（行情数据）
- requests（网页抓取，如需）

使用：
    python scripts/intelligence_collector.py
"""

import json
import os
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============

# 情报源配置
INTELLIGENCE_SOURCES = {
    "大V体系": {
        "年大": {"定位": "超短/盘口逻辑", "关键词": ["年大", "盘口", "超短"]},
        "盘口逻辑拆解": {"定位": "技术分析/主力行为", "关键词": ["主力", "盘口", "机构"]},
        "听顾后花园": {"定位": "价值投资/基本面", "关键词": ["价值", "基本面", "政策"]},
    },
    "政策源": {
        "中国政府网": {"优先级": "🔴最高", "url": "http://www.gov.cn/zhengce/index.htm"},
        "证监会": {"优先级": "🔴最高", "url": "http://www.csrc.gov.cn/"},
        "财联社": {"优先级": "🟠高级", "url": "https://www.cls.cn/telegraph"},
    }
}

# 输出路径
OUTPUT_DIR = Path(__file__).parent.parent / "📡 数据子系统" / "📡 情报子系统" / "📊 情报分析"
TEMPLATE_FILE = Path(__file__).parent.parent / "个人作战台" / "📡 数据子系统" / "📡 情报子系统" / "📰 研报情报" / "输出模板.md"


def load_template():
    """加载输出模板"""
    if TEMPLATE_FILE.exists():
        return TEMPLATE_FILE.read_text(encoding="utf-8")
    return None


def generate_intelligence_report(articles: list, date: str = None) -> str:
    """
    生成情报日报
    
    Args:
        articles: 文章列表 [{"source": "年大", "title": "...", "summary": "...", "url": "..."}]
        date: 日期，默认今日
    
    Returns:
        str: 格式化后的情报报告
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # 按来源分组
    grouped = {}
    for article in articles:
        source = article.get("source", "未知")
        if source not in grouped:
            grouped[source] = []
        grouped[source].append(article)
    
    # 生成报告
    report = f"""📡 情报日报 | {date}

━━━━━━━━━━━━━━━━━
【大V观点】📰
━━━━━━━━━━━━━━━━━
"""
    
    for source, source_info in INTELLIGENCE_SOURCES["大V体系"].items():
        report += f"\n### {source}（{source_info['定位']}）\n"
        
        articles_from_source = grouped.get(source, [])
        if not articles_from_source:
            report += "- 今日暂无更新\n"
        else:
            for i, article in enumerate(articles_from_source, 1):
                report += f"- {article.get('title', '无标题')}\n"
                if article.get("summary"):
                    report += f"  摘要：{article['summary']}\n"
                if article.get("url"):
                    report += f"  链接：{article['url']}\n"
                report += f"  → 我的判断：\n\n"
    
    report += """━━━━━━━━━━━━━━━━━
【市场异动】⚠️
━━━━━━━━━━━━━━━━━
- 待接入行情数据...

━━━━━━━━━━━━━━━━━
【今日情报总结】💡
━━━━━━━━━━━━━━━━━
{一句话总结}
{明确建议}
"""
    
    return report


def save_report(report: str, date: str = None):
    """保存报告到文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # 保存每日情报
    daily_file = OUTPUT_DIR / "每日情报.md"
    
    # 追加模式
    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n\n{report}")
    
    print(f"✅ 情报已保存: {daily_file}")


def main():
    """主函数"""
    print("📡 情报收集器启动...")
    
    # 加载模板
    template = load_template()
    if template:
        print("✅ 模板加载成功")
    
    # 生成报告（示例数据）
    sample_articles = [
        {
            "source": "年大",
            "title": "今日盘口：XX股主力行为分析",
            "summary": "高位放量需警惕，主力出货信号明显",
            "url": "https://..."
        }
    ]
    
    report = generate_intelligence_report(sample_articles)
    print("\n" + report)
    
    # 保存
    save_report(report)
    
    print("\n📡 下一步：使用 wechat-article-search 工具搜索大V最新文章")


if __name__ == "__main__":
    main()
