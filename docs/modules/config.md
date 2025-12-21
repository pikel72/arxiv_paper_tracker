# config 模块

功能：读取环境变量并提供全局配置常量与 `AIClient` 封装。

重要变量：

- `PAPERS_DIR`, `RESULTS_DIR`：路径对象
- `CATEGORIES`, `MAX_PAPERS`, `SEARCH_DAYS`：抓取配置
- `PRIORITY_TOPICS`, `SECONDARY_TOPICS`：主题过滤列表
- `MAX_THREADS`：多线程处理时的最大线程数（默认为 5）

`AIClient` 类：

- 用途：统一对接不同 AI 提供商（deepseek、openai、glm、qwen、doubao、kimi、custom）。
- 方法：`chat_completion(messages, **kwargs)`，返回文本回答。

示例：

```python
from config import ai_client
resp = ai_client.chat_completion(messages=[{"role":"user","content":"Hello"}])
```
