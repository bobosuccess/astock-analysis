# A股分析系统 v2.0 架构升级方案

> 基于个人作战台设计理念重构 | 版本：v2.0 | 日期：2026-04-26

---

## 一、升级核心思路

### 1.1 当前问题

```
获取数据 → 生成报告 → 结束
     ↓
   数据孤岛，无法形成闭环
```

### 1.2 升级目标

```
资讯输入 → 数据获取 → 因子计算 → 信号分析 → 交易记录 → 收益复盘 → 策略优化
```

### 1.3 六大原则（沿用个人作战台）

| 原则 | 实现 |
|------|------|
| **有身份** | 系统人格：严谨、数据驱动的A股分析师 |
| **有记忆** | MEMORY.md + 每日笔记 + 历史信号库 |
| **有技能** | akshare数据 + 技术指标计算 + 信号生成 |
| **能分身** | 并行获取多只股票 + 多因子同时计算 |
| **能自动** | 盘后自动运行 + 定时生成简报 |
| **克服人性** | 预设止损/止盈规则 + 强制信号审核 |

---

## 二、目录架构

```
A股分析系统/
│
├── 📂 config/                      # 配置层
│   ├── system_config.json           # 主配置（股票池、Token、路径）
│   ├── indicators_config.json       # 指标参数（RSI/MACD/布林带阈值）
│   └── risk_rules.json              # 风控规则（止损/止盈/仓位）
│
├── 📂 data/                        # 数据层
│   ├── raw/                        # 原始行情数据
│   │   └── {code}_{date}.csv
│   ├── factors/                    # 因子计算结果
│   │   └── {code}_factors.csv
│   └── signals/                    # 信号记录
│       └── {date}_signals.csv
│
├── 📂 scripts/                     # 执行层
│   ├── 01_data_fetch.py            # 数据获取
│   ├── 02_indicator_calc.py         # 指标计算
│   ├── 03_signal_generator.py      # 信号生成
│   ├── 04_risk_check.py            # 风控检查
│   ├── 05_trade_record.py          # 交易记录
│   └── 06_daily_report.py          # 日报生成
│
├── 📂 reports/                     # 报告层
│   ├── daily/                      # 每日报告
│   ├── weekly/                     # 周报
│   └── backtest/                   # 回测报告
│
├── 📂 memory/                      # 记忆层
│   ├── MEMORY.md                   # 长期记忆
│   ├── signals_history.md          # 信号历史
│   └── trades_history.md           # 交易历史
│
├── 📂 notebooks/                   # 分析层（可选）
│   └── factor_analysis.ipynb
│
├── main.py                         # 主入口
├── run_daily.py                    # 每日自动运行
└── config_checker.py               # 配置检查工具
```

---

## 三、核心模块设计

### 3.1 数据获取模块（01_data_fetch.py）

```python
# 功能：并行获取多只股票行情数据
# 升级点：从串行改为并行，添加重试机制

import akshare as ak
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

class DataFetcher:
    def __init__(self, stocks, days=30):
        self.stocks = stocks
        self.days = days
        self.data = {}
    
    def fetch_all(self):
        """并行获取所有股票数据"""
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.fetch_one, code): code 
                      for code in self.stocks}
            for future in futures:
                code = futures[future]
                try:
                    self.data[code] = future.result()
                except Exception as e:
                    self.data[code] = {'error': str(e)}
        return self.data
    
    def fetch_one(self, code):
        """获取单只股票数据"""
        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=self.days)).strftime('%Y%m%d')
        df = ak.stock_zh_a_hist(symbol=code.split('.')[0],
                                 start_date=start, end_date=end, adjust="qfq")
        return df
```

### 3.2 指标计算模块（02_indicator_calc.py）

