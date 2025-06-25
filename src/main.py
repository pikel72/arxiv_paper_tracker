#!/usr/bin/env python3
# ArXiv论文追踪与分析器

import os
import arxiv

import datetime
from pathlib import Path
import openai
import time
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from jinja2 import Template

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                   handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
# 支持多个收件人邮箱，用逗号分隔
EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]

PAPERS_DIR = Path("./papers")
RESULTS_DIR = Path("./results")

# 从环境变量读取配置，如果没有则使用默认值
CATEGORIES = [cat.strip() for cat in os.getenv("ARXIV_CATEGORIES", "math.AP").split(",") if cat.strip()]
MAX_PAPERS = int(os.getenv("MAX_PAPERS", "50"))
SEARCH_DAYS = int(os.getenv("SEARCH_DAYS", "5"))

# 主题过滤列表从环境变量读取
default_priority_topics = [
    "流体力学中偏微分方程的数学理论",
    "Navier-Stokes方程",
    "Euler方程", 
    "Prandtl方程",
    "湍流",
    "涡度"
]

default_secondary_topics = [
    "色散偏微分方程的数学理论",
    "双曲偏微分方程的数学理论", 
    "调和分析",
    "极大算子",
    "椭圆偏微分方程",
    "抛物偏微分方程"
]

# 从环境变量读取主题列表，使用 | 分隔
PRIORITY_TOPICS = os.getenv("PRIORITY_TOPICS", "|".join(default_priority_topics)).split("|")
SECONDARY_TOPICS = os.getenv("SECONDARY_TOPICS", "|".join(default_secondary_topics)).split("|")

# API调用延时配置
PRIORITY_ANALYSIS_DELAY = int(os.getenv("PRIORITY_ANALYSIS_DELAY", "3"))  # 重点论文分析延时（秒）
SECONDARY_ANALYSIS_DELAY = int(os.getenv("SECONDARY_ANALYSIS_DELAY", "2"))  # 摘要翻译延时（秒）

# 邮件配置
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "ArXiv论文分析报告")


def check_topic_relevance(paper):
    """使用AI判断论文是否符合指定主题，并返回优先级"""
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]
        
        # 获取论文摘要
        abstract = paper.summary if hasattr(paper, 'summary') else "无摘要"
        
        prompt = f"""
        论文标题: {paper.title}
        作者: {', '.join(author_names)}
        摘要: {abstract}
        类别: {', '.join(paper.categories)}
        
        我关注以下研究主题：
        
        重点关注领域（优先级1）：
        {chr(10).join([f"- {topic}" for topic in PRIORITY_TOPICS])}
        
        了解领域（优先级2）：
        {chr(10).join([f"- {topic}" for topic in SECONDARY_TOPICS])}
        
        请判断这篇论文是否与上述主题相关，并指定优先级。
        
        请只回答以下格式之一：
        优先级1 - 简述原因（不超过20字）
        优先级2 - 简述原因（不超过20字）
        不相关
        
        格式示例：
        优先级1 - 研究了Navier-Stokes方程的存在性
        优先级2 - 涉及椭圆方程的正则性理论
        不相关
        """
        
        logger.info(f"正在检查主题相关性: {paper.title}")
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位专业的学术论文分类专家。请严格按照要求的格式回答。"},
                {"role": "user", "content": prompt},
            ]
        )
        
        result = response.choices[0].message.content.strip()
        logger.info(f"主题相关性检查结果: {result}")
        
        # 判断优先级
        if result.startswith("优先级1"):
            reason = result.replace("优先级1", "").strip(" -")
            logger.info(f"论文符合重点关注主题: {paper.title} - {reason}")
            return 1, reason
        elif result.startswith("优先级2"):
            reason = result.replace("优先级2", "").strip(" -")
            logger.info(f"论文符合了解主题: {paper.title} - {reason}")
            return 2, reason
        else:
            logger.info(f"论文不符合主题要求，跳过: {paper.title}")
            return 0, "不符合主题要求"
            
    except Exception as e:
        logger.error(f"检查主题相关性失败 {paper.title}: {str(e)}")
        # 出错时默认为优先级2，避免遗漏
        return 2, f"检查出错，默认处理: {str(e)}"

def translate_abstract_with_deepseek(paper):
    """使用DeepSeek API翻译论文摘要"""
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]
        
        prompt = f"""
        请将以下英文摘要翻译成中文，保持学术性和准确性：
        
        论文标题: {paper.title}
        摘要: {paper.summary}
        
        请提供：
        1. 标题的中文翻译
        2. 摘要的中文翻译（保持原文的学术表达风格）
        
        格式：
        **中文标题**: [翻译后的标题]
        
        **摘要翻译**: [翻译后的摘要]
        """
        
        logger.info(f"正在翻译摘要: {paper.title}")
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位专业的学术翻译专家，擅长数学和物理领域的翻译。"},
                {"role": "user", "content": prompt},
            ]
        )
        
        translation = response.choices[0].message.content
        logger.info(f"摘要翻译完成: {paper.title}")
        return translation
    except Exception as e:
        logger.error(f"翻译摘要失败 {paper.title}: {str(e)}")
        return f"**翻译出错**: {str(e)}"

