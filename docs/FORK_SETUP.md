# Fork 用户配置指南

这份指南适合 fork 本仓库后，想做两件事的同学：

- 在本地分析单篇 arXiv 文献或本地 PDF
- 用 GitHub Actions 每天自动生成报告，并推送到自己指定的仓库

## 1. Fork 并克隆

先在 GitHub 页面点 `Fork`，然后克隆自己的 fork：

```bash
git clone https://github.com/<你的用户名>/arxiv_paper_tracker.git
cd arxiv_paper_tracker
```

建议创建虚拟环境：

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 2. 本地配置 `.env`

复制模板：

```bash
cp .env.example .env
```

Windows PowerShell 可以用：

```powershell
Copy-Item .env.example .env
```

最小配置只需要一个可用的 AI provider。例如使用 Qwen：

```bash
AI_PROVIDER=qwen
AI_MODEL=qwen-plus
QWEN_API_KEY=sk-your-qwen-api-key
```

如果要发送邮件，再补充 SMTP：

```bash
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_mail@qq.com
SMTP_PASSWORD=your_mail_authorization_code
EMAIL_FROM=your_mail@qq.com
EMAIL_TO=receiver@example.com
```

常用论文筛选配置：

```bash
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=50
SEARCH_DAYS=3
PRIORITY_TOPICS=Navier-Stokes方程|Euler方程|湍流
SECONDARY_TOPICS=色散偏微分方程|调和分析|椭圆偏微分方程
```

## 3. 本地分析单篇文献

分析 arXiv 编号：

```bash
python src/main.py --arxiv 2401.12345
```

只分析前 20 页：

```bash
python src/main.py --arxiv 2401.12345 -p 20
```

分析全部页面并开启 thinking：

```bash
python src/main.py --arxiv 2401.12345 -p all --thinking
```

分析本地 PDF：

```bash
python src/main.py --pdf ./papers/example.pdf -p all
```

结果会生成在 `results/` 目录中。

## 4. 配置 Actions 每日运行

进入 fork 后的仓库页面：

`Settings -> Secrets and variables -> Actions`

### Secrets

至少配置你实际使用的 AI Key。例如使用 Qwen：

```text
QWEN_API_KEY=sk-your-qwen-api-key
```

如果需要邮件：

```text
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_mail@qq.com
SMTP_PASSWORD=your_mail_authorization_code
EMAIL_FROM=your_mail@qq.com
EMAIL_TO=receiver@example.com
```

如果要把报告推送到另一个仓库，还需要一个 token：

```text
REPORT_PUSH_TOKEN=ghp_xxx
```

这个 token 需要有目标仓库的写权限。目标仓库如果也是你的私有或公开仓库，通常创建 fine-grained token，并给该目标仓库 `Contents: Read and write` 权限即可。

### Variables

最小 AI 配置：

```text
AI_PROVIDER=qwen
AI_MODEL=qwen-plus
```

论文范围：

```text
ARXIV_CATEGORIES=math.AP
MAX_PAPERS=50
SEARCH_DAYS=3
PRIORITY_TOPICS=Navier-Stokes方程|Euler方程|湍流
SECONDARY_TOPICS=色散偏微分方程|调和分析|椭圆偏微分方程
```

报告推送目标：

```text
REPORT_TARGET_REPOSITORY=<你的用户名>/<目标仓库名>
REPORT_TARGET_PATH=content/report
```

例如你想推送到 `alice/pages_src` 的 `content/report/` 目录：

```text
REPORT_TARGET_REPOSITORY=alice/pages_src
REPORT_TARGET_PATH=content/report
```

如果不配置 `REPORT_TARGET_REPOSITORY`，Actions 仍会生成报告并上传到 Artifacts，但 fork 仓库不会自动推送到外部仓库。

## 5. 手动测试 Actions

进入 GitHub 仓库：

`Actions -> Daily Paper Analysis -> Run workflow`

运行完成后检查三处：

- `Summary` 页面是否成功
- `Artifacts` 里是否有 `arxiv-analysis-results-*`
- 目标仓库的 `REPORT_TARGET_PATH` 目录下是否出现新的 `.md` 报告

## 6. 常见问题

如果 AI 调用失败，先检查：

```bash
AI_PROVIDER
AI_MODEL
对应 provider 的 API Key
```

如果报告没有推送到目标仓库，先检查：

```bash
REPORT_TARGET_REPOSITORY
REPORT_TARGET_PATH
REPORT_PUSH_TOKEN
```

如果周末没有报告，这是正常情况：当前爬取逻辑会在周六、周日跳过。
