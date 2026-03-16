# emailer.py - 发送邮件模块

import datetime
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

from analyzer import extract_analysis_title, render_analysis_body
from config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, 
    EMAIL_FROM, EMAIL_TO, EMAIL_SUBJECT_PREFIX, RESULTS_DIR
)

logger = logging.getLogger(__name__)

def _extract_translation_title(text: str) -> str:
    return extract_analysis_title(text, "").strip()

def format_email_content(priority_analyses, secondary_analyses, irrelevant_papers=None):
    """格式化邮件内容，包含三种类型的论文"""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    content = f"## arXiv论文分析报告 ({today})\n\n"
    content += f"**重点关注论文**: {len(priority_analyses)} 篇\n"
    content += f"**了解领域论文**: {len(secondary_analyses)} 篇\n"
    if irrelevant_papers:
        content += f"**不相关论文**: {len(irrelevant_papers)} 篇\n"
    content += "\n"
    
    # 重点关注论文
    if priority_analyses:
        content += "### 🔥 重点关注论文（完整分析）\n\n"
        for i, (paper, analysis) in enumerate(priority_analyses, 1):
            author_names = [author.name for author in paper.authors]
            chinese_title = extract_analysis_title(analysis, paper.title)
            analysis_body = render_analysis_body(analysis)

            content += f"#### {i}. {chinese_title if chinese_title else paper.title}\n"
            if chinese_title and chinese_title != paper.title:
                content += f"**{paper.title}**\n\n"
            
            content += f"**作者**: {', '.join(author_names)}\n"
            content += f"**类别**: {', '.join(paper.categories)}\n"
            content += f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n"
            content += f"**链接**: {paper.entry_id}\n\n"
            content += f"{analysis_body}\n\n"
            content += "---\n\n"
    
    # 了解领域论文
    if secondary_analyses:
        content += "### 📖 了解领域论文（摘要翻译）\n\n"
        for i, (paper, translation) in enumerate(secondary_analyses, 1):
            author_names = [author.name for author in paper.authors]
            chinese_title = _extract_translation_title(translation)

            content += f"#### {i}. {chinese_title if chinese_title else paper.title}\n"
            if chinese_title:
                content += f"**{paper.title}**\n\n"
            
            content += f"**作者**: {', '.join(author_names)}\n"
            content += f"**类别**: {', '.join(paper.categories)}\n"
            content += f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n"
            content += f"**链接**: {paper.entry_id}\n\n"
            content += f"{translation}\n\n"
            content += "---\n\n"
    
    # 不相关论文
    if irrelevant_papers:
        content += "### 📋 不相关论文（基本信息）\n\n"
        for i, (paper, reason, title_translation) in enumerate(irrelevant_papers, 1):
            author_names = [author.name for author in paper.authors]
            chinese_title = _extract_translation_title(title_translation)

            content += f"#### {i}. {chinese_title if chinese_title else paper.title}\n"
            if chinese_title:
                content += f"**{paper.title}**\n\n"
            
            content += f"**作者**: {', '.join(author_names)}\n"
            content += f"**类别**: {', '.join(paper.categories)}\n"
            content += f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n"
            content += f"**链接**: {paper.entry_id}\n\n"
            content += f"**摘要**: {paper.summary}\n\n"
            content += "---\n\n"
    
    return content

