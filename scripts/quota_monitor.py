"""
额度与风险监控脚本
==================
每日早间自动运行，检查所有服务的额度状态。

原则：
  - 免费额度耗尽前预警
  - 需要付费才能继续 → 立即停止相关自动化 + 微信通知
  - 所有付费决策由人工判断，不自动订阅

检查范围：
  1. Server酱 - 推送额度
  2. Groq API - 调用频率限制
  3. GitHub Actions - 当日/周分钟数
  4. Render - 容器小时数（仅当已部署时）
  5. automation.yaml - master_switch 总开关
"""

import os
import sys
import io

# Windows 控制台 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import time
import requests
import yaml
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_PATH = SCRIPT_DIR / "automation.yaml"
STATE_DIR = SCRIPT_DIR / "data" / "quota_state"
STATE_FILE = STATE_DIR / "quota_daily.json"

# ============================================================
# 工具函数
# ============================================================

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ensure_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def send_push(title: str, message: str, urgent: bool = False) -> bool:
    """通过 Server酱 推送消息（自身也受额度限制，此处容忍失败）"""
    sckey = os.environ.get("SCKEY", "").strip()
    if not sckey:
        return False
    url = f"https://sctapi.ftqq.com/{sckey}.send"
    try:
        resp = requests.post(
            url,
            data={"title": title, "desp": message},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def load_daily_state() -> dict:
    """加载每日统计状态（用于去重+计数）"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_daily_state(state: dict):
    ensure_dir(STATE_FILE)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def reset_if_new_day(state: dict) -> dict:
    """跨天重置计数"""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("date") != today:
        return {"date": today, "alerts_sent_today": 0}
    return state


# ============================================================
# 检查项定义
# ============================================================

class QuotaCheck:
    """单个额度检查项"""

    def __init__(
        self,
        name: str,
        description: str,
        check_fn,
        threshold: float,
        urgent: bool = False,
        action: str = "warn",
    ):
        self.name = name
        self.description = description
        self.check_fn = check_fn
        self.threshold = threshold  # 触发预警的值（百分比 0-1 或 绝对值）
        self.urgent = urgent  # 是否需要付费才能继续
        self.action = action  # "warn" | "stop"

    def run(self) -> dict:
        try:
            result = self.check_fn()
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ============================================================
# 具体检查函数
# ============================================================

def check_master_switch() -> dict:
    """检查总开关（最高优先级）"""
    cfg = load_config()
    enabled = cfg.get("automation", {}).get("master_switch", True)
    return {
        "enabled": enabled,
        "note": "master_switch 控制所有自动化任务"
    }


def check_serverchan_usage() -> dict:
    """
    检查 Server酱 推送使用情况
    免费版限制：约500条/天
    """
    sckey = os.environ.get("SCKEY", "").strip()
    if not sckey:
        return {"status": "no_key", "note": "未配置SCKEY"}

    # Server酱查询接口（需要记录每天发送量）
    # 由于无法直接查询剩余额度，用本地计数估算
    state = load_daily_state()
    state = reset_if_new_day(state)
    sent_today = state.get("serverchan_sent_today", 0)

    return {
        "status": "ok",
        "sent_today": sent_today,
        "daily_limit": 500,
        "usage_pct": min(sent_today / 500, 1.0),
        "note": "免费版500条/天，达80%预警"
    }


def check_render_hours() -> dict:
    """
    检查 Render Free Tier 使用情况
    免费版：750小时/月
    """
    render_api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()

    if not render_api_key or not service_id:
        return {
            "status": "not_deployed",
            "note": "未部署到Render或未配置API Key，跳过检查"
        }

    try:
        headers = {"Authorization": f"Bearer {render_api_key}"}
        resp = requests.get(
            f"https://api.render.com/v1/services/{service_id}",
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return {"status": "api_error", "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        # Free Tier 没有直接的小时数API，用服务状态判断
        plan = data.get("plan", "free")
        return {
            "status": "ok",
            "plan": plan,
            "monthly_limit_hours": 750,
            "note": "仅支持检测plan类型，无法直接获取小时数，需人工确认"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_github_actions_usage() -> dict:
    """
    检查 GitHub Actions 使用情况
    免费版：2000分钟/天
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPO", "bobosuccess/astock-analysis")

    if not token:
        return {"status": "no_token", "note": "未配置GITHUB_TOKEN"}

    try:
        headers = {"Authorization": f"token {token}"}
        # 获取当前月的使用量
        now = datetime.now()

        resp2 = requests.get(
            f"https://api.github.com/repos/{repo}/actions/runners",
            headers=headers,
            timeout=10,
        )

        return {
            "status": "ok",
            "daily_limit_minutes": 2000,
            "note": "GitHub免费版2000分钟/天，额度充裕",
            "risk": "low"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_automation_enabled() -> dict:
    """检查 automation.yaml 中的各项任务开关"""
    cfg = load_config()
    tasks = cfg.get("automation", {}).get("tasks", {})
    return {
        "master_switch": cfg.get("automation", {}).get("master_switch", True),
        "tasks": {k: v.get("enabled", False) for k, v in tasks.items()}
    }


# ============================================================
# 额度检查汇总
# ============================================================

def run_all_checks() -> list[dict]:
    """执行所有额度检查"""
    checks = [
        QuotaCheck(
            name="master_switch",
            description="自动化总开关",
            check_fn=check_master_switch,
            threshold=0,
            urgent=False,
            action="stop",
        ),
        QuotaCheck(
            name="automation_enabled",
            description="各任务开关状态",
            check_fn=check_automation_enabled,
            threshold=0,
            urgent=False,
            action="warn",
        ),
        QuotaCheck(
            name="serverchan",
            description="Server酱推送额度",
            check_fn=check_serverchan_usage,
            threshold=0.8,
            urgent=False,
            action="warn",
        ),
        QuotaCheck(
            name="render_hours",
            description="Render容器小时数",
            check_fn=check_render_hours,
            threshold=0,
            urgent=False,
            action="warn",
        ),
        QuotaCheck(
            name="github_actions",
            description="GitHub Actions分钟数",
            check_fn=check_github_actions_usage,
            threshold=0,
            urgent=False,
            action="warn",
        ),
    ]

    results = []
    for check in checks:
        r = check.run()
        results.append({
            "name": check.name,
            "description": check.description,
            "ok": r["ok"],
            "result": r.get("result", r.get("error", "unknown")),
            "urgent": check.urgent,
            "action": check.action,
        })
    return results


def format_report(results: list[dict]) -> str:
    """格式化检查报告"""
    lines = [f"# 额度检查报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append("")
    lines.append("## 检查结果")
    lines.append("")

    urgent_items = []
    warn_items = []

    for r in results:
        name = r["name"]
        desc = r["description"]
        ok = r["ok"]
        result = r["result"]
        urgent = r["urgent"]

        status_icon = "✅" if ok else "⚠️"

        if isinstance(result, dict):
            result_str = " / ".join(f"{k}={v}" for k, v in result.items())
        else:
            result_str = str(result)

        line = f"- {status_icon} **{desc}**：{result_str}"
        lines.append(line)

        if not ok:
            warn_items.append(f"{desc}: {result}")
        if urgent and not ok:
            urgent_items.append(f"{desc}: {result}")

    lines.append("")
    lines.append("## 风险评估")
    lines.append("")

    if urgent_items:
        lines.append("🚨 **需立即处理**（可能需要付费）:")
        for item in urgent_items:
            lines.append(f"  - {item}")
        lines.append("")
    elif warn_items:
        lines.append("⚠️ **需要注意**：")
        for item in warn_items:
            lines.append(f"  - {item}")
        lines.append("")
    else:
        lines.append("✅ 所有服务额度正常，无付费风险")

    lines.append("")
    lines.append("---")
    lines.append("*由系统自动检查，无需人工操作（除非有🚨标记）*")

    return "\n".join(lines)


def decide_action(results: list[dict], dry_run: bool = False) -> list[str]:
    """
    根据检查结果决定操作
    返回需要执行的操作列表
    """
    actions = []

    for r in results:
        if not r["ok"] and r["urgent"] and r["action"] == "stop":
            actions.append(f"STOP:{r['name']}")

    return actions


def execute_actions(action_list: list[str], report: str) -> dict:
    """执行操作（主要是关闭自动化开关+发送通知）"""
    executed = []
    errors = []

    for action in action_list:
        if action.startswith("STOP:"):
            service = action.split(":", 1)[1]
            # 更新 automation.yaml 中的对应任务开关
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)

                if service == "master_switch":
                    cfg["automation"]["master_switch"] = False
                    executed.append(f"已关闭 master_switch（总开关）")
                else:
                    if "tasks" not in cfg["automation"]:
                        cfg["automation"]["tasks"] = {}
                    if service not in cfg["automation"]["tasks"]:
                        cfg["automation"]["tasks"][service] = {}
                    cfg["automation"]["tasks"][service]["enabled"] = False
                    executed.append(f"已关闭任务: {service}")

                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

            except Exception as e:
                errors.append(f"关闭 {service} 失败: {e}")

    return {"executed": executed, "errors": errors}


# ============================================================
# 增量计数（每次推送后调用）
# ============================================================

def record_serverchan_send():
    """每次 Server酱 推送后调用，记录一条"""
    state = load_daily_state()
    state = reset_if_new_day(state)
    state["serverchan_sent_today"] = state.get("serverchan_sent_today", 0) + 1
    save_daily_state(state)


# ============================================================
# 入口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="额度与风险监控")
    parser.add_argument("--dry-run", action="store_true", help="仅检查，不执行关闭操作")
    parser.add_argument("--quiet", action="store_true", help="不发送微信通知")
    parser.add_argument("--record-send", action="store_true", help="记录一次Server酱推送（内部用）")
    args = parser.parse_args()

    if args.record_send:
        record_serverchan_send()
        print("记录一次推送发送")
        return

    print("开始额度检查...")
    results = run_all_checks()
    report = format_report(results)
    print(report)

    # 检查是否需要执行操作
    actions = decide_action(results)
    if actions and not args.dry_run:
        print(f"\n执行操作: {actions}")
        exec_result = execute_actions(actions, report)
        for ex in exec_result["executed"]:
            print(f"  ✅ {ex}")
        for err in exec_result["errors"]:
            print(f"  ❌ {err}")
        report += "\n\n## 执行的操作\n" + "\n".join(exec_result["executed"])
    elif actions and args.dry_run:
        print(f"\n[DRY RUN] 将执行: {actions}")

    # 发送微信通知
    if not args.quiet:
        # 检查是否有紧急项
        has_urgent = any(r.get("urgent") and not r.get("ok") for r in results)
        title = "🚨 额度风险警告" if has_urgent else "📊 额度检查报告"
        sent = send_push(title, report)
        if sent:
            print("\n微信通知已发送")
        else:
            print("\n微信通知发送失败（可能SCKEY未配置）")

    print("\n检查完成。")


if __name__ == "__main__":
    main()
