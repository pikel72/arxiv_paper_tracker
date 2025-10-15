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
cd arxiv_paper_tracker
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填入您的API密钥和其他配置
```

3. 在 GitHub 仓库中，进入 **Settings → Secrets and variables → Actions**，点击 **Secrets** 标签页，添加以下敏感信息：

```
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
OPENAI_API_KEY=sk-your-openai-api-key
GLM_API_KEY=your-glm-api-key
QWEN_API_KEY=sk-your-qwen-api-key
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_qq@qq.com
SMTP_PASSWORD=your_qq_authorization_code
EMAIL_FROM=your_qq@qq.com
EMAIL_TO=recipient@email.com
```

**Secrets 配置说明：**
- `DEEPSEEK_API_KEY`: 从 [DeepSeek 官网](https://platform.deepseek.com/) 获取的 API 密钥
- `OPENAI_API_KEY`: 从 [OpenAI 官网](https://platform.openai.com/) 获取的 API 密钥
- `GLM_API_KEY`: 从 [智谱AI](https://open.bigmodel.cn/) 获取的 API 密钥
- `QWEN_API_KEY`: 从 [通义千问](https://dashscope.aliyun.com/) 获取的 API 密钥
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
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
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
- `AI_PROVIDER`: AI提供商选择，支持 `deepseek`, `openai`, `glm`
- `AI_MODEL`: AI模型名称（如：`deepseek-chat`, `gpt-4`, `glm-4`）
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
| 豆包 | `AI_PROVIDER=doubao` | `doubao-chat` | [豆包官网](https://www.doubao.com/) |
| Kimi | `AI_PROVIDER=kimi` | `kimi-gpt` | [Kimi官网](https://kimi.moonshot.cn/) |
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
# DOUBAO_API_BASE 可选，默认 https://openapi.doubao.com/v1

# 使用Kimi
AI_PROVIDER=kimi
KIMI_API_KEY=your-kimi-api-key
# KIMI_API_BASE 可选，默认 https://api.kimi.com/v1

# 使用自定义大模型API
AI_PROVIDER=custom
CUSTOM_API_KEY=your-custom-api-key
CUSTOM_API_BASE=https://your-custom-api.com/v1


# 使用智谱AI
AI_PROVIDER=glm
AI_MODEL=glm-4
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


### 单论文分析（本地命令行）

支持直接分析指定 arXiv 论文，适合单篇精读或补充分析。

**命令格式：**

```bash
python src/main.py --single <arxiv_id> [-p <页数或all>]
```

参数说明：
- `--single <arxiv_id>`：指定要分析的 arXiv 论文编号（如 `2305.09582`）。
- `-p <页数>` 或 `--pages <页数>`：最大 PDF 提取页数，默认为 10。可用数字（如 20），或 `all` 表示全部页。

**示例：**

只分析前 10 页：
```bash
python src/main.py --single 2305.09582
```

分析前 20 页：
```bash
python src/main.py --single 2305.09582 -p 20
```

分析全部页：
```bash
python src/main.py --single 2305.09582 -p all
```

**输出说明：**
- 结果 Markdown 文件保存在 `results/` 目录，文件名如 `arxiv_2305.09582_2025-10-12_22-56-45.md`
- 文件内容仅包含该论文的详细分析和基本信息，YAML 头部 description 字段为作者姓名







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