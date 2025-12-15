# utils 模块

功能：包含文件写入、下载与清理等辅助函数，用于结果生成与文件管理。

主要函数：

- `write_to_conclusion(priority_analyses, secondary_analyses, irrelevant_papers=None, filename=None)`
  - 作用：将分析结果写入带时间戳的 Markdown 文件，返回路径。

- `write_single_analysis(paper, analysis, filename: str = None)`
  - 作用：为单论文分析生成更简洁的 Markdown 文件。

- `download_paper(paper, output_dir)`
  - 作用：将 PDF 下载到 `output_dir`，若已存在则跳过。

- `delete_pdf(pdf_path)`
  - 作用：删除本地 PDF 文件以节省空间。

示例：

```python
from utils import write_to_conclusion
file = write_to_conclusion(priority_analyses, secondary_analyses)
```
