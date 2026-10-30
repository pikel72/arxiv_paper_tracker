# Hermes 日报重试

任务 `023a6e28ecf3` 使用北京时间 `0 0,6,12,18 * * *`。
当天 12:00、18:00 和次日 00:00、06:00 均处理同一报告日期。
入口为 `src/daily_retry.py`；手动指定历史日期使用 `--date YYYY-MM-DD`。

安装 `scripts/hermes_arxiv_daily.sh` 到服务器
`~/.hermes/scripts/arxiv_daily_backup.sh`，继续使用原任务和 `deliver=origin`。

- `~/.local/state/arxiv-paper-tracker/days/YYYY-MM-DD.json` 保存完成状态。
  `complete` 日期仅检查此文件即退出，不访问任何外部服务，不发消息。
- HTTP 429 当次立即静默退出，返回 0，状态为 `pending`，尊重 `Retry-After`。
  四个时段均限流也不会发失败通知；详情保存在 `attempt-YYYY-MM-DD.log`。
- 其他错误保留待完成状态并按原 Hermes 配置报告；部分报告不能标为完成。
- 复用成功的论文列表、模型缓存和 `pending/` 中的完整报告。
  发布失败后下一时段复用报告，不重新调用 AI。
- 成功提交报告后保存完成标记并输出一次反馈。周末或官方停刊的正常反馈也只输出一次。
- 已运行的旧任务不受升级打断；其成功投递记录会被新入口接纳为完成状态。

完成标记先于 stdout 写入，以避免后续重复执行。若 Hermes 投递失败，报告仍然
算已完成，不会自动重新分析或重复推送；摘要保存在状态文件中便于人工查看。
