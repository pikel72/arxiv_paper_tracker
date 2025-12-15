# crawler 模块

功能：与 arXiv API 交互，获取最近发布/更新的论文条目并封装为 `SimplePaper`。

主要函数：

- `get_recent_papers(categories, max_results=MAX_PAPERS)`
  - 作用：根据当前日期和星期逻辑构建时间区间，调用 arXiv API 并解析返回的 feed。
  - 返回：`List[SimplePaper]`。

实现要点：

- 使用 `feedparser` 解析 arXiv 的 XML返回结果；按 `updated` 字段判断是否落在检索区间内。

示例：

```python
from crawler import get_recent_papers
papers = get_recent_papers(['math.AP'], max_results=50)
for p in papers:
    print(p.title, p.get_short_id())
```
