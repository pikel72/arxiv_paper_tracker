# Thinking Mode 实现说明（归档）

这份文档保留的是 thinking mode 改造阶段的实现脉络，当前行为请以仓库根目录的 `README.md` 和代码为准。

## 当前状态

- 完整论文分析与本地 PDF 分析支持 thinking / non-thinking 两条路径
- 默认开关可由 `ANALYSIS_THINKING_MODE` 控制
- 命令行 `--thinking` 会显式开启
- 命令行 `--no-thinking` 会显式关闭
- 若 provider 或 model 不接受当前 thinking 配置，请求会自动回退到普通模式
- 结果 frontmatter 会记录 `thinking_applied`、`fallback_used`、`reasoning_content_present`

## 相关实现文件

- `src/config.py`
- `src/analyzer.py`
- `src/main.py`
- `tests/test_thinking_mode.py`

## 备注

- thinking 开启方式仍然因 provider 不同而不同
- 项目当前通过 `LiteLLM` 统一 transport，通过 `Instructor + Pydantic` 约束结构化输出
- cleanup 模型是独立的第二阶段，不和主分析模型共享必须相同的 thinking 配置
