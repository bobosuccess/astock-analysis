# 📡 Render 实时监控容器部署指南

> 部署平台：Render Free Tier（750小时/月，休眠机制：无请求15分钟后自动休眠）
> 代码仓库：https://github.com/bobosuccess/astock-analysis

---

## 一、部署步骤

### 步骤1：推送代码到 GitHub
```bash
cd c:/Users/Jenny King/WorkBuddy/20260426055457
git add .
git commit -m "feat: realtime monitor + render deployment"
git push origin main
```

### 步骤2：Render 连接 GitHub
1. 访问 https://render.com → Sign Up / Login
2. Dashboard → New → Web Service
3. 连接到 GitHub → 选择 `bobosuccess/astock-analysis` 仓库
4. 配置如下：
   - **Name**: `astock-realtime-monitor`
   - **Region**: Oregon
   - **Branch**: main
   - **Root Directory**: （留空）
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python scripts/realtime_monitor.py`
   - **Plan**: Free

### 步骤3：配置环境变量（Render Dashboard → Environment）
| 变量名 | 值 | 说明 |
|--------|-----|------|
| `SCKEY` | 你的Server酱SCKEY | 微信推送必需 |
| `PYTHONIOENCODING` | `utf-8` | 编码修复 |
| `RENDER` | `true` | 标识运行环境 |

### 步骤4：部署
- 点击 "Create Web Service"
- 等待 Build 完成（首次约2-3分钟）
- 查看日志确认启动成功

---

## 二、配置自选股池

在 `automation.yaml` 中修改：

```yaml
portfolio:
  positions:
    # 简单格式（只监控，不设止损）
    - "000001.SZ"     # 平安银行
    - "600519.SS"     # 贵州茅台

    # 完整格式（监控 + 止损价）
    - code: "000001.SZ"
      stop_loss: 12.00   # 止损价（元）
```

修改后提交 GitHub，Render 自动重新部署（Auto-Deploy: Enabled）。

---

## 三、预警类型说明

| 类型 | 触发条件 | 推送优先级 |
|------|---------|-----------|
| 🔴 涨停预警 | 涨幅 ≥ 9.5% | 高 |
| 🟠 炸板预警 | 从涨停板打开 | 高 |
| ⚠️ 急跌预警 | 5分钟内下跌 ≥ 3% | 中 |
| 🔵 大跌预警 | 当日跌幅 ≤ -5% | 高 |
| 💥 放量异动 | 量能≥3倍 且 涨幅≥3% | 中 |
| 🛑 止损触发 | 价格 ≤ 止损价 | 最高 |

轮询间隔：交易时段 5分钟 / 非交易时段 30分钟（休市自动切换）。

---

## 四、监控状态持久化

Render Free 无持久磁盘。状态文件 `data/monitor_state.json` 每次轮询保存，下次启动时从 GitHub Actions 同步。

**注意**：止损/涨停状态不跨容器实例保留，重启后需重新建立基准。

---

## 五、成本说明

| 资源 | Free Tier | 说明 |
|------|-----------|------|
| 运行时间 | 750h/月 | 休眠后不计时 |
| 内存 | 512MB | akshare 够用 |
| 磁盘 | 无持久化 | 每次重启清空 |
| 休眠 | 15分钟无请求 | 自动休眠 |

**月估算**（交易日约22天）：
- 每天运行 5.5h = 121h/月
- 休眠时间 648h/月
- 合计 769h → 略超750h限制

**解决方案**：工作日 9:00 开启 / 周末手动暂停，或升级到 $7/月 Hobby Tier。
