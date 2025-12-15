# analyzer 模块

功能：从 PDF 提取文本并调用 AI 接口对论文进行深入分析或主题相关性判断。

主要函数：

- `extract_pdf_text(pdf_path, max_pages=10)`
  - 作用：使用 `pdfplumber` 提取 PDF 指定页数的文本。
  - 返回：字符串，包含每页文本和页码分隔标记。

- `check_topic_relevance(paper)`
  - 作用：调用 `ai_client.chat_completion` 判断论文是否匹配 `PRIORITY_TOPICS` 或 `SECONDARY_TOPICS`。
  - 返回：`(priority:int, reason:str)`，其中 `priority` 为 0/1/2。

- `analyze_paper(pdf_path, paper)`
  - 作用：把 PDF 内容与论文元信息组成 prompt，通过 AI 生成详细分析（中文，Markdown，支持 MathJax）。
  - 返回：AI 生成的字符串（Markdown）。

示例用法：

```python
from analyzer import extract_pdf_text, analyze_paper

text = extract_pdf_text('papers/2305.09582.pdf', max_pages=10)
# analyze_paper 依赖于全局 ai_client，通常从 `main.py` 调用，传入 SimplePaper 对象。
```
