# ArXiv 论文追踪与分析器

一个用于追踪、筛选、翻译和分析 arXiv 论文的自动化工具。项目支持多家兼容 OpenAI 风格接口的模型服务商，能够区分重点论文与次重点论文，并把结果写入 Markdown、发送邮件、上传到 GitHub Actions Artifacts。

## 核心能力

- 按类别和日期范围抓取 arXiv 论文
- 用 AI 做主题分类：重点关注、了解领域、不相关
- 对重点论文提取 PDF 并生成完整中文分析
- 对次重点论文生成标题和摘要翻译
- 完整分析优先走 `LiteLLM + Instructor + Pydantic` 的结构化输出
- 可选启用 reasoning/thinking 模式，并在不支持时自动回退
- 可选启用第二个 cleanup 模型，对分析 blocks 做文本清洗
- 结果自动写入 `results/`，并支持邮件发送
- 内置缓存，避免重复请求

## 运行环境

- Python `3.10+`
- GitHub Actions 工作流当前使用 Python `3.13`

安装依赖：

```bash
pip install -r requirements.txt
```

## 快速开始

1. 克隆仓库并进入目录

```bash
git clone <your-repo-url>
cd arxiv_paper_tracker
```

2. 复制环境变量模板

```bash
cp .env.example .env
```

3. 编辑 `.env`，至少填写你要使用的 AI 提供商密钥和邮件配置

4. 本地运行

```bash
python src/main.py
```

## 主要环境变量

### AI 基础配置

```bash
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo
```

支持的 provider：

- `deepseek`
- `openai`
- `glm`
- `qwen`
- `doubao`
- `kimi`
- `openrouter`
- `siliconflow`
- `nvidia_nim`
- `custom`

注意：如果模型名是 `qwen/...` 这类前缀路由格式，请显式匹配服务商。
例如：
- 使用 NVIDIA NIM 时，设置 `AI_PROVIDER=nvidia_nim`，并配置 `NVIDIA_NIM_API_KEY`（或 `NVIDIA_API_KEY`）。
- 使用 OpenRouter 时，设置 `AI_PROVIDER=openrouter`，并配置 `OPENROUTER_API_KEY`。
- 使用 DashScope 直连时，模型名通常应为 `qwen-plus` / `qwen-turbo` 这类形式，并配置 `QWEN_API_KEY`。

### 完整分析的 thinking 配置

```bash
ANALYSIS_THINKING_MODE=off
ANALYSIS_THINKING_MODEL=
ANALYSIS_THINKING_BUDGET=
ANALYSIS_THINKING_EFFORT=
```

说明：

- `ANALYSIS_THINKING_MODE=on|off` 用于设置完整分析的默认 thinking 开关
- 命令行 `--thinking` 会显式开启
- 命令行 `--no-thinking` 会显式关闭
- 若 provider/model 不支持 thinking，请求会自动回退到普通模式

### 完整分析的 cleanup 配置

```bash
ANALYSIS_CLEANUP_ENABLED=off
ANALYSIS_CLEANUP_PROVIDER=
ANALYSIS_CLEANUP_MODEL=
ANALYSIS_CLEANUP_THINKING_MODE=off
```

cleanup 只接收两类输入：

- 论文元数据
- 结构化分析的各个 block

它会以 block in, block out 的方式返回清洗后的标题与四个 section，然后再由本地代码拼回固定 Markdown。

### ArXiv 与性能配置

```bash
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=50
SEARCH_DAYS=5
MAX_THREADS=5
PRIORITY_ANALYSIS_DELAY=3
SECONDARY_ANALYSIS_DELAY=2
```

### 邮件配置

```bash
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_mail@qq.com
SMTP_PASSWORD=your_authorization_code
EMAIL_FROM=your_mail@qq.com
EMAIL_TO=recipient@example.com
EMAIL_SUBJECT_PREFIX=ArXiv论文分析报告
```

## GitHub Actions 配置

在仓库 `Settings -> Secrets and variables -> Actions` 中配置：

### Secrets

