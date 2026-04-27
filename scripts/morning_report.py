# 晨间简报脚本
# 触发时间: 每天07:00 (北京时间)

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_reader import is_enabled, is_push_enabled
from scripts.push import serverchan_push


def main():
    if not is_enabled("morning_report"):
        print("[跳过] 晨间简报开关已关闭")
        return

    print("=" * 50)
    print("生成晨间简报...")
    print("=" * 50)

    # TODO: 实现晨间简报逻辑
    # 1. 获取隔夜外盘数据
    # 2. 获取A股最新数据
    # 3. 生成盘前预判
    # 4. 推送微信

    content = "📊 晨间简报\n\n"
    content += "• 外盘: 美股微涨\n"
    content += "• A股: 震荡偏多\n"
    content += "• 建议: 观察开盘量能"

    if is_push_enabled():
        serverchan_push("晨间简报", content)

    print("晨间简报完成")


if __name__ == "__main__":
    main()
