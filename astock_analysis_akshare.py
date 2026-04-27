# A股分析代码 - akshare 免费版
# 无需 Token，无权限限制

import akshare as ak
import json
import os
from datetime import datetime, timedelta

# ========== 1. 路径配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'system_config.json')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')
DATA_DIR = os.path.join(BASE_DIR, 'results')

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ========== 2. 加载配置 ==========
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
except Exception as e:
    print(f"配置文件读取失败: {e}")
    config = {'stocks': ['000001.SZ', '600519.SH']}

stocks = config.get('stocks', ['000001.SZ', '600519.SH'])

# ========== 3. 设置日期 ==========
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

# ========== 4. 获取数据 ==========
all_data = {}
data_lines = []

for code in stocks:
    try:
        # akshare 获取日线数据
        df = ak.stock_zh_a_hist(symbol=code.split('.')[0], 
                                start_date=start_date, 
                                end_date=end_date,
                                adjust="qfq")
        
        if df is not None and len(df) > 0:
            all_data[code] = df
            price = df.iloc[0]['收盘']
            change = df.iloc[0]['涨跌幅']
            data_lines.append(f"{code}: 最新价 {price:.2f}  涨跌幅 {change:+.2f}%")
        else:
            data_lines.append(f"{code}: 无数据")
    except Exception as e:
        data_lines.append(f"{code}: 获取失败 - {e}")

# ========== 5. 生成报告 ==========
timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
report_path = os.path.join(REPORT_DIR, f'报告_{timestamp}.txt')

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

with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_content))

print(f"报告已保存: {report_path}")

# ========== 6. 保存数据 ==========
for code, df in all_data.items():
    safe_code = code.replace(':', '-')
    data_path = os.path.join(DATA_DIR, f"{safe_code}_{timestamp}.csv")
    df.to_csv(data_path, index=False, encoding='utf-8-sig')

# ========== 7. 完成 ==========
print("分析完成")
print(f"数据获取: {len(all_data)}/{len(stocks)} 只股票")
print(f"报告路径: {report_path}")
