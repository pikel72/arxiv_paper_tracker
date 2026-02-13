# AGENTS.md

## 项目概览

**目的**：自动化追踪、分析和报告 ArXiv 论文，使用 AI 进行智能筛选和分析

**技术栈**：
- Python 3.10+
- `arxiv==2.2.0` - ArXiv API 客户端
- `openai==0.28` - AI API 封装（注意是 v0.28）
- `pdfplumber==0.11.0` - PDF 文本提取
- `requests`, `python-dotenv`, `jinja2`, `pytz`

## 代码库地图

```
arxiv_paper_tracker/
├── src/                          # 主代码
│   ├── main.py                   # 入口点，CLI 参数解析
│   ├── config.py                 # 配置 + AIClient (AI 统一接口)
│   ├── models.py                 # SimplePaper, SimpleAuthor
│   ├── crawler.py                # ArXiv API 爬取
│   ├── analyzer.py               # PDF 提取 + AI 分析
│   ├── translator.py             # AI 翻译
│   ├── emailer.py                # SMTP 邮件发送
│   ├── utils.py                  # 文件读写
│   └── cache.py                  # 基于文件的缓存系统
├── tests/                        # 测试
├── .github/workflows/
│   └── daily_paper_analysis.yml  # GitHub Actions 定时任务
├── requirements.txt              # 依赖
├── .env.example                  # 环境变量模板
└── run_tracker.bat               # Windows 交互脚本
```

**核心流程**：
```
main.py → crawler.py (获取论文) → analyzer.py (AI 主题判断)
    ↓
优先级1: analyze_paper() → utils.py (写文件) → emailer.py (发邮件)
优先级2: translator.py (翻译) → utils.py → emailer.py
不相关: 记录标题 → utils.py → emailer.py
```

## 关键模块快速参考

| 模块 | 主要类/函数 | 作用 | 导入位置 |
|------|------------|------|----------|
| **config.py** | `AIClient` | 统一 8 种 AI 提供商接口，内置重试 | 所有模块 |
| **crawler.py** | `get_recent_papers()` | 获取 ArXiv 论文列表，支持日期范围 | main.py |
| **analyzer.py** | `analyze_paper()`, `check_topic_relevance()` | PDF 提取 + AI 分析 + 主题判断 | main.py |
| **translator.py** | `translate_abstract_with_deepseek()` | 翻译摘要/标题 | main.py |
| **emailer.py** | `send_email()`, `format_email_content()` | SMTP 邮件发送 | main.py |
| **utils.py** | `write_to_conclusion()`, `download_paper()` | 文件操作 | main.py, analyzer.py |
| **cache.py** | `get_cache()`, `set_cache()` | 文件缓存 (papers/classification/analysis/translation) | analyzer.py, translator.py |
| **models.py** | `SimplePaper` | 论文数据结构 | crawler.py |

## 环境配置

**必需环境变量** (.env)：
```
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
GLM_API_KEY=xxx
QWEN_API_KEY=sk-xxx

SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=xxx@qq.com
SMTP_PASSWORD=授权码
EMAIL_FROM=xxx@qq.com
EMAIL_TO=recipient@xxx.com
```

**可选配置**：
```
AI_PROVIDER=deepseek  # 支持: deepseek, openai, glm, qwen, doubao, kimi, openrouter, siliconflow, custom
AI_MODEL=deepseek-chat
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=50
SEARCH_DAYS=3
PRIORITY_TOPICS=Navier-Stokes方程|Euler方程
SECONDARY_TOPICS=色散偏微分方程|调和分析
MAX_THREADS=5
```

## 运行与调试

**主程序运行**：
```bash
# 批量模式（自动日期）
python src/main.py

# 指定日期范围
python src/main.py --date 2025-01-01:2025-01-07

# 单论文分析
python src/main.py --arxiv 2401.12345

# 单论文分析（指定页数）
python src/main.py --arxiv 2401.12345 -p 20
python src/main.py --arxiv 2401.12345 -p all

# 本地 PDF 分析
python src/main.py --pdf ./papers/paper.pdf
```

**缓存管理**：
```bash
# 查看缓存统计
python src/main.py --cache-stats

# 清除所有缓存
python src/main.py --clear-cache

# 清除特定类型缓存
python src/main.py --clear-cache classification
python src/main.py --clear-cache analysis
```

**测试**：
```bash
# 运行所有测试
python tests/test_*.py

# 单独运行某个测试
python tests/test_ai_providers.py
```