def send_email(content, attachment_path=None):
    """发送邮件，支持QQ邮箱，改进错误处理，优化字体样式，支持附件"""
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM]) or not EMAIL_TO:
        logger.error("邮件配置不完整，跳过发送邮件")
        return

    try:
        # 创建邮件容器，支持附件
        msg = MIMEMultipart('mixed')
        msg['From'] = EMAIL_FROM
        msg['To'] = ", ".join(EMAIL_TO)
        msg['Subject'] = f"{EMAIL_SUBJECT_PREFIX} - {datetime.datetime.now().strftime('%Y-%m-%d')}"

        # 创建邮件正文部分
        body_part = MIMEMultipart('alternative')
        
        # 转换Markdown为HTML，使用更小的字体
        html_content = content
        
        # 转换标题
        html_content = html_content.replace('## ', '<h1>')
        html_content = html_content.replace('### 🔥', '<h2><span style="font-size: 16px;">🔥</span>')
        html_content = html_content.replace('### 📖', '<h2><span style="font-size: 16px;">📖</span>')
        html_content = html_content.replace('### ', '<h2>')
        html_content = html_content.replace('#### ', '<h3>')
        
        # 处理加粗文本
        import re
        html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
        
        # 处理链接 (如果有的话)
        html_content = re.sub(r'https?://[^\s<>"]+', r'<a href="\g<0>" style="color: #3498db; text-decoration: none; word-break: break-all;">\g<0></a>', html_content)
        
        # 转换换行
        html_content = html_content.replace('\n\n', '</p><p>')
        html_content = html_content.replace('\n', '<br>')
        
        # 处理分隔线
        html_content = html_content.replace('---', '<hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;">')
        
        # 包装段落
        html_content = f'<p>{html_content}</p>'
        
        # 清理多余的段落标签
        html_content = html_content.replace('<p></p>', '')
        html_content = html_content.replace('<p><hr', '<hr')
        html_content = html_content.replace('></p>', '>')
        html_content = html_content.replace('<p><h1>', '<h1>')
        html_content = html_content.replace('</h1></p>', '</h1>')
        html_content = html_content.replace('<p><h2>', '<h2>')
        html_content = html_content.replace('</h2></p>', '</h2>')
        html_content = html_content.replace('<p><h3>', '<h3>')
        html_content = html_content.replace('</h3></p>', '</h3>')
        
        # 为翻译内容添加特殊样式
        html_content = html_content.replace('**中文标题**:', '<strong style="color: #e74c3c; font-size: 14px;">中文标题</strong>:')
        html_content = html_content.replace('**摘要翻译**:', '<strong style="color: #e74c3c; font-size: 14px;">摘要翻译</strong>:')
        
        # 创建完整的HTML文档
        final_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 15px;
            background-color: #f8f9fa;
        }}
        .container {{
            background-color: white;
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        h1 {{
            font-size: 18px;
            color: #2c3e50;
            margin: 0 0 12px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid #3498db;
        }}
        h2 {{
            font-size: 16px;
            color: #34495e;
            margin: 16px 0 8px 0;
            padding-bottom: 4px;
            border-bottom: 1px solid #eee;
        }}
        h3 {{
            font-size: 14px;
            color: #2980b9;
            margin: 12px 0 6px 0;
        }}
        p {{
            margin: 6px 0;
            font-size: 13px;
        }}
        strong {{
            color: #2c3e50;
            font-weight: 600;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        /* 翻译内容特殊样式 */
        .translation-content {{
            font-size: 14px;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>
        """
        
        # 添加文本和HTML版本到正文部分
        part1 = MIMEText(content, 'plain', 'utf-8')
        part2 = MIMEText(final_html, 'html', 'utf-8')
        body_part.attach(part1)
        body_part.attach(part2)
        
        # 将正文部分添加到主邮件
        msg.attach(body_part)
        
        # 添加附件
        if attachment_path and attachment_path.exists():
            try:
                from email.mime.application import MIMEApplication
                
                with open(attachment_path, 'rb') as f:
                    attach = MIMEApplication(f.read(), _subtype='octet-stream')
                    attach.add_header('Content-Disposition', 'attachment', 
                                    filename=f'{attachment_path.name}')
                    msg.attach(attach)
                    logger.info(f"已添加附件: {attachment_path.name}")
            except Exception as e:
                logger.warning(f"添加附件失败: {str(e)}")

        # 连接到SMTP服务器
        logger.info(f"正在连接到 {SMTP_SERVER}:{SMTP_PORT}")
        
        # 使用适当的连接方式
        if SMTP_PORT == 465:
            # 使用SSL连接
            import ssl
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
            logger.info("使用SSL连接")
        else:
            # 使用TLS连接
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.starttls()
            logger.info("使用TLS连接")
        
        # 登录
        logger.info(f"正在登录邮箱: {SMTP_USERNAME}")
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        # 发送邮件
        logger.info(f"正在发送邮件给: {EMAIL_TO}")
        text = msg.as_string()
        server.sendmail(EMAIL_FROM, EMAIL_TO, text)
        
        # 安全关闭连接
        try:
            server.quit()
        except:
            server.close()

        attachment_info = f" (包含附件: {attachment_path.name})" if attachment_path and attachment_path.exists() else ""
        logger.info(f"邮件发送成功，收件人: {', '.join(EMAIL_TO)}{attachment_info}")
        return True
        
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        # 如果是我们已知的无害错误，但邮件可能已经发送
        error_str = str(e)
        if "b'\\x00\\x00\\x00\\x00'" in error_str or "(-1," in error_str:
            logger.warning("邮件可能已发送成功，但服务器响应异常。请检查收件箱。")
            return True
        
        # 提供更详细的错误信息
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return False
