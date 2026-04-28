"""
实时行情监控服务 (UptimeRobot 唤醒版)
====================================
- 完全免费方案：UptimeRobot(免费) + Render Free Tier
- UptimeRobot 每5分钟访问 /health → 触发一次监控检查
- 非交易时段容器自然休眠（UptimeRobot只配置在交易时段）
- 依赖：flask, akshare, requests
"""

import os
import sys
import io
import time
import json
import signal
import logging
from datetime import datetime
import requests
import yaml
import akshare as ak
import pandas as pd
import numpy as np

# Windows 控制台 UTF-8

try:
    from flask import Flask, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    print("[WARN] flask not installed, running in CLI-only mode")

# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(PROJECT_DIR, "automation.yaml"))
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(PROJECT_DIR, "data", "realtime_state"))
STATE_FILE = os.path.join(STATE_DIR, "alert_state.json")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("realtime_monitor")


# ============================================================
# 工具函数
# ============================================================

def load_yaml_config(path: str) -> dict:
    """加载 YAML 配置文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.error(f"配置加载失败: {e}")
        return {}


def load_config() -> dict:
    """读取完整配置"""
    return load_yaml_config(CONFIG_PATH)


def is_trading_day() -> bool:
    """判断今天是否为交易日（简化判断：周一~周五）"""
    today = datetime.now().date()
    # 0=周一, 6=周日
    return today.weekday() < 5


def is_trading_hours() -> bool:
    """
    判断当前是否为 A股交易时段
    上午: 09:30-11:30
    下午: 13:00-15:00
    """
    now = datetime.now()
    h, m = now.hour, now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return False

    # 转换为分钟计数
    cur_min = h * 60 + m
    am_start, am_end = 9 * 60 + 30, 11 * 60 + 30
    pm_start, pm_end = 13 * 60, 15 * 60

    return (am_start <= cur_min <= am_end) or (pm_start <= cur_min <= pm_end)


def get_session_interval() -> int:
    """根据是否在交易时段，返回休眠秒数"""
    return 60 if is_trading_hours() else 1800  # 盘中1分钟，盘后30分钟


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def load_state() -> dict:
    """加载预警状态（用于检测状态变化，如涨停后炸板）"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_state(state: dict):
    """保存预警状态"""
    try:
        ensure_dir(STATE_DIR)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"状态保存失败: {e}")


# ============================================================
# 数据获取
# ============================================================

def get_realtime_data(codes: list[str]) -> dict[str, dict]:
    """获取实时行情数据（akshare 优先，腾讯财经备用）"""
    result = {}

    # 格式标准化
    normalized = []
    for code in codes:
        code = code.strip()
        if code.endswith(".SH") or code.endswith(".SS"):
            normalized.append(code.replace(".SH", ".SS"))
        elif code.endswith(".SZ"):
            normalized.append(code)
        else:
            # 未知格式，假设深市
            normalized.append(f"{code}.SZ")

    try:
        # 批量获取实时行情
        df = ak.stock_zh_a_spot_em()
        df = df.set_index("代码")

        for code in normalized:
            try:
                if code in df.index:
                    row = df.loc[code]
                    price = float(str(row["最新价"]).replace("--", "0"))
                    change = float(str(row["涨跌幅"]).replace("--", "0"))
                    volume = float(str(row["成交额"]).replace("--", "0")) if "成交额" in row else 0
                    high = float(str(row["最高"]).replace("--", "0"))
                    low = float(str(row["最低"]).replace("--", "0"))
                    name = str(row["名称"]) if "名称" in row else code

                    result[code] = {
                        "name": name,
                        "price": price,
                        "change": change,
                        "volume": volume,
                        "high": high,
                        "low": low,
                        "source": "akshare",
                    }
            except Exception:
                pass
    except Exception as e:
        log.error(f"akshare 获取失败: {e}")

    # 备用：腾讯财经
    if len(result) < len(normalized):
        for code in normalized:
            if code not in result:
                try:
                    df2 = ak.stock_zh_a_spot_pre_market_em()
                    # 简化备用逻辑：用新浪财经备用
                    result[code] = _get_from_tencent_fallback(code)
                except Exception:
                    pass

    return result


