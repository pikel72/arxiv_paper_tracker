# ArXiv论文追踪与分析器

一个基于 GitHub Actions 的自动化工具，每天早上自动追踪和分析 arXiv 最新论文，并通过邮件发送分析报告。该工具使用 DeepSeek AI 进行论文分析和总结。

## 功能特点

- 每天早上 8 点自动运行（UTC+8）
- 自动追踪最近发布的 AI、机器学习和 NLP 类别的论文
- 使用 DeepSeek AI 进行论文分析和总结
- 通过邮件发送分析报告
- 自动保存分析结果到 conclusion.md
- 自动清理下载的 PDF 文件以节省空间

## 安装与配置

1. Fork 或克隆仓库：
```bash
git clone https://github.com/你的用户名/arxiv_paper_tracker.git
cd arxiv_paper_tracker
```

在 GitHub 仓库中，进入 **Settings → Secrets and variables → Actions**，点击 **Secrets** 标签页，添加以下敏感信息：

```
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_qq@qq.com
SMTP_PASSWORD=your_qq_authorization_code
EMAIL_FROM=your_qq@qq.com
EMAIL_TO=recipient@email.com
```

**Secrets 配置说明：**
- `DEEPSEEK_API_KEY`: 从 [DeepSeek 官网](https://platform.deepseek.com/) 获取的 API 密钥
- `SMTP_SERVER`: 邮件服务器地址
- `SMTP_PORT`: SMTP 端口（QQ邮箱建议使用587）
- `SMTP_USERNAME`: 发送邮件的邮箱账号
- `SMTP_PASSWORD`: 邮箱授权码（不是登录密码）
- `EMAIL_FROM`: 发件人邮箱（通常与SMTP_USERNAME相同）
- `EMAIL_TO`: 收件人邮箱

#### GitHub Variables 配置（非敏感配置）

在同一页面点击 **Variables** 标签页，添加以下可公开的配置：

```
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=40
SEARCH_DAYS=7
PRIORITY_TOPICS=Navier-Stokes方程|Euler方程|湍流|涡度
SECONDARY_TOPICS=色散偏微分方程|调和分析|极大算子
PRIORITY_ANALYSIS_DELAY=3
SECONDARY_ANALYSIS_DELAY=2
EMAIL_SUBJECT_PREFIX=ArXiv论文分析报告
```

**Variables 配置说明：**
- `ARXIV_CATEGORIES`: ArXiv 论文类别，用逗号分隔（如：`math.AP,math.NA`）
- `MAX_PAPERS`: 每次获取的最大论文数量
- `SEARCH_DAYS`: 搜索最近几天的论文
- `PRIORITY_TOPICS`: 重点关注主题，用 `|` 分隔，与之相关的论文会进行完整分析
- `SECONDARY_TOPICS`: 了解领域主题，用 `|` 分隔，与之相关的论文只翻译摘要
- `PRIORITY_ANALYSIS_DELAY`: 重点论文分析间隔时间（秒）
- `SECONDARY_ANALYSIS_DELAY`: 摘要翻译间隔时间（秒）
- `EMAIL_SUBJECT_PREFIX`: 邮件主题前缀

4. 安装依赖（本地测试时需要）：
```bash
pip install -r requirements.txt
```

## 使用方法

### 自动运行
- 工作流会在每天早上 8 点（北京时间）自动运行
- 运行结果会：
  1. 发送到配置的邮箱
  2. 保存在 conclusion.md 文件中
  3. 自动提交到仓库

### 手动触发
1. 在仓库的 Actions 页面
2. 选择 "Daily Paper Analysis" 工作流
3. 点击 "Run workflow"
4. 选择 "Run workflow" 确认运行

## 配置说明



### 邮件配置
支持主流邮箱服务：
- QQ 邮箱：需要在邮箱设置中开启 SMTP 服务并获取授权码
- Gmail：需要开启两步验证并生成应用专用密码
- 其他邮箱：需要确保支持 SMTP 服务

## 注意事项

- 确保 DeepSeek API 密钥有效
- 邮箱配置正确（特别是授权码/应用专用密码）
- GitHub Actions 每月有 2000 分钟的免费额度，足够日常使用
- 如需修改运行时间，可以在 `.github/workflows/daily_paper_analysis.yml` 中调整 cron 表达式

## 许可证

MIT License 