# 配置OpenAI API用于DeepSeek
openai.api_key = DEEPSEEK_API_KEY
openai.api_base = "https://api.deepseek.com/v1"

# 如果不存在论文目录则创建
PAPERS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)  # 创建结果目录
logger.info(f"论文将保存在: {PAPERS_DIR.absolute()}")
logger.info(f"分析结果将写入: {RESULTS_DIR.absolute()}")

def get_recent_papers(categories, max_results=MAX_PAPERS):
    """获取最近几天内发布的指定类别的论文"""
    # 使用环境变量配置的天数
    today = datetime.datetime.now()
    days_ago = today - datetime.timedelta(days=SEARCH_DAYS)
    
    # 格式化ArXiv查询的日期
    start_date = days_ago.strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    
    # 创建查询字符串
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    date_range = f"submittedDate:[{start_date}000000 TO {end_date}235959]"
    query = f"({category_query}) AND {date_range}"
    
    logger.info(f"正在搜索论文，查询条件: {query}")
    logger.info(f"搜索范围: 最近{SEARCH_DAYS}天，类别: {', '.join(categories)}，最大数量: {max_results}")
    
    # 搜索ArXiv
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    results = list(search.results())
    logger.info(f"找到{len(results)}篇符合条件的论文")
    return results

def download_paper(paper, output_dir):
    """将论文PDF下载到指定目录"""
    pdf_path = output_dir / f"{paper.get_short_id().replace('/', '_')}.pdf"
    
    # 如果已下载则跳过
    if pdf_path.exists():
        logger.info(f"论文已下载: {pdf_path}")
        return pdf_path
    
    try:
        logger.info(f"正在下载: {paper.title}")
        paper.download_pdf(filename=str(pdf_path))
        logger.info(f"已下载到 {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"下载论文失败 {paper.title}: {str(e)}")
        return None

def analyze_paper_with_deepseek(pdf_path, paper):
    """使用DeepSeek API分析论文（使用OpenAI 0.28.0兼容格式）"""
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]
        
        prompt = f"""
        论文标题: {paper.title}
        作者: {', '.join(author_names)}
        类别: {', '.join(paper.categories)}
        发布时间: {paper.published}
        
        请分析这篇研究论文并提供：
        1. 研究对象和背景: 给出论文描述的方程或系统, 如果在Introduction的部分给出了方程组的数学公式, 请一并给出 (用行间公式表示); 如果文章研究的是某一种现象的验证, 请描述现象.
        2. 主要定理或主要结果: 给出文章证明的主要定理.
        3. 研究方法, 具体采用的技术, 工具
        4. 与之前工作的比较: 文章是否声称做出了什么突破或改进? 如果有，请描述.
        
        请使用中文回答，并以Markdown格式 (包含数学公式), 分自然段格式输出。
        """
        
        logger.info(f"正在分析论文: {paper.title}")
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        
        analysis = response.choices[0].message.content
        logger.info(f"论文分析完成: {paper.title}")
        return analysis
    except Exception as e:
        logger.error(f"分析论文失败 {paper.title}: {str(e)}")
        return f"**论文分析出错**: {str(e)}"

def write_to_conclusion(priority_analyses, secondary_analyses):
    """将分析结果写入带时间戳的.md文件"""
    today = datetime.datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    time_str = today.strftime('%H-%M-%S')
    
    # 创建带时间戳的文件名
    filename = f"arxiv_analysis_{date_str}_{time_str}.md"
    conclusion_file = RESULTS_DIR / filename
    
    # 写入分析结果到新文件
    with open(conclusion_file, 'w', encoding='utf-8') as f:
        f.write(f"# ArXiv论文分析报告\n\n")
        f.write(f"**生成时间**: {today.strftime('%Y年%m月%d日 %H:%M:%S')}\n")
        f.write(f"**搜索类别**: {', '.join(CATEGORIES)}\n")
        f.write(f"**重点关注论文数量**: {len(priority_analyses)}\n")
        f.write(f"**了解领域论文数量**: {len(secondary_analyses)}\n\n")
        f.write("---\n\n")
        
        # 写入重点关注的论文（完整分析）
        if priority_analyses:
            f.write("# 重点关注论文（完整分析）\n\n")
            for i, (paper, analysis) in enumerate(priority_analyses, 1):
                author_names = [author.name for author in paper.authors]
                
                f.write(f"## {i}. {paper.title}\n\n")
                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**ArXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"### 详细分析\n\n{analysis}\n\n")
                f.write("---\n\n")
        
        # 写入了解领域的论文（摘要翻译）
        if secondary_analyses:
            f.write("# 了解领域论文（摘要翻译）\n\n")
            for i, (paper, translation) in enumerate(secondary_analyses, 1):
                author_names = [author.name for author in paper.authors]
                
                f.write(f"## {i}. {paper.title}\n\n")
                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**ArXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"### 摘要翻译\n\n{translation}\n\n")
                f.write("---\n\n")
    
    logger.info(f"分析结果已写入 {conclusion_file.absolute()}")
    return conclusion_file