- 各 provider 的 API Key
- `NVIDIA_NIM_API_KEY`（兼容 `NVIDIA_API_KEY`）
- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- 可选：`GH_PAGES_TOKEN`

### Variables

- `AI_PROVIDER`
- `AI_MODEL`
- `NVIDIA_NIM_API_BASE`（兼容 `NVIDIA_API_BASE`）
- `ANALYSIS_THINKING_MODE`
- `ANALYSIS_THINKING_MODEL`
- `ANALYSIS_THINKING_BUDGET`
- `ANALYSIS_THINKING_EFFORT`
- `ANALYSIS_CLEANUP_ENABLED`
- `ANALYSIS_CLEANUP_PROVIDER`
- `ANALYSIS_CLEANUP_MODEL`
- `ANALYSIS_CLEANUP_THINKING_MODE`
- `ARXIV_CATEGORIES`
- `MAX_PAPERS`
- `SEARCH_DAYS`
- `MAX_THREADS`
- `PRIORITY_TOPICS`
- `SECONDARY_TOPICS`
- `PRIORITY_ANALYSIS_DELAY`
- `SECONDARY_ANALYSIS_DELAY`
- `EMAIL_SUBJECT_PREFIX`

工作流文件位于 `.github/workflows/daily_paper_analysis.yml`。

## 本地使用方式

### 批量分析

```bash
python src/main.py
python src/main.py --date 2026-04-01
python src/main.py --date 2026-04-01:2026-04-03
python src/main.py --thinking
python src/main.py --no-thinking
```

### 单论文分析

```bash
python src/main.py --arxiv 2401.12345
python src/main.py --arxiv 2401.12345 -p 20
python src/main.py --arxiv 2401.12345 -p all --thinking
```

### 本地 PDF 分析

```bash
python src/main.py --pdf ./papers/some_paper.pdf
python src/main.py --pdf ./papers/some_paper.pdf -p all --thinking
```

### 缓存管理

```bash
python src/main.py --cache-stats
python src/main.py --clear-cache
python src/main.py --clear-cache analysis
python src/main.py --clear-cache translation
```

### 交互脚本

- Windows: `run_tracker.bat`
- macOS / Linux: `run_tracker.sh`

## 输出文件

### 批量模式

- `results/arxiv_analysis_YYYY-MM-DD_HH-MM-SS.md`

### 单论文模式

- `results/arxiv_<id>_YYYY-MM-DD_HH-MM-SS.md`

### 本地 PDF 模式

- `results/pdf_<pdf_stem>_YYYY-MM-DD_HH-MM-SS.md`

单论文和本地 PDF 结果的 frontmatter 会记录这些关键信息：

- `ai_provider`
- `effective_model`
- `thinking_mode`
- `thinking_applied`
- `fallback_used`
- `reasoning_content_present`
- `structured_output_validated`
- `structured_output_fallback`
- `cleanup_requested`
- `cleanup_attempted`
- `cleanup_applied`
- `cleanup_provider`
- `cleanup_effective_model`
- `cleanup_structured_validated`
- `from_cache`
- `token_usage`

## 结构化输出与回退策略

- 重点论文分析和本地 PDF 分析优先请求 `StructuredPaperAnalysis`
- 主题分类优先请求 `StructuredTopicClassification`
- 标题/摘要翻译优先请求结构化翻译 schema
- 若结构化路径失败，会回退到兼容的文本模式
- 若 thinking 配置不被接受，会回退到普通模式
- 若 cleanup 开启，则会在结构化 blocks 上做独立清洗

## 测试

运行全量测试：

```bash
python -m pytest tests -q
```

## 常见问题

### 1. GitHub Actions 安装依赖失败

优先检查：

- `requirements.txt` 是否有新的版本冲突
- workflow 是否使用了项目当前支持的 Python 版本

### 2. 分析结果格式异常

优先检查：

- `structured_output_validated`
- `structured_output_fallback`
- `cleanup_applied`
- `cleanup_validation_error`

### 3. thinking 看起来没有生效

优先检查结果 frontmatter 中的：

- `thinking_mode`
- `thinking_applied`
- `reasoning_content_present`
- `fallback_used`

## 许可证

MIT
