# emailer 模块

功能：将分析结果组织为 Markdown/HTML，并通过 SMTP 发送邮件，支持附件。

主要函数：

- `format_email_content(priority_analyses, secondary_analyses, irrelevant_papers=None)`
  - 作用：把不同类型的分析结果格式化为 Markdown 文本，供邮件正文或存档使用。
  - 返回：字符串（Markdown）。

- `send_email(content, attachment_path=None)`
  - 作用：将 Markdown 文本转换为 HTML（简单转换规则），构造邮件并通过 SMTP 发送。
  - 返回：布尔值，表示是否成功。

注意事项：

- 需要在 `.env` 中配置 SMTP 相关变量（`SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`）。