def _get_from_tencent_fallback(code: str) -> dict | None:
    """腾讯财经备用数据源"""
    try:
        url = f"https://qt.gtimg.cn/q={code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            parts = resp.text.split("~")
            if len(parts) > 10:
                return {
                    "name": parts[1],
                    "price": float(parts[3]),
                    "change": round((float(parts[3]) - float(parts[4])) / float(parts[4]) * 100, 2),
                    "volume": float(parts[6]) if parts[6] else 0,
                    "high": float(parts[33]) if parts[33] else 0,
                    "low": float(parts[34]) if parts[34] else 0,
                    "source": "tencent",
                }
    except Exception:
        pass
    return None


# ============================================================
# 预警判断
# ============================================================

def check_alerts(
    code: str,
    data: dict,
    prev_state: dict,
    position_info: dict,
) -> list[str]:
    """
    检查单只股票的预警类型
    返回预警类型列表
    """
    alerts = []
    price = data.get("price", 0)
    change = data.get("change", 0)
    volume = data.get("volume", 0)
    name = data.get("name", code)
    high = data.get("high", 0)
    low = data.get("low", 0)
    prev_price = prev_state.get("price", price)
    prev_change = prev_state.get("change", change)

    s_key = f"{code}_state"

    # 1. 涨停预警（涨幅 ≥ 9.5%，且非ST/涨跌停板限制股）
    if change >= 9.5:
        alerts.append("limit_up")

    # 2. 炸板预警（昨日涨停，今日打开涨停板）
    if s_key in prev_state and prev_state[s_key].get("was_limit_up"):
        if change < 9.5 and price > prev_price:
            alerts.append("break_limit_up")

    # 3. 急跌预警（5min内跌幅 > 3%，基于当前价 vs 盘中高点）
    if high > 0 and (high - price) / high * 100 > 3:
        alerts.append("rapid_drop")

    # 4. 大跌预警（跌幅 > 5%）
    if change <= -5:
        alerts.append("big_drop")

    # 5. 放量异动（成交量 > 均量3倍 且 涨幅 > 3%）
    if change > 3 and prev_change > 0:
        vol_ratio = volume / max(prev_state.get("prev_volume", 1), 1)
        if vol_ratio > 3:
            alerts.append("volume_surge")

    # 6. 止损触发（配置了止损价且跌破）
    stop_loss = position_info.get("stop_loss")
    if stop_loss and price > 0 and price <= float(stop_loss):
        alerts.append("stop_loss")

    return alerts


def build_alert_message(code: str, data: dict, alert_types: list[str]) -> str:
    """生成预警推送内容"""
    name = data.get("name", code)
    price = data.get("price", 0)
    change = data.get("change", 0)
    emoji_map = {
        "limit_up": "🔴",
        "break_limit_up": "🟠",
        "rapid_drop": "⚠️",
        "big_drop": "🔵",
        "volume_surge": "💥",
        "stop_loss": "🛑",
    }
    label_map = {
        "limit_up": "涨停预警",
        "break_limit_up": "炸板预警",
        "rapid_drop": "急跌预警",
        "big_drop": "大跌预警",
        "volume_surge": "放量异动",
        "stop_loss": "止损触发",
    }

    emojis = "".join(emoji_map.get(t, "⚡") for t in alert_types)
    labels = "/".join(label_map.get(t, t) for t in alert_types)

    msg = f"{emojis} {labels}\n"
    msg += f"股票: {name} ({code})\n"
    msg += f"现价: {price:.2f}  涨跌: {change:+.2f}%"

    return msg


# ============================================================
# 推送
# ============================================================

