# 手动恢复

所有命令在服务器的 `terminal` 中执行，以项目 venv Python 运行。

## Git 卡住但报告已完成

1. `tracker_ops.py status --date DATE` 给出 `pending_report`。`pending_metadata` 必须满足：
   `report_date=DATE`、`partial_run=false`、`selection_capped=false`、
   `total_papers=completed_papers>0`、`skipped_papers=0`。
2. 用户已经要求发布/补跑这份日报时，用已有文件通过官方 Contents API 提交：

```python
terminal(command='cd /data/Code/arxiv_paper_tracker && "$HOME/.local/share/arxiv-paper-tracker/venv/bin/python" src/tracker_ops.py publish --date 2026-10-30', timeout=120)
```

该命令不会调用 AI 或重新抓取论文。它拒绝与正在运行的分析并发，检查远端同日文件，
不自动覆盖不同篇数或不完整的现有同名报告；新提交后校验 blob SHA，再保存完成标记。
发生报告冲突时检查差异，根据用户实际要求处理，不用强推覆盖。
手动发布的摘要保存在状态文件，可用 `tracker_ops.py summary --date DATE` 读取并在当前聊天反馈。
作者动态可另外使用 `authors-news --date DATE` 查询；手动发布摘要不假装已包含作者动态。

用 `terminal` 执行：
`gh run list --repo pikel72/pages_src --limit 3 --json status,conclusion,headSha,url`。
使用实际返回的网页地址验证 HTTP 200 和报告日期，才声称网页已上线。

## 恢复作者名单

用 `read_file` 对比 `~/.config/arxiv-paper-tracker/authors-backups/` 中的备份和现库。
备份只恢复作者库，不恢复整份 `.config` 或 Git 工作区。
若用户明确要求恢复某版名单，先保存现库副本，用 `patch`/`write_file` 恢复该名单，
再运行 `manage_authors.py validate`。只有文件有效时才让下一次任务使用它。
架构允许 `ARXIV_AUTHORS_FILE` 指定其他库文件；默认部署不设置此变量。
`--file PATH` 管理非默认库时，查询端也必须明确使用同一个 `ARXIV_AUTHORS_FILE`。

## 调度与维护

当前唯一任务 `023a6e28ecf3`，脚本 `~/.hermes/scripts/arxiv_daily_backup.sh`，
调用 `src/daily_retry.py`。时间表为北京时间 `0 0,6,12,18 * * *`。
用户明确要求改调度才使用 `cronjob` 或 Hermes CLI 编辑原任务，不创建重复任务。
修改状态字段前区分“报告提交成功”“网页部署成功”“Hermes 通知成功”；它们是三个独立结果。
完成标记写在输出摘要之前以阻止重复执行，通知投递失败时不会自动重分析。
`adopted=true` 表示从旧 Hermes 成功输出接纳，状态文件不一定包含摘要。

`arxiv_schedule.json` 记录官方停刊和恢复后合并区间；新增条目前用 `web_search` /
`web_extract` 核对 arXiv 官方状态公告。不要凭空把网络零结果标为停刊。
