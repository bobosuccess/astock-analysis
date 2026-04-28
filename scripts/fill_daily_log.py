"""
每日操盘日志自动填充脚本
从akshare获取市场数据，填充到操盘日志模板

使用方法：
    python scripts/fill_daily_log.py [YYYY-MM-DD]
"""

import sys
import datetime
import yaml
import json
import subprocess
from pathlib import Path

# ========== 数据源配置 ==========
DATA_SOURCES = {
    "akshare": "主数据源（akshare）",
    "tencent": "备用1（腾讯财经）",
    "eastmoney": "备用2（东方财富）"
}


def get_market_data():
    """获取市场数据，多数据源备用"""
    try:
        import akshare as ak

        # 指数行情
        index_data = {}

        # 上证指数
        try:
            df = ak.stock_zh_index_spot()
            shanghai = df[df['名称'] == '上证指数'].iloc[0]
            sz = df[df['名称'] == '深证成指'].iloc[0]
            cyb = df[df['名称'] == '创业板指'].iloc[0]

            index_data = {
                "shanghai": {
                    "close": float(shanghai['最新价']),
                    "change_pct": float(shanghai['涨跌幅'])
                },
                "sz": {
                    "close": float(sz['最新价']),
                    "change_pct": float(sz['涨跌幅'])
                },
                "cyb": {
                    "close": float(cyb['最新价']),
                    "change_pct": float(cyb['涨跌幅'])
                }
            }
        except Exception as e:
            print(f"  [akshare] 指数数据获取失败: {e}")
            index_data = None

        # 涨跌家数
        try:
            df = ak.stock_board_quotes_spot()
            rising = len(df[df['涨跌幅'] > 0])
            falling = len(df[df['涨跌幅'] < 0])
            limit_up = len(df[df['涨跌幅'] >= 9.5])
            limit_down = len(df[df['涨跌幅'] <= -9.5])

            emotion = calc_emotion(limit_up, limit_down)
        except Exception as e:
            print(f"  [akshare] 涨跌家数获取失败: {e}")
            rising, falling, limit_up, limit_down, emotion = None, None, None, None, "未知"

        # 成交额
        try:
            df = ak.stock_spot_sse()
            total_amount = df['成交额'].sum() / 1e8  # 转为亿
        except:
            total_amount = None

        # 北向资金
        try:
            north = ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")
            north_flow = north['净流入'].sum() / 1e8
        except:
            north_flow = None

        # 板块排行
        try:
            board = ak.stock_board_industry_name_em()
            top3 = board.head(3)['板块名称'].tolist()
        except:
            top3 = []

        return {
            "index": index_data,
            "rising": rising,
            "falling": falling,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "emotion": emotion,
            "total_amount": total_amount,
            "north_flow": north_flow,
            "top3": top3,
            "source": "akshare"
        }

    except ImportError:
        print("  [错误] akshare 未安装，运行: pip install akshare")
        return None
    except Exception as e:
        print(f"  [错误] 数据获取失败: {e}")
        return None


def calc_emotion(limit_up, limit_down):
    """计算市场情绪"""
    if limit_up is None:
        return "未知"
    if limit_up >= 80:
        return "高潮"
    elif limit_up >= 40:
        return "回暖"
    elif limit_down >= 30:
        return "冰点"
    else:
        return "偏暖"


def get_portfolio_pnl():
    """从automation.yaml读取持仓，计算盈亏"""
    config_path = Path(__file__).parent.parent / "automation.yaml"
    if not config_path.exists():
        return []

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    positions = config.get('portfolio', {}).get('positions', [])
    if not positions:
        return []

    try:
        import akshare as ak

        results = []
        for pos in positions:
            code = pos.get('code', '')
            name = pos.get('name', '')
            shares = pos.get('shares', 0)
            cost = pos.get('cost', 0)
            direction = pos.get('direction', 'long')

            # 获取实时价格
            try:
                if code.startswith('6'):
                    symbol = f"sh{code}"
                else:
                    symbol = f"sz{code}"

                df = ak.stock_zh_a_spot_em(symbol=symbol)
                current_price = float(df['最新价'].iloc[0])

                if direction == 'long':
                    pnl = (current_price - cost) * shares
                else:
                    pnl = (cost - current_price) * shares

                results.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "cost": cost,
                    "current": current_price,
                    "pnl": pnl
                })
            except Exception as e:
                print(f"  [警告] 获取 {code} 价格失败: {e}")
                results.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "cost": cost,
                    "current": None,
                    "pnl": None
                })

        return results

    except ImportError:
        return []
    except Exception as e:
        print(f"  [错误] 持仓盈亏计算失败: {e}")
        return []


