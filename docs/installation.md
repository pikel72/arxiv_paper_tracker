# 安装

1. 克隆仓库并进入项目目录：

```bash
git clone <repo-url>
cd arxiv_paper_tracker
```

2. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

3. 复制并配置环境变量：

```bash
cp .env.example .env
# 编辑 .env 填入 API key / 邮箱等
```

4. 目录说明：
- `papers/`：下载的 PDF 存放目录
- `results/`：分析输出的 Markdown 文件
- `src/`：源代码

如需在本地忽略某些运行产物，请使用 `.git/info/exclude` 或在 `.gitignore` 中按需添加条目。