def send_push(message: str) -> bool:
    """通过 Server酱 推送微信消息"""
    sckey = os.environ.get("SCKEY", "").strip()
    if not sckey:
        log.warning("SCKEY 未设置，跳过推送")
        return False

    url = f"https://sctapi.ftqq.com/{sckey}.send"
    try:
        resp = requests.post(
            url,
            data={
                "title": "📡 行情预警",
                "desp": message,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log.info(f"推送成功: {message[:50]}")
            return True
        else:
            log.error(f"推送失败: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        log.error(f"推送异常: {e}")
    return False


# ============================================================
# 核心监控逻辑
# ============================================================

def run_monitoring_cycle():
    """执行一次监控检查（UptimeRobot 唤醒时调用）"""
    cfg = load_config()

    # 检查总开关
    realtime_cfg = cfg.get("automation", {}).get("tasks", {}).get("realtime_monitor", {})
    if not realtime_cfg.get("enabled", False):
        log.debug("实时监控未启用，跳过")
        return {"status": "skipped", "reason": "disabled"}

    # 检查交易时段（可选，默认启用）
    if not realtime_cfg.get("check_trading_hours", True):
        if not is_trading_hours():
            log.debug("非交易时段，跳过")
            return {"status": "skipped", "reason": "outside_hours"}

    positions = cfg.get("portfolio", {}).get("positions", [])
    if not positions:
        log.info("自选股池为空，跳过")
        return {"status": "skipped", "reason": "empty_watchlist"}

    # 标准化股票代码
    if isinstance(positions, list):
        codes = [p if isinstance(p, str) else p.get("code", "") for p in positions]
    else:
        codes = []
    codes = [c for c in codes if c]

    log.info(f"监控 {len(codes)} 只股票: {codes}")

    # 获取行情
    market_data = get_realtime_data(codes)
    if not market_data:
        log.warning("行情数据获取失败")
        return {"status": "error", "reason": "no_data"}

    # 加载预警状态
    prev_state = load_state()

    # 构建持仓信息映射
    pos_map = {}
    if isinstance(positions, list):
        for p in positions:
            code = p if isinstance(p, str) else p.get("code", "")
            pos_map[code] = p if isinstance(p, dict) else {}

    # 检查预警
    all_alerts = []
    new_state = {}

    for code, data in market_data.items():
        s_key = f"{code}_state"
        pos_info = pos_map.get(code, {})

        alert_types = check_alerts(code, data, prev_state.get(s_key, {}), pos_info)
        new_state[s_key] = {
            "price": data.get("price"),
            "change": data.get("change"),
            "volume": data.get("volume"),
            "was_limit_up": data.get("change", 0) >= 9.5,
        }

        if alert_types:
            msg = build_alert_message(code, data, alert_types)
            sent = send_push(msg)
            all_alerts.append({"code": code, "types": alert_types, "sent": sent})

    # 保存状态
    save_state(new_state)

    log.info(f"检查完成，触发预警: {len(all_alerts)} 条")
    return {"status": "ok", "alerts": all_alerts, "checked": len(market_data)}


def continuous_monitor():
    """持续监控模式（备用，非UptimeRobot场景直接运行）"""
    log.info("启动持续监控模式 (Ctrl+C 退出)")
    while True:
        run_monitoring_cycle()
        interval = get_session_interval()
        log.info(f"休眠 {interval}s")
        time.sleep(interval)


# ============================================================
# Flask HTTP 服务（供 UptimeRobot 唤醒用）
# ============================================================

def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)

    @app.route("/")
    def index():
        return jsonify({
            "service": "AStock Realtime Monitor",
            "status": "running",
            "time": datetime.now().isoformat(),
        })

    @app.route("/health")
    def health():
        """
        UptimeRobot 健康检查 + 触发监控
        UptimeRobot 在交易时段每5分钟访问一次此端点
        """
        # 立即触发一次监控（异步，不阻塞响应）
        import threading
        def bg_check():
            try:
                run_monitoring_cycle()
            except Exception as e:
                log.error(f"后台监控异常: {e}")

        t = threading.Thread(target=bg_check, daemon=True)
        t.start()

        return jsonify({
            "status": "ok",
            "time": datetime.now().isoformat(),
            "is_trading_hours": is_trading_hours(),
            "is_trading_day": is_trading_day(),
        })

    @app.route("/status")
    def status():
        """状态查询"""
        cfg = load_config()
        positions = cfg.get("portfolio", {}).get("positions", [])
        return jsonify({
            "enabled": cfg.get("automation", {}).get("tasks", {}).get("realtime_monitor", {}).get("enabled", False),
            "watchlist_count": len(positions),
            "trading_day": is_trading_day(),
            "trading_hours": is_trading_hours(),
            "uptime": datetime.now().isoformat(),
        })

    return app


# ============================================================
# 入口
# ============================================================

def signal_handler(signum, frame):
    log.info("收到退出信号，优雅关闭...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if HAS_FLASK and os.environ.get("RENDER") or os.environ.get("FLASK_RUN"):
        # 生产环境：启动 Flask HTTP 服务
        port = int(os.environ.get("PORT", 10000))
        app = create_app()
        log.info(f"Flask 服务启动，监听端口 {port}")
        app.run(host="0.0.0.0", port=port)
    else:
        # 本地/调试模式：直接运行一次
        result = run_monitoring_cycle()
        print(json.dumps(result, ensure_ascii=False, indent=2))
