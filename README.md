# ArXiv论文追踪与分析器

一个基于 GitHub Actions 的自动化工具，每天早上自动追踪和分析 arXiv 最新论文，并通过邮件发送分析报告。该工具支持多种 AI 模型进行论文分析和总结。

## 功能特点

- 每天北京时间早上 10:40 自动运行（UTC 02:40）
- 自动追踪最近发布的 arXiv 论文（默认类别：数学偏微分方程 math.AP）
- 支持多种 AI 模型提供商（DeepSeek、OpenAI、智谱AI、通义千问、豆包、Kimi、OpenRouter、SiliconFlow 等）
- 智能主题分类：重点关注论文进行完整分析，了解领域论文翻译摘要
- 多线程并行处理，提高分析效率
- 内置缓存机制，避免重复分析
- 支持单论文分析和本地 PDF 分析
- 通过邮件发送分析报告
- 自动保存分析结果到 conclusion.md
- 自动清理下载的 PDF 文件以节省空间

## 安装与配置

1. Fork 或克隆仓库：
cd arxiv_paper_tracker
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填入您的API密钥和其他配置
```

3. 在 GitHub 仓库中，进入 **Settings → Secrets and variables → Actions**，点击 **Secrets** 标签页，添加以下敏感信息：

```
QWEN_API_KEY=sk-your-qwen-api-key
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
OPENAI_API_KEY=sk-your-openai-api-key
GLM_API_KEY=your-glm-api-key
DOUBAO_API_KEY=your-doubao-api-key
KIMI_API_KEY=your-kimi-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
SILICONFLOW_API_KEY=your-siliconflow-api-key
CUSTOM_API_KEY=your-custom-api-key
SMTP_USERNAME=your_qq@qq.com
SMTP_PASSWORD=your_qq_authorization_code
EMAIL_FROM=your_qq@qq.com
EMAIL_TO=recipient@email.com
```

**Secrets 配置说明：**
- 各个 AI 提供商的 API 密钥（只需配置您使用的提供商）
- `SMTP_USERNAME`: 发送邮件的邮箱账号
- `SMTP_PASSWORD`: 邮箱授权码（不是登录密码）
- `EMAIL_FROM`: 发件人邮箱（通常与SMTP_USERNAME相同）
- `EMAIL_TO`: 收件人邮箱（支持多个，用逗号分隔）

#### GitHub Variables 配置（非敏感配置）

在同一页面点击 **Variables** 标签页，添加以下可公开的配置：

```
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=50
SEARCH_DAYS=5
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo
MAX_THREADS=5
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
- `AI_PROVIDER`: AI提供商选择，支持 `deepseek`, `openai`, `glm`, `qwen`, `doubao`, `kimi`, `openrouter`, `siliconflow`, `custom`
- `AI_MODEL`: AI模型名称（默认 `qwen-turbo`）
- `MAX_THREADS`: 并行处理的最大线程数（默认5）
- `PRIORITY_TOPICS`: 重点关注主题，用 `|` 分隔，与之相关的论文会进行完整分析
- `SECONDARY_TOPICS`: 了解领域主题，用 `|` 分隔，与之相关的论文只翻译摘要
- `PRIORITY_ANALYSIS_DELAY`: 重点论文分析间隔时间（秒）
- `SECONDARY_ANALYSIS_DELAY`: 摘要翻译间隔时间（秒）
- `EMAIL_SUBJECT_PREFIX`: 邮件主题前缀

4. 安装依赖（本地测试时需要）：
```bash
pip install -r requirements.txt
```

## AI模型配置

系统支持多种AI模型提供商，您可以通过环境变量选择：

### 支持的AI提供商

