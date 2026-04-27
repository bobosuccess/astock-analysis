# GitHub 部署指南

## 1. 创建 GitHub 仓库

1. 登录 GitHub → 点击右上角 `+` → `New repository`
2. 仓库名称：`astock-analysis`
3. 选择 `Private`（私有仓库）
4. 不要勾选 Initialize repository
5. 点击 `Create repository`

## 2. 本地初始化（PowerShell）

```powershell
# 进入项目目录
cd "C:\Users\Jenny King\WorkBuddy\20260426055457"

# 初始化 Git
git init
git add .
git commit -m "feat: A股分析系统框架初始化

- automation.yaml: 自动化开关配置
- .github/workflows/daily.yml: GitHub Actions
- requirements.txt: Python依赖
- scripts/: 核心脚本（配置读取/推送/晨间简报/盘后批量）"

# 添加远程仓库（替换 YOUR_USERNAME 为你的GitHub用户名）
git remote add origin https://github.com/YOUR_USERNAME/astock-analysis.git

# 推送
git branch -M main
git push -u origin main
```

## 3. 配置 Secrets

1. 进入 GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions`
2. 添加以下 Secrets：

| Name | Value |
|------|-------|
| `SCKEY` | 你的Server酱SCKEY |
| `GROQ_API_KEY` | 你的Groq API Key（可选，先不加） |

## 4. 测试 Actions

1. 进入仓库 → `Actions` 标签页
2. 点击左侧 `A股分析系统 - 每日自动化`
3. 点击 `Run workflow` → 选择 `all` → 点击 `Run workflow`
4. 查看运行结果

---

## 5. 验证清单

- [ ] GitHub 仓库创建成功
- [ ] 代码已推送
- [ ] SCKEY 已配置
- [ ] Actions 手动触发成功
- [ ] Server酱收到测试消息

---

## 6. 注意事项

1. **不要提交敏感信息**：确保 `automation.yaml` 中的 `YOUR_SCKEY_HERE` 已被替换
2. **代理问题**：本地运行需要取消代理，GitHub Actions 不需要
3. **定时任务**：Actions 已配置每日07:00自动运行
