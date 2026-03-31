# AI 思考模式 (Thinking Mode) + 用量统计 实现计划

## 背景与目标
在论文分析阶段，通过让大语言模型进行深度思考，可以显著提升分析结果的逻辑性、准确性和深度。

**核心目标**：
1. **仅在论文分析阶段生效**：翻译等较简单的阶段不开启思考，节省资源与时间
2. **按需触发**：通过 CLI 参数 `--thinking` 和 TUI 菜单开关
3. **API 级别支持**：为各提供商提供正确的 thinking 参数
4. **用量统计**：记录每次 AI 调用的 token 使用量，写入结果元数据

---

## 技术方案

### SDK 升级
已从 `openai==0.28` 升级到 `openai>=1.0`，支持 `extra_body` 参数

### 各提供商 Thinking 模式支持

| 提供商 | 支持方式 | 说明 |
|--------|---------|------|
| DeepSeek | `native` | 使用 deepseek-reasoner 模型，reasoning_content 自动返回 |
| OpenAI | `native` | 使用 o1/o1-mini/o1-preview 模型 |
| Qwen | `enable_thinking` | `extra_body={"enable_thinking": True}` |
| Kimi | `native` | 使用 kimi-k2-thinking 模型 |
| GLM | `none` | 暂不支持 |
| Doubao | `none` | 暂不支持 |
| OpenRouter | `none` | 取决于具体路由的模型 |
| SiliconFlow | `none` | 取决于具体使用的模型 |

### 实现方式
- `native`：用户自行配置推理模型（如 deepseek-reasoner），代码只做日志记录
- `enable_thinking`：代码自动添加 `extra_body={"enable_thinking": True}` 参数

---

## 实施阶段 ✅ 已完成

### 第一阶段：AIClient 返回用量统计 ✅
**目标文件**：`src/config.py`
1. 添加 `chat_completion_with_usage()` 方法返回 `(content, usage)`
2. 保持 `chat_completion()` 向后兼容
3. 实现提供商配置表 `PROVIDER_CONFIG`
4. 实现 thinking 模式的 API 级别参数支持

### 第二阶段：Analyzer 改造 ✅
**目标文件**：`src/analyzer.py`
1. `analyze_paper()` 接收 `thinking_mode: bool = False` 参数
2. 收集并返回用量统计

### 第三阶段：CLI 参数支持 ✅
**目标文件**：`src/main.py`
1. 添加 `--thinking` 参数
2. 将参数传递给 `analyze_paper()`
3. 在结果文件元数据中写入用量统计

### 第四阶段：TUI 适配 ✅
**目标文件**：`run_tracker.bat`
1. 菜单中添加"切换思考模式"选项
2. 记录状态变量，执行时追加 `--thinking` 参数

### 第五阶段：SDK 升级 ✅
**目标文件**：`requirements.txt`, `src/config.py`
1. 升级 `openai==0.28` 到 `openai>=1.0`
2. 重写 AIClient 使用新的客户端实例化模式
3. 所有测试通过

---

## 使用方式

### CLI
```bash
# 普通分析
python src/main.py --arxiv 2401.12345

# 启用深度思考模式（需配置推理模型，如 AI_MODEL=deepseek-reasoner）
python src/main.py --arxiv 2401.12345 --thinking
```

### 环境变量配置示例
```bash
# DeepSeek 推理模型
AI_PROVIDER=deepseek
AI_MODEL=deepseek-reasoner

# Qwen 推理模型（自动启用 enable_thinking）
AI_PROVIDER=qwen
AI_MODEL=qwq-plus
```
