# 配置读取器
# 用于读取 automation.yaml 配置

import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_PATH = Path(__file__).parent / "automation.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    """加载并缓存配置文件"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_enabled(task_name: str) -> bool:
    """检查任务是否开启"""
    cfg = load_config()
    if not cfg["automation"]["master_switch"]:
        return False
    return cfg["automation"]["tasks"].get(task_name, {}).get("enabled", False)


def get_layer_enabled(layer_name: str) -> bool:
    """检查分层开关"""
    cfg = load_config()
    if not cfg["automation"]["master_switch"]:
        return False
    return cfg["automation"]["layers"].get(layer_name, {}).get("enabled", False)


def is_push_enabled() -> bool:
    """推送是否开启"""
    return get_layer_enabled("push_notification")


def get_data_source(data_type: str) -> list:
    """获取数据源优先级列表"""
    cfg = load_config()
    sources = cfg["data_sources"].get(data_type, {})
    priority = []
    for key in ["primary", "backup1", "backup2"]:
        if key in sources:
            priority.append(sources[key])
    return priority


def get_quota_alert() -> dict:
    """获取配额预警阈值"""
    return load_config()["quota_alert"]


def get_config() -> dict:
    """获取完整配置"""
    return load_config()


def get_portfolio() -> list:
    """获取持仓配置列表"""
    cfg = load_config()
    positions = cfg.get("portfolio", {}).get("positions", [])
    if not positions:
        return []
    return positions


def get_task_config(task_name: str) -> dict:
    """获取指定任务的配置"""
    cfg = load_config()
    return cfg["automation"]["tasks"].get(task_name, {})


if __name__ == "__main__":
    # 测试
    print("=== 自动化开关状态 ===")
    print(f"总开关: {load_config()['automation']['master_switch']}")
    print(f"\n晨间简报: {'开启' if is_enabled('morning_report') else '关闭'}")
    print(f"实时监控: {'开启' if is_enabled('realtime_monitor') else '关闭'}")
    print(f"晚间简报: {'开启' if is_enabled('evening_report') else '关闭'}")
    print(f"晚间复盘: {'开启' if is_enabled('evening_review') else '关闭'}")
    print(f"\n微信推送: {'开启' if is_push_enabled() else '关闭'}")
    print(f"\n=== 持仓配置 ===")
    positions = get_portfolio()
    if not positions:
        print("⚠️ 未配置持仓，请编辑 automation.yaml 的 portfolio.positions")
    else:
        for p in positions:
            print(f"• {p.get('name')} ({p.get('code')}): {p.get('shares')}股 @ {p.get('cost')}元")
