# main 模块

功能：程序入口，控制抓取/分析/邮件发送流程，并提供单论文分析模式。

主要函数：

- `main()`：解析命令行参数，支持 `--single` 模式或批量流程。
- `fetch_paper_by_id(arxiv_id)`：通过 arXiv API 获取单篇元数据并返回 `SimplePaper`。
- `analyze_single_paper(arxiv_id, max_pages=10)`：单论文完整分析流程（下载、提取、分析、写文件）。

示例：

```bash
python src/main.py --single 2305.09582
```