```python
# 功能：计算技术指标
# 升级点：从单纯获取数据升级为计算指标

import pandas as pd
import numpy as np

class IndicatorCalculator:
    def __init__(self, df):
        self.df = df
    
    def calculate_all(self):
        """计算全部指标"""
        self.df = self.calc_ma()
        self.df = self.calc_rsi()
        self.df = self.calc_macd()
        self.df = self.calc_boll()
        self.df = self.calc_volume()
        return self.df
    
    def calc_ma(self, periods=[5, 10, 20, 60]):
        """移动平均线"""
        for p in periods:
            self.df[f'MA{p}'] = self.df['收盘'].rolling(p).mean()
        return self.df
    
    def calc_rsi(self, period=14):
        """RSI相对强弱指标"""
        delta = self.df['收盘'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))
        return self.df
    
    def calc_macd(self, fast=12, slow=26, signal=9):
        """MACD指标"""
        ema_fast = self.df['收盘'].ewm(span=fast).mean()
        ema_slow = self.df['收盘'].ewm(span=slow).mean()
        self.df['DIF'] = ema_fast - ema_slow
        self.df['DEA'] = self.df['DIF'].ewm(span=signal).mean()
        self.df['MACD'] = (self.df['DIF'] - self.df['DEA']) * 2
        return self.df
    
    def calc_boll(self, period=20, std=2):
        """布林带"""
        self.df['BOLL_MID'] = self.df['收盘'].rolling(period).mean()
        self.df['BOLL_UPPER'] = self.df['BOLL_MID'] + std * self.df['收盘'].rolling(period).std()
        self.df['BOLL_LOWER'] = self.df['BOLL_MID'] - std * self.df['收盘'].rolling(period).std()
        return self.df
    
    def calc_volume(self):
        """量价指标"""
        self.df['VOL_MA5'] = self.df['成交量'].rolling(5).mean()
        self.df['VOL_RATIO'] = self.df['成交量'] / self.df['VOL_MA5']
        self.df['PRICE_RATE'] = self.df['收盘'] / self.df['开盘']
        return self.df
```

### 3.3 信号生成模块（03_signal_generator.py）

```python
# 功能：根据指标生成交易信号
# 升级点：增加信号评分机制

class SignalGenerator:
    def __init__(self, df, config):
        self.df = df
        self.config = config
    
    def generate(self):
        """生成综合信号"""
        signals = {
            'MA_GOLDEN': self.check_ma_golden(),      # 均线金叉
            'MA_DEATH': self.check_ma_death(),        # 均线死叉
            'RSI_OVERBUY': self.check_rsi_overbuy(),  # RSI超买
            'RSI_OVERSELL': self.check_rsi_oversell(),# RSI超卖
            'MACD_CROSS_UP': self.check_macd_cross_up(),   # MACD金叉
            'MACD_CROSS_DOWN': self.check_macd_cross_down(),# MACD死叉
            'BOLL_BREAK_UP': self.check_boll_break_up(),   # 布林上轨突破
            'BOLL_BREAK_DOWN': self.check_boll_break_down(),# 布林下轨突破
        }
        
        # 计算综合评分
        score = sum([1 for v in signals.values() if v]) - sum([1 for v in signals.values() if v == False])
        signals['SCORE'] = score
        
        return signals
    
    def check_ma_golden(self):
        """MA5上穿MA10金叉"""
        if len(self.df) < 2:
            return None
        return self.df.iloc[-1]['MA5'] > self.df.iloc[-1]['MA10'] and \
               self.df.iloc[-2]['MA5'] <= self.df.iloc[-2]['MA10']
```

### 3.4 风控检查模块（04_risk_check.py）

```python
# 功能：执行风控规则检查
# 升级点：沿用个人作战台"克服人性"设计

class RiskChecker:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.rules = json.load(f)
    
    def check(self, signal, current_price, cost_price=None):
        """执行风控检查"""
        checks = []
        
        # 止损检查
        if cost_price:
            loss_ratio = (current_price - cost_price) / cost_price
            if loss_ratio <= -self.rules['stop_loss']:
                checks.append({
                    'action': 'SELL',
                    'reason': f'触发止损线 -{self.rules["stop_loss"]*100}%',
                    'priority': 'HIGH'
                })
        
        # 止盈检查
        if cost_price:
            profit_ratio = (current_price - cost_price) / cost_price
            if profit_ratio >= self.rules['take_profit']:
                checks.append({
                    'action': 'SELL',
                    'reason': f'达到止盈目标 +{self.rules["take_profit"]*100}%',
                    'priority': 'MEDIUM'
                })
        
        # RSI超买检查
        if signal.get('RSI_OVERBUY'):
            checks.append({
                'action': 'WATCH',
                'reason': 'RSI超买，谨慎追高',
                'priority': 'LOW'
            })
        
        return checks
```

---

## 四、主入口设计

