# AI 思考模式 (Thinking Mode) + 用量统计 实现计划

## 背景与目标
在论文分析阶段，通过让大语言模型进行深度思考，可以显著提升分析结果的逻辑性、准确性和深度。

**核心目标**：
1. **仅在论文分析阶段生效**：翻译等较简单的阶段不开启思考，节省资源与时间
2. **按需触发**：通过 CLI 参数 `--thinking` 和 TUI 菜单开关
3. **零后处理**：利用 `openai==0.28` 自动忽略 `reasoning_content` 的特性，无需清理思考内容
4. **用量统计**：记录每次 AI 调用的 token 使用量，写入结果元数据

---

## 技术方案

### 关键洞察
- **推理模型**（DeepSeek-R1、QwQ 等）：思考过程在 `reasoning_content` 字段，最终结果在 `content` 字段
- **openai==0.28**：自动忽略 `reasoning_content`，只返回 `content`
- **结论**：不需要 `<think>` 标签，不需要清理函数，只需修改 Prompt 引导深度思考

### Prompt 策略
```python
THINKING_MODE_PROMPT_PREFIX = """
请在输出前进行深度的逐步推理和批判性思考，但不要在回复中展示思考过程。
直接输出经过深度思考后的最终分析结果。
"""
```

---

## 实施阶段

### 第一阶段：AIClient 返回用量统计
**目标文件**：`src/config.py`
1. 添加 `chat_completion_with_usage()` 方法返回 `(content, usage)`
2. 保持 `chat_completion()` 向后兼容

### 第二阶段：Analyzer 改造
**目标文件**：`src/analyzer.py`
1. `analyze_paper()` 接收 `thinking_mode: bool = False` 参数
2. 当 `thinking_mode=True` 时，在 Prompt 开头添加深度思考引导
3. 收集并返回用量统计

### 第三阶段：CLI 参数支持
**目标文件**：`src/main.py`
1. 添加 `--thinking` 参数
2. 将参数传递给 `analyze_paper()`
3. 在结果文件元数据中写入用量统计

### 第四阶段：TUI 适配
**目标文件**：`run_tracker.bat`
1. 菜单中添加"切换思考模式"选项
2. 记录状态变量，执行时追加 `--thinking` 参数

### 第五阶段：测试验证

---

## 已删除的阶段（不需要）
- ~~输出清理与健壮性改造~~：`openai==0.28` 自动忽略 `reasoning_content`，无需清理
- ~~`<think>` 标签处理~~：不使用标签方案
- ~~`strip_thinking_content()` 函数~~：不需要
