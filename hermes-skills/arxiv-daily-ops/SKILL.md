---
name: arxiv-daily-ops
description: 维护服务器论文日报、手动补跑和关注作者库.
license: MIT
metadata:
  hermes:
    tags: [arxiv, daily-report, authors, cron, backfill]
---

# 服务器论文日报与作者库

## When to use

用户要求检查论文日报、补跑某天、处理发布失败，或添加/删除/修改关注作者时使用。
这是该用户服务器上已部署的 tracker 运维流程；普通论文检索可用原有 arxiv skill。

## Prerequisites

项目 `/data/Code/arxiv_paper_tracker`，Python 为
`$HOME/.local/share/arxiv-paper-tracker/venv/bin/python`，在服务器 Linux 上使用 `terminal`。
不要用系统 Python，它不具备项目依赖。所有分析命令先进入项目目录。
凭据由现有 `.env`、`~/.config/arxiv-paper-tracker/runtime.env` 和 `gh` 登录提供；不要打印密钥。

## 不变量

- 原 Hermes 任务 `023a6e28ecf3` 每天北京时间 12、18、次日 0、6 点尝试同一份报告。
  0 点和 6 点处理前一天；手动补跑明确使用 `--date YYYY-MM-DD`。
- `src/daily_retry.py` 是补跑入口。自动任务遇到 429 静默退出，等待下一时段；不要改成循环重试或故障推送。
- 日期状态为 `complete` 时不要再次联网、分析或通知，也不要通过直接运行 `daily_backup.py` 绕过完成标记。
- 完整报告提交到网页源码仓库后才算完成；退出码 0 也可能只是限流等待或已有任务运行，要检查状态。
- 保持代理关闭。不要发送邮件，不修改 GitHub 主工作流，不删除整个缓存或整个状态目录。

## 手动处理日报

先用 `terminal` 执行本地检查（不会联网）：

```python
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/tracker_ops.py status --date 2026-10-30')
```

检查 `state.status`、`pending_metadata`、`attempt_log`、`analysis_log`。
用 `read_file` 阅读相关日志；用 `terminal` 执行
`$HOME/.hermes/hermes-agent/hermes cron runs 023a6e28ecf3` 检查调度和实际投递结果。

- **complete**：报告已经完成，读取 `tracker_ops.py summary --date DATE`；不重新分析。
  若 `adopted: true` 而没有摘要，用 `read_file` 查看 `~/.hermes/cron/output/023a6e28ecf3/` 中对应报告日期的成功输出。
- **pending / 没有状态**：用户要求现在补跑时，用下面入口。长任务使用 `terminal` 的后台会话和后续状态查询，不误把启动成功说成报告完成。
- **reason=429 / retry_at 未到期**：自动任务不发消息。只有用户主动询问时才解释当前状态；不清除冷却时间、不切换代理绕开限流。
- **已有完整 pending_report、发布失败**：不重新调用模型，读 [手动恢复说明](references/manual.md) 的 API 发布部分。
- **仍有进程运行**：等待现有任务；不要杀进程、删除锁文件或并行运行第二份分析。

```python
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/daily_retry.py --date 2026-10-30', timeout=60)
```

此直接命令的 stdout 是反馈正文，**不会自动通过 Hermes cron 投递**；用户在当前聊天要求补跑时，在当前聊天反馈结果即可，不额外发送邮件或其他消息。
需要沿原渠道投递当前调度日期时，使用 `terminal` 执行
`$HOME/.hermes/hermes-agent/hermes cron run 023a6e28ecf3`；不要用这个无日期命令补跑其他历史日期。
完成标记阻止重复通知；用户要求重发时，读取保存的摘要在当前聊天回复，不删除完成标记。

## 维护关注作者库

权威库是 `~/.config/arxiv-paper-tracker/authors.json`；`authors.json` 只是仓库种子。
自动任务每次实际执行时读权威库，不需要重启 Hermes，也不要为作者变更重置今天的完成状态。
在 `terminal` 中使用下面命令格式（每次调用均带完整前缀）：

```python
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/manage_authors.py list')
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/manage_authors.py add "Author Full Name" --note "用户指定关注"')
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/manage_authors.py alias-add "Author Full Name" "Verified Published Alias"')
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/manage_authors.py disable "Author Full Name"')
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/manage_authors.py remove "Author Full Name"')
```

还支持 `enable NAME`、`rename NAME NEW_NAME`、`alias-remove NAME ALIAS`、`note NAME TEXT`、`validate` 和 `path`。
根据用户意思选择启停或删除；明确增删作者的指示已经授权相应名单变更，不必重复确认。
用户只给了全名就按全名添加，不擅自增加同名者、缩写或其他人物。别名仅添加已确认的发表姓名。
姓名和别名都会归一化检查，重复修改会报错而不写坏库；每次修改在同目录 `authors-backups/` 留有旧版本。
修改后执行 `validate` 和 `list` 核对。个人库不需要 Git 提交，也不会被下次拉取代码覆盖。

要立即检查新加入的作者，用单独作者查询，不重开已完成日报：

```python
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/tracker_ops.py authors-news --date 2026-10-30')
```

作者检索覆盖所有 arXiv 分类，按原始新提交时间检索，当前不追踪旧论文修订。
匹配完整姓名及明确别名，同名身份仍须核实；`notes` 是维护备注，不能声称它参与了自动消歧。
作者查询 429 与“没有新论文”是不同状态，按命令实际输出反馈。

## Verification

手动运行后再次检查 `tracker_ops.py status --date DATE`。
声称“已提交”需要远端提交证据；声称“网页已上线”还需部署成功和公开报告 URL HTTP 200。
作者修改以权威库路径、`validate` 输出和实际条目为证。
更多发布恢复、名单恢复和调度调整，按需读 [references/manual.md](references/manual.md)。
