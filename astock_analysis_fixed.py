# A股分析代码 - 修正版
# 兼容 Windows 路径，支持配置文件读取

import tushare as ts
import json
import os
from datetime import datetime, timedelta

# ========== 1. 路径配置 ==========
# 使用相对路径或绝对路径，避免 Google Colab 格式
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'system_config.json')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')
DATA_DIR = os.path.join(BASE_DIR, 'results')

# 确保目录存在
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ========== 2. 加载配置 ==========
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"配置文件不存在: {CONFIG_PATH}")
    print("请创建 config/system_config.json 文件，内容示例：")
    print('{"api_config": {"tushare_token": "你的Token"}, "stocks": ["000001.SZ", "600519.SH"]}')
    raise
except json.JSONDecodeError as e:
    print(f"配置文件格式错误: {e}")
    raise

# ========== 3. 设置 Token ==========
token = config.get('api_config', {}).get('tushare_token', '')
if not token:
    raise ValueError("配置文件中未找到 tushare_token")
ts.set_token(token)
pro = ts.pro_api()

# ========== 4. 获取股票列表 ==========
stocks = config.get('stocks', ['000001.SZ', '600519.SH'])

# ========== 5. 设置日期参数 ==========
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

# ========== 6. 获取数据 ==========
all_data = {}
data_lines = []

for code in stocks:
    try:
        df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
        if df is not None and len(df) > 0:
            all_data[code] = df
            price = df.iloc[0]['close']
            data_lines.append(f"{code}: {len(df)}条数据，最新价 {price:.2f}")
        else:
            data_lines.append(f"{code}: 无数据")
    except Exception as e:
        # 输出具体错误信息
        data_lines.append(f"{code}: 获取失败 - {e}")

# ========== 7. 生成报告 ==========
# Windows 文件名禁止使用冒号，替换为下划线
timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

report_path = os.path.join(REPORT_DIR, f'报告_{timestamp}.txt')

# 构建报告内容
report_content = [
    "=" * 60,
    "A股分析报告",
    f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "=" * 60,
    "",
    "数据获取概览",
    "-" * 40,
]
report_content.extend(data_lines)

report_content.extend([
    "",
    "系统状态",
    "-" * 40,
    f"分析股票数量: {len(stocks)}只",
    f"成功获取数据: {len(all_data)}只",
    "",
    "=" * 60,
    "报告生成完成",
    "=" * 60,
])

# 写入文件 - 修正：使用正确的换行符语法
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_content))  # 一次性写入，避免逐行问题

print(f"报告已保存: {report_path}")

# ========== 8. 保存数据 ==========
for code, df in all_data.items():
    # Windows 文件名禁止使用冒号
    safe_code = code.replace(':', '-')
    data_path = os.path.join(DATA_DIR, f"{safe_code}_{timestamp}.csv")
    df.to_csv(data_path, index=False, encoding='utf-8-sig')

# ========== 9. 完成 ==========
print("分析完成")
print(f"数据获取: {len(all_data)}/{len(stocks)} 只股票")
print(f"报告路径: {report_path}")