| 提供商 | 环境变量 | 默认模型 | 获取API密钥 |
|--------|----------|----------|-------------|
| DeepSeek | `AI_PROVIDER=deepseek` | `deepseek-chat` | [DeepSeek官网](https://platform.deepseek.com/) |
| OpenAI | `AI_PROVIDER=openai` | `gpt-4` | [OpenAI官网](https://platform.openai.com/) |
| 智谱AI | `AI_PROVIDER=glm` | `glm-4` | [智谱AI](https://open.bigmodel.cn/) |
| 通义千问 | `AI_PROVIDER=qwen` | `qwen-turbo` | [通义千问](https://dashscope.aliyun.com/) |
| 豆包 | `AI_PROVIDER=doubao` | `doubao-pro` | [豆包官网](https://www.doubao.com/) |
| Kimi | `AI_PROVIDER=kimi` | `moonshot-v1-8k` | [Kimi官网](https://kimi.moonshot.cn/) |
| OpenRouter | `AI_PROVIDER=openrouter` | 根据模型 | [OpenRouter官网](https://openrouter.ai/) |
| SiliconFlow | `AI_PROVIDER=siliconflow` | 根据模型 | [SiliconFlow官网](https://siliconflow.cn/) |
| 自定义 | `AI_PROVIDER=custom` | 自定义 | 需配置 CUSTOM_API_BASE/CUSTOM_API_KEY |

### 配置示例

```bash
# 使用DeepSeek（默认）
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat

# 使用OpenAI GPT-4
AI_PROVIDER=openai
AI_MODEL=gpt-4

# 使用智谱AI
AI_PROVIDER=glm
AI_MODEL=glm-4

# 使用通义千问
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo

# 使用豆包
AI_PROVIDER=doubao
DOUBAO_API_KEY=your-doubao-api-key

# 使用Kimi
AI_PROVIDER=kimi
KIMI_API_KEY=your-kimi-api-key

# 使用智谱AI
AI_PROVIDER=glm
AI_MODEL=glm-4

# 使用自定义大模型API
AI_PROVIDER=custom
CUSTOM_API_KEY=your-custom-api-key
CUSTOM_API_BASE=https://your-custom-api.com/v1
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

### Windows 便捷脚本

双击运行项目根目录下的 `run_tracker.bat` 脚本，进入交互式菜单：

- 选择 1：运行全流程分析（抓取并分析最近论文）
- 选择 2：单论文分析（输入 arXiv ID 和可选页数）
- 选择 3：退出

脚本假设您已提前配置好虚拟环境和 `.env` 文件。

## 配置说明


### 命令行参数（本地运行）

除了 GitHub Actions 自动运行，您也可以在本地通过命令行运行，支持多种模式。

#### 批量模式

自动获取和分析最近论文（使用配置中的类别和时间范围）：

```bash
python src/main.py
```

指定日期分析：

```bash
# 分析指定日期
python src/main.py --date 2025-12-25

# 分析日期范围
python src/main.py --date 2025-12-20:2025-12-25
```

#### 单论文分析

通过 arXiv ID 分析指定论文：

```bash
# 分析前 10 页（默认）
python src/main.py --arxiv 2401.12345

# 分析前 20 页
python src/main.py --arxiv 2401.12345 -p 20

# 分析全部页
python src/main.py --arxiv 2401.12345 -p all
```

#### 本地 PDF 分析

直接分析本地 PDF 文件：

```bash
python src/main.py --pdf ./papers/some_paper.pdf -p 20
```

#### 缓存管理

查看和清理缓存：

```bash
# 显示缓存统计
python src/main.py --cache-stats

# 清除所有缓存
python src/main.py --clear-cache

# 清除特定类型缓存
python src/main.py --clear-cache classification
python src/main.py --clear-cache analysis
python src/main.py --clear-cache translation
```

**输出说明：**
- 批量模式结果保存在 `results/` 目录，文件名如 `arxiv_analysis_2025-02-07.md`
- 单论文分析结果文件名如 `arxiv_2401.12345_2025-02-07_22-56-45.md`
- 本地 PDF 分析结果文件名如 `pdf_some_paper_2025-02-07_22-56-45.md`

### 邮件配置
支持主流邮箱服务：
- QQ 邮箱：需要在邮箱设置中开启 SMTP 服务并获取授权码
- Gmail：需要开启两步验证并生成应用专用密码
- 其他邮箱：需要确保支持 SMTP 服务

### GitHub Actions 高级配置

**修改运行时间：**

在 `.github/workflows/daily_paper_analysis.yml` 中调整 cron 表达式：

```yaml
on:
  schedule:
    - cron: '40 2 * * *'  # UTC 时间，北京时间早上 10:40
```

**配置页面推送（可选）：**

如需自动推送分析结果到 Pages 仓库，需要添加：
- Secret: `GH_PAGES_TOKEN` - GitHub Personal Access Token（需要 repo 权限）
- 在 workflow 中修改 `if: github.repository == 'your-username/arxiv_paper_tracker'`

**工作流超时：**

默认超时时间为 40 分钟，可在 workflow 中调整：

```yaml
jobs:
  analyze-papers:
    timeout-minutes: 40







### 邮件配置
支持主流邮箱服务：
- QQ 邮箱：需要在邮箱设置中开启 SMTP 服务并获取授权码
- Gmail：需要开启两步验证并生成应用专用密码
- 其他邮箱：需要确保支持 SMTP 服务

## 故障排查

### 常见问题

**1. API 调用失败**

- 检查 API 密钥是否正确配置
- 确认 API 密钥是否有足够的配额
- 检查网络连接是否正常
- 如果遇到频率限制，可以增加 `PRIORITY_ANALYSIS_DELAY` 和 `SECONDARY_ANALYSIS_DELAY` 的值

**2. 邮件发送失败**

- 确认邮箱配置正确，特别是授权码/应用专用密码
- 检查 SMTP 服务器地址和端口是否正确
- QQ 邮箱必须使用授权码，不是登录密码
- Gmail 需要开启两步验证并生成应用专用密码

**3. 工作流超时**

- 默认超时时间为 40 分钟
- 如果论文数量较多或 PDF 较大，可能需要增加超时时间
- 可以减少 `MAX_PAPERS` 的值来减少处理时间
- 减少 `MAX_THREADS` 可能有助于降低并发压力

**4. PDF 下载失败**

- 某些 arXiv 论文可能没有 PDF 版本
- 检查网络连接是否正常
- 查看 GitHub Actions 日志获取详细错误信息

**5. 本地运行问题**

- 确保已安装所有依赖：`pip install -r requirements.txt`
- 检查 `.env` 文件是否正确配置
- Python 版本建议 3.8 或更高

### 调试技巧

**查看详细日志：**

```bash
# 本地运行时会显示详细日志
python src/main.py
```

**查看缓存状态：**

```bash
python src/main.py --cache-stats
```

**清除缓存重新分析：**

```bash
python src/main.py --clear-cache all
```

**分析单篇论文进行测试：**

```bash
python src/main.py --arxiv 2401.12345 -p 5
```

## 注意事项

- 确保配置的 AI API 密钥有效且有足够配额
- 邮箱配置正确（特别是授权码/应用专用密码）
- GitHub Actions 每月有 2000 分钟的免费额度，足够日常使用
- 如需修改运行时间，可以在 `.github/workflows/daily_paper_analysis.yml` 中调整 cron 表达式

## 许可证

MIT License 