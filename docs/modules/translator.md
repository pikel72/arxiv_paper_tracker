# translator 模块

功能：使用 AI 将论文标题或摘要翻译为中文。

主要函数：

- `translate_abstract_with_deepseek(paper, translate_title_only=False)`
  - 作用：生成翻译 prompt 并调用 `ai_client.chat_completion`。当 `translate_title_only=True` 时仅返回中文标题。
  - 返回：包含 `**中文标题**:` 和（可选）`**摘要翻译**:` 的字符串。

示例：

```python
from translator import translate_abstract_with_deepseek
translation = translate_abstract_with_deepseek(paper)
```