**Windows 快捷脚本**：
```bash
run_tracker.bat  # 交互式菜单
```

## 代码风格与约定

1. **日志**：所有模块使用 `logger = logging.getLogger(__name__)`
2. **类型注解**：函数参数和返回值标注类型（可选）
3. **错误处理**：网络请求使用 try-except + 重试机制
4. **缓存优先**：analyzer 和 translator 在调用 AI 前先检查缓存
5. **多线程**：main.py 使用 `ThreadPoolExecutor(max_workers=MAX_THREADS)`

**重要**：项目要求 **不要添加代码注释**，保持代码简洁。

## Commit Message 格式

`[图标 类别] 简短描述`

* **[✨ 新增]** : 新增笔记、新项目、新模板。
* **[🛠️ 修复]** : 修正错别字、修正 LaTeX 错误、修复断链。
* **[📝 优化]** : 润色表达、整理排版、补充内容（不改变结构）。
* **[📂 整理]** : 重构目录结构、重命名文件、移动位置。
* **[⚙️ 系统]** : 修改 `.gitignore`、配置插件、工具/设置维护。

**示例** :
* `[✨ 新增] 添加 AI 分析结果的邮件模板`
* `[🛠️ 修复] 修正 analyzer.py 的 PDF 提取错误`
* `[📂 整理] 将论文缓存移动到 .cache/papers`
* `[⚙️ 系统] 更新 daily_paper_analysis 工作流超时设置`

## 常见任务

**添加新的 AI 提供商**：
1. 修改 `config.py` 的 `AIClient.__init__()` 添加 provider 分支
2. 在 `.env.example` 添加对应 API 密钥

**修改主题过滤**：
- 编辑环境变量 `PRIORITY_TOPICS` 和 `SECONDARY_TOPICS`

**调整日期逻辑**：
- 修改 `crawler.py` 的 `get_recent_papers()` 中的星期计算

**调试 AI 调用**：
- 检查 `config.py` 的 `AIClient.chat_completion()` 重试逻辑
- 清除缓存：`python src/main.py --clear-cache`

## 数据模型

**SimplePaper** (models.py):
```python
class SimplePaper:
    title: str
    authors: List[SimpleAuthor]
    published: datetime  # UTC
    categories: List[str]
    entry_id: str        # arXiv URL
    summary: str
    get_short_id() -> str
    download_pdf(filename) -> None
```

**SimpleAuthor** (models.py):
```python
class SimpleAuthor:
    name: str
```

## GitHub Actions

- 定时任务：`.github/workflows/daily_paper_analysis.yml`
- 运行时间：每天 10:40（北京时间）
- 超时：40 分钟
- 手动触发：Settings → Actions → "Run workflow"
- 结果上传：GitHub Artifacts（保留 30 天）

## 注意事项

1. **openai 版本**：使用 `openai==0.28`，不是 v1.x
2. **PDF 清理**：main.py 在所有分析完成后统一清理 PDF 文件
3. **周末跳过**：crawler.py 在周六、周日自动返回空列表
4. **缓存目录**：`.cache/` 已在 `.gitignore` 中
5. **测试覆盖**：关键路径有测试，修改后务必运行对应测试

## AI 提供商支持

当前支持的 AI 提供商（通过 `AI_PROVIDER` 环境变量配置）：
- `deepseek` - DeepSeek API
- `openai` - OpenAI API
- `glm` - 智谱AI (BigModel)
- `qwen` - 通义千问 (Alibaba DashScope)
- `doubao` - 豆包 (Volcengine)
- `kimi` - Kimi (Moonshot)
- `openrouter` - OpenRouter
- `siliconflow` - SiliconFlow
- `custom` - 自定义 API base 和 key

## 缓存系统

缓存目录：`.cache/`
缓存类型：
- `papers` - 论文列表（24 小时）
- `classification` - 主题分类结果（72 小时）
- `analysis` - 论文分析结果（7 天）
- `translation` - 翻译结果（7 天）

缓存键使用 MD5 哈希，避免文件名过长或包含特殊字符。

## 主题过滤逻辑

论文分类：
- **优先级 1**（重点关注）：完整 PDF 分析 + 详细报告
- **优先级 2**（了解领域）：仅翻译摘要和标题
- **不相关**：仅记录中文标题

分类通过 AI 判断，基于 `PRIORITY_TOPICS` 和 `SECONDARY_TOPICS` 配置。