def format_email_content(priority_analyses, secondary_analyses):
    """格式化邮件内容，包含两种类型的论文"""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    content = f"## 今日ArXiv论文分析报告 ({today})\n\n"
    content += f"**重点关注论文**: {len(priority_analyses)} 篇\n"
    content += f"**了解领域论文**: {len(secondary_analyses)} 篇\n\n"
    
    # 重点关注论文
    if priority_analyses:
        content += "### 🔥 重点关注论文（完整分析）\n\n"
        for i, (paper, analysis) in enumerate(priority_analyses, 1):
            author_names = [author.name for author in paper.authors]
            
            content += f"#### {i}. {paper.title}\n"
            content += f"**作者**: {', '.join(author_names)}\n"
            content += f"**类别**: {', '.join(paper.categories)}\n"
            content += f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n"
            content += f"**链接**: {paper.entry_id}\n\n"
            content += f"{analysis}\n\n"
            content += "---\n\n"
    
    # 了解领域论文
    if secondary_analyses:
        content += "### 📖 了解领域论文（摘要翻译）\n\n"
        for i, (paper, translation) in enumerate(secondary_analyses, 1):
            author_names = [author.name for author in paper.authors]
            
            content += f"#### {i}. {paper.title}\n"
            content += f"**作者**: {', '.join(author_names)}\n"
            content += f"**类别**: {', '.join(paper.categories)}\n"
            content += f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n"
            content += f"**链接**: {paper.entry_id}\n\n"
            content += f"{translation}\n\n"
            content += "---\n\n"
    
    return content

def delete_pdf(pdf_path):
    """删除PDF文件"""
    try:
        if pdf_path.exists():
            pdf_path.unlink()
            logger.info(f"已删除PDF文件: {pdf_path}")
        else:
            logger.info(f"PDF文件不存在，无需删除: {pdf_path}")
    except Exception as e:
        logger.error(f"删除PDF文件失败 {pdf_path}: {str(e)}")

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

def main():
    logger.info("开始arXiv论文跟踪")
    logger.info(f"配置信息:")
    logger.info(f"- 搜索类别: {', '.join(CATEGORIES)}")
    logger.info(f"- 最大论文数: {MAX_PAPERS}")
    logger.info(f"- 搜索天数: {SEARCH_DAYS}")
    logger.info(f"- 重点主题数量: {len(PRIORITY_TOPICS)}")
    logger.info(f"- 了解主题数量: {len(SECONDARY_TOPICS)}")
    
    # 获取最近几天的论文
    papers = get_recent_papers(CATEGORIES, MAX_PAPERS)
    logger.info(f"从最近几天找到{len(papers)}篇论文")
    
    if not papers:
        logger.info("所选时间段没有找到论文。退出。")
        return
    
    # 处理每篇论文
    priority_analyses = []  # 重点关注论文的完整分析
    secondary_analyses = [] # 了解领域论文的摘要翻译
    
    priority_count = 0
    secondary_count = 0
    skipped_count = 0
    
    for i, paper in enumerate(papers, 1):
        logger.info(f"正在处理论文 {i}/{len(papers)}: {paper.title}")
        
        # 检查主题相关性和优先级
        priority, reason = check_topic_relevance(paper)
        
        if priority == 1:
            # 重点关注论文：下载PDF并进行完整分析
            priority_count += 1
            logger.info(f"重点关注论文 {priority_count}: {paper.title} ({reason})")
            
            pdf_path = download_paper(paper, PAPERS_DIR)
            if pdf_path:
                time.sleep(PRIORITY_ANALYSIS_DELAY)  # 使用环境变量配置的延时
                analysis = analyze_paper_with_deepseek(pdf_path, paper)
                priority_analyses.append((paper, analysis))
                delete_pdf(pdf_path)
                
        elif priority == 2:
            # 了解领域论文：只翻译摘要
            secondary_count += 1
            logger.info(f"了解领域论文 {secondary_count}: {paper.title} ({reason})")
            
            time.sleep(SECONDARY_ANALYSIS_DELAY)  # 使用环境变量配置的延时
            translation = translate_abstract_with_deepseek(paper)
            secondary_analyses.append((paper, translation))
            
        else:
            # 不相关论文：跳过
            skipped_count += 1
            logger.info(f"跳过不相关论文: {paper.title}")
    
    logger.info(f"处理完成 - 重点关注: {priority_count}篇, 了解领域: {secondary_count}篇, 跳过: {skipped_count}篇")
    
    if not priority_analyses and not secondary_analyses:
        logger.info("没有找到相关论文，不发送邮件。")
        return
    
    # 将分析结果写入带时间戳的.md文件
    result_file = write_to_conclusion(priority_analyses, secondary_analyses)
    
    # 发送邮件，包含附件
    email_content = format_email_content(priority_analyses, secondary_analyses)
    email_success = send_email(email_content, attachment_path=result_file)
    
    if email_success:
        logger.info("邮件发送完成")
    else:
        logger.warning("邮件发送可能失败，请手动检查")
    
    logger.info("ArXiv论文追踪和分析完成")
    logger.info(f"结果已保存至 {result_file.absolute()}")

if __name__ == "__main__":
    main()