### 4.1 main.py

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股分析系统 v2.0 主入口
遵循六大原则：有身份、有记忆、有技能、能分身、能自动、克服人性
"""

import json
import os
from datetime import datetime
from scripts.data_fetch import DataFetcher
from scripts.indicator_calc import IndicatorCalculator
from scripts.signal_generator import SignalGenerator
from scripts.risk_check import RiskChecker
from scripts.daily_report import DailyReport

class AStockSystem:
    """A股分析系统主类"""
    
    def __init__(self, config_path='config/system_config.json'):
        self.config = self.load_config(config_path)
        self.results = {}
        self.signals = []
        
    def load_config(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run(self):
        """主运行流程"""
        print(f"[{self.get_time()}] 系统启动")
        
        # 1. 获取数据（分身）
        print("[1/5] 获取行情数据...")
        fetcher = DataFetcher(self.config['stocks'])
        raw_data = fetcher.fetch_all()
        
        # 2. 计算指标
        print("[2/5] 计算技术指标...")
        for code, df in raw_data.items():
            if 'error' not in df:
                calc = IndicatorCalculator(df)
                self.results[code] = calc.calculate_all()
        
        # 3. 生成信号
        print("[3/5] 生成交易信号...")
        indicator_config = self.config.get('indicators', {})
        for code, df in self.results.items():
            gen = SignalGenerator(df, indicator_config)
            signal = gen.generate()
            self.signals.append({'code': code, **signal})
        
        # 4. 风控检查
        print("[4/5] 执行风控检查...")
        checker = RiskChecker('config/risk_rules.json')
        for s in self.signals:
            checks = checker.check(s, self.results[s['code']].iloc[-1]['收盘'])
            s['risk_checks'] = checks
        
        # 5. 生成报告
        print("[5/5] 生成分析报告...")
        report = DailyReport(self.signals, self.results)
        report.generate()
        
        print(f"[{self.get_time()}] 分析完成")
        return self.signals
    
    def get_time(self):
        return datetime.now().strftime('%H:%M:%S')

if __name__ == '__main__':
    system = AStockSystem()
    system.run()
```

### 4.2 run_daily.py（自动化）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日定时运行脚本
注册到Windows任务计划程序，实现盘后自动运行
"""

import schedule
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    filename='logs/run.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def job():
    """每日盘后任务"""
    logging.info("=" * 50)
    logging.info(f"开始执行: {datetime.now()}")
    
    try:
        from main import AStockSystem
        system = AStockSystem()
        signals = system.run()
        logging.info(f"完成，生成 {len(signals)} 个信号")
    except Exception as e:
        logging.error(f"执行失败: {e}")
    
    logging.info("=" * 50)

# 每天16:30执行（A股收盘后30分钟）
schedule.every().day.at("16:30").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 五、配置规范

### 5.1 system_config.json

```json
{
    "stocks": [
        "000001.SZ",
        "000002.SZ",
        "000858.SZ",
        "600519.SH",
        "000333.SZ"
    ],
    "data_days": 60,
    "indicators": {
        "rsi_period": 14,
        "rsi_overbuy": 70,
        "rsi_oversell": 30,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "boll_period": 20,
        "boll_std": 2
    },
    "paths": {
        "data": "data",
        "reports": "reports",
        "memory": "memory"
    }
}
```

### 5.2 risk_rules.json

```json
{
    "stop_loss": 0.08,
    "take_profit": 0.15,
    "max_position_single": 0.20,
    "max_position_total": 0.80,
    "max_hold_count": 5,
    "min_rsi_to_buy": 50,
    "max_rsi_to_buy": 75
}
```

---

## 六、升级前后对比

| 维度 | v1.0 | v2.0 |
|------|------|------|
| **代码结构** | 单文件150行 | 6个模块+配置驱动 |
| **数据处理** | 串行获取 | 并行获取+重试 |
| **指标能力** | 仅获取 | RSI/MACD/布林带/均线 |
| **信号生成** | 无 | 综合评分机制 |
| **风控** | 无 | 止损/止盈/仓位规则 |
| **记忆** | 无 | MEMORY.md+历史记录 |
| **自动化** | 手动运行 | 定时+日志 |
| **报告** | 文本文件 | 结构化报告 |

---

## 七、实施计划

| 阶段 | 时间 | 内容 |
|------|------|------|
| **Phase 1** | Day 1 | 创建目录结构，迁移配置 |
| **Phase 2** | Day 2 | 实现数据获取+指标计算模块 |
| **Phase 3** | Day 3 | 实现信号生成+风控检查模块 |
| **Phase 4** | Day 4 | 实现日报生成+记忆系统 |
| **Phase 5** | Day 5 | 配置自动化任务+测试 |

预计开发时间：5个工作日
