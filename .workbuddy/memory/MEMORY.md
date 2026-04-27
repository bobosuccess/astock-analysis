# MEMORY.md - 长期记忆

## 用户背景
- **身份**：Jenny King，顶级股票分析师
- **目标**：建立完整的A股智能投研系统
- **偏好**：免费方案、高信息密度、专业简洁

## 项目状态

### 个人作战台 v3.0
- 路径：`C:\Users\Jenny King\WorkBuddy\20260417115741\个人作战台\`
- **新增模块**：`📡 数据子系统`（2026-04-27）
  - 整合方案：`📡 数据子系统/数据模块整合方案.md`
  - 自动化控制：`⚙️ 系统配置/自动化控制面板.md`

### A股分析系统
- 路径：`C:\Users\Jenny King\WorkBuddy\20260426055457\`
- 状态：**已创建核心配置文件**（2026-04-27）

## 已创建的核心文件

| 文件 | 用途 |
|------|------|
| `automation.yaml` | 自动化开关配置（JSON/YAML格式，Python直接读取） |
| `.github/workflows/daily.yml` | GitHub Actions定时任务配置 |
| `requirements.txt` | Python依赖清单 |
| `scripts/config_reader.py` | 配置读取器（连接YAML和Python） |
| `scripts/push.py` | 推送模块（Server酱/Bark） |
| `scripts/morning_report.py` | 晨间简报脚本 |
| `scripts/after_close_batch.py` | 盘后批量脚本 |

## 技术栈决策

| 组件 | 方案 | 备注 |
|------|------|------|
| 数据源 | akshare + 3个备用 | 多源自动切换 |
| 实时监控 | Render免费容器 | 750h/月，剩余618h |
| 批量处理 | GitHub Actions | 2000min/天，剩余1940min |
| AI分析 | Groq/FeiFei API | 免费额度 |
| 推送 | Server酱 | 微信通知 |

### 多数据源备用方案
- 主数据源：akshare（实时行情）
- 备用1：baostock（历史回测）
- 备用2：腾讯财经（实时备用）
- 备用3：东方财富（资金流向）
- 备用4：新浪财经（新闻资讯）

## 自动化开关机制

- **配置文件**：`automation.yaml`
- **控制方式**：Python脚本直接读取YAML，无需Obsidian作为控制层
- **Obsidian定位**：仅作状态展示，不做控制
- **GitHub Secrets**：需配置 `SCKEY`、`GROQ_API_KEY`

## 用户反馈
- 对"免费"承诺敏感，需要诚实说明成本
- 拒绝"吹牛"，偏好务实方案
- 核心需求：通达信公式调试 + 24h在线 + 不占内存
- 需要自动化开关（Obsidian控制）
- 需要资源配额显示
- 需要多数据源备用

## 关键文件
- 整合方案：`个人作战台\📡 数据子系统\数据模块整合方案.md`
- 自动化控制：`个人作战台\⚙️ 系统配置/自动化控制面板.md`
- 核心原则：`个人作战台\⚙️ 系统配置/系统核心原则.md`
- 闭环架构：`个人作战台\🚀 快速开始/系统闭环架构.md`

## 待完成任务
- 配置 GitHub Secrets（SCKEY、GROQ_API_KEY）
- 完善各脚本的业务逻辑（当前为骨架）
- Render 容器部署（实时监控层）
