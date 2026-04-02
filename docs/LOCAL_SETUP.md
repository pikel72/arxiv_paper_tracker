# 本地环境配置指南

## 环境要求

- Python `3.10+`
- 建议先创建虚拟环境

检查版本：

```bash
python --version
```

## 安装依赖

```bash
pip install -r requirements.txt
```

如果网络较慢，可使用镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 配置 `.env`

复制模板：

```bash
cp .env.example .env
```

最少需要配置：

```bash
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo
QWEN_API_KEY=sk-your-qwen-api-key
```

如需邮件发送，再补充：

```bash
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_mail@qq.com
SMTP_PASSWORD=your_authorization_code
EMAIL_FROM=your_mail@qq.com
EMAIL_TO=recipient@example.com
```

如需默认开启完整分析的 reasoning：

```bash
ANALYSIS_THINKING_MODE=on
ANALYSIS_THINKING_MODEL=
```

如需启用第二个 cleanup 模型：

```bash
ANALYSIS_CLEANUP_ENABLED=on
ANALYSIS_CLEANUP_PROVIDER=openrouter
ANALYSIS_CLEANUP_MODEL=your-editor-model
ANALYSIS_CLEANUP_THINKING_MODE=off
```

## 验证配置

```bash
python src/main.py --cache-stats
python -m pytest tests -q
```

## 常用本地命令

批量分析：

```bash
python src/main.py
python src/main.py --date 2026-04-01
python src/main.py --thinking
python src/main.py --no-thinking
```

单论文分析：

```bash
python src/main.py --arxiv 2401.12345 -p 10
```

本地 PDF 分析：

```bash
python src/main.py --pdf ./papers/example.pdf -p all
```

缓存管理：

```bash
python src/main.py --cache-stats
python src/main.py --clear-cache
python src/main.py --clear-cache analysis
```

## 备注

- Windows 可以直接运行 `run_tracker.bat`
- macOS / Linux 可以运行 `run_tracker.sh`
- 更完整的项目说明请看仓库根目录的 `README.md`
