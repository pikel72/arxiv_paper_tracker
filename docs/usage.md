# 使用示例

## 手动分析单篇论文

```bash
python src/main.py --single 2305.09582
```

可选：设置页数

```bash
python src/main.py --single 2305.09582 -p 20
```

## 本地定时或手动运行全部流程

直接运行主程序将按照配置的 `ARXIV_CATEGORIES` / 环境变量去抓取并分析论文：

```bash
python src/main.py
```

运行后会在 `results/` 目录生成带时间戳的 Markdown 文件，程序也会尝试发送邮件（需在 `.env` 中配置 SMTP info）。