def format_market_data(data, pnl_list, target_date=None):
    """生成填充后的数据表格"""
    if target_date is None:
        target_date = datetime.date.today().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"# 📊 每日操盘日志 - {target_date}")
    lines.append("")
    lines.append("> **自动填充版本** | 数据来源：akshare | 更新时间：{datetime.datetime.now().strftime('%H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 【自动数据区】")
    lines.append("")

    if data:
        # 指数
        if data.get('index'):
            idx = data['index']
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            if idx.get('shanghai'):
                s = idx['shanghai']
                lines.append(f"| 上证指数 | {s['close']:.2f} / {s['change_pct']:+.2f}% |")
            if idx.get('sz'):
                s = idx['sz']
                lines.append(f"| 深证成指 | {s['close']:.2f} / {s['change_pct']:+.2f}% |")
            if idx.get('cyb'):
                s = idx['cyb']
                lines.append(f"| 创业板指 | {s['close']:.2f} / {s['change_pct']:+.2f}% |")
            lines.append("")

        # 涨跌家数
        lines.append("| 涨跌统计 | 数值 |")
        lines.append("|----------|------|")
        if data.get('rising') is not None:
            lines.append(f"| 上涨家数 | {data['rising']} |")
            lines.append(f"| 下跌家数 | {data['falling']} |")
            lines.append(f"| 涨停家数 | {data['limit_up']} |")
            lines.append(f"| 跌停家数 | {data['limit_down']} |")
        lines.append("")

        # 成交额 & 北向资金
        lines.append("| 资金面 | 数值 |")
        lines.append("|--------|------|")
        if data.get('total_amount'):
            lines.append(f"| 沪深成交额 | {data['total_amount']:.0f}亿 |")
        if data.get('north_flow') is not None:
            sign = "+" if data['north_flow'] >= 0 else ""
            lines.append(f"| 北向资金 | {sign}{data['north_flow']:.2f}亿 |")
        lines.append("")

        # 情绪 & 板块
        lines.append("| 情绪 & 板块 | 数值 |")
        lines.append("|------------|------|")
        lines.append(f"| 市场情绪 | **{data.get('emotion', '未知')}** |")
        if data.get('top3'):
            lines.append(f"| 板块排行(前3) | 1. {data['top3'][0]} |")
            if len(data['top3']) > 1:
                lines.append(f"| | 2. {data['top3'][1]} |")
            if len(data['top3']) > 2:
                lines.append(f"| | 3. {data['top3'][2]} |")
        lines.append("")

    else:
        lines.append("*数据获取失败，请检查网络或akshare安装状态*")
        lines.append("")

    # 持仓盈亏
    lines.append("**持仓盈亏**（读取自 automation.yaml）：")
    lines.append("")
    if pnl_list:
        lines.append("| 代码 | 名称 | 股数 | 成本 | 当前价 | 浮盈 |")
        lines.append("|------|------|------|------|--------|------|")
        for p in pnl_list:
            if p['current']:
                pnl_str = f"¥{p['pnl']:.2f}" if p['pnl'] else "-"
                lines.append(f"| {p['code']} | {p['name']} | {p['shares']} | ¥{p['cost']:.2f} | ¥{p['current']:.2f} | {pnl_str} |")
            else:
                lines.append(f"| {p['code']} | {p['name']} | {p['shares']} | ¥{p['cost']:.2f} | 获取失败 | - |")
    else:
        lines.append("*持仓为空，请在 automation.yaml 中配置*")
    lines.append("")

    # 数据来源
    source = data.get('source', 'N/A') if data else 'N/A'
    lines.append(f"> 数据来源：{source} | 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)


def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 40)
    print("📊 每日操盘日志 - 自动填充")
    print("=" * 40)

    # 获取市场数据
    print("\n[1/2] 获取市场数据...")
    data = get_market_data()

    # 获取持仓盈亏
    print("\n[2/2] 计算持仓盈亏...")
    pnl_list = get_portfolio_pnl()

    # 生成数据
    print("\n[完成] 生成自动数据区内容：")
    output = format_market_data(data, pnl_list, target_date)

    # 打印输出
    print("-" * 40)
    print(output)
    print("-" * 40)

    # 保存到文件
    if target_date:
        date_str = target_date.replace('-', '')
    else:
        date_str = datetime.date.today().strftime('%Y%m%d')

    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"auto_data_{date_str}.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\n✅ 已保存到：{output_file}")

    return output


if __name__ == "__main__":
    main()
