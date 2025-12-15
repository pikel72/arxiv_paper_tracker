# models 模块

功能：定义简化的作者与论文数据结构 `SimpleAuthor` 与 `SimplePaper`。

主要类：

- `SimpleAuthor(name)`：简单的作者容器，字段 `name`。

- `SimplePaper(entry)`：从 `feedparser` 的 entry 初始化，包含以下重要属性：
  - `title`, `authors` (列表 `SimpleAuthor`), `published` (datetime), `categories`, `entry_id`, `summary`
  - 方法：`get_short_id()`、`download_pdf(filename)`。

示例：

```python
from models import SimplePaper
# feedparser entry -> SimplePaper
```
