# 推送模块
# 支持: Server酱 / Bark

import os, sys, io
import requests
from config_reader import load_config


def serverchan_push(title: str, content: str):
    """Server酱微信推送"""
    import json as _json

    # 优先用 GitHub Actions 环境变量（secrets.SCKEY），其次用本地 automation.yaml
    sckey = os.getenv("SCKEY", "")
    sckey_source = "环境变量 SCKEY"

    if not sckey or sckey == "YOUR_SCKEY_HERE":
        # fallback: 尝试从本地配置文件读取
        try:
            config = load_config()
            sckey = config["push"]["serverchan"].get("sckey") or ""
            sckey_source = "automation.yaml"
        except Exception:
            sckey = ""

    if not sckey or sckey == "YOUR_SCKEY_HERE":
        print(f"[推送跳过] Server酱未配置SCKEY（来源: {sckey_source}，值: '{sckey[:4]}***' 如果有值说明SCKEY本身有效但被排除了）")
        return

    url = f"https://sctapi.ftqq.com/{sckey}.send"
    data = {
        "title": title,
        "desp": content
    }

    print(f"[推送调试] 使用 {sckey_source}，URL: https://sctapi.ftqq.com/{sckey[:8]}***.send")

    try:
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        if result.get("code") == 0 or result.get("data", {}).get("error") == 0:
            print(f"[推送成功] {title}")
            _record_quota()  # 记录一次推送，用于每日额度监控
        else:
            print(f"[推送失败] code={result.get('code')} error={result.get('error')} info={result.get('info')}")
    except Exception as e:
        print(f"[推送异常] {type(e).__name__}: {e}")


def _record_quota():
    """记录一次推送发送，用于额度监控"""
    try:
        import subprocess, sys
        script_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "quota_monitor.py"), "--record-send"],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass  # 记录失败不影响推送


def bark_push(title: str, content: str):
    """Bark推送 (iPhone)"""
    config = load_config()
    bark_key = config["push"]["bark"].get("bark_key") or os.getenv("BARK_KEY", "")

    if not bark_key or bark_key == "YOUR_BARK_KEY_HERE":
        print(f"[推送跳过] Bark未配置Key")
        return

    url = f"https://api.day.app/{bark_key}/{title}/{content}"

    try:
        resp = requests.get(url, timeout=10)
        print(f"[Bark推送] {resp.text}")
    except Exception as e:
        print(f"[Bark异常] {e}")


def push_to_wechat(title: str, content: str) -> bool:
    """统一推送入口（微信推送）"""
    sckey = os.getenv("SCKEY", "")
    print(f"[推送调试] push_to_wechat 使用 SCKEY 环境变量，长度: {len(sckey) if sckey else 0}")

    if not sckey or sckey == "YOUR_SCKEY_HERE":
        print(f"[推送跳过] 未配置SCKEY")
        return False
    try:
        url = f"https://sctapi.ftqq.com/{sckey}.send"
        data = {"title": title, "desp": content}
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        if result.get("code") == 0:
            print(f"[推送成功] {title}")
            return True
        else:
            print(f"[推送失败] {result}")
            return False
    except Exception as e:
        print(f"[推送异常] {e}")
        return False
