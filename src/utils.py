# utils.py - 工具函数模块

import datetime
import logging
from pathlib import Path

from config import RESULTS_DIR

logger = logging.getLogger(__name__)

def write_to_conclusion(priority_analyses, secondary_analyses, irrelevant_papers=None):
    """将分析结果写入带时间戳的.md文件"""
    today = datetime.datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    time_str = today.strftime('%H-%M-%S')
    
    # 创建带时间戳的文件名
    filename = f"arxiv_analysis_{date_str}_{time_str}.md"
    conclusion_file = RESULTS_DIR / filename
    
    # 确保结果目录存在
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 写入分析结果到新文件
    with open(conclusion_file, 'w', encoding='utf-8') as f:
        f.write(f"# ArXiv论文分析报告\n\n")
        f.write(f"**生成时间**: {today.strftime('%Y年%m月%d日 %H:%M:%S')}\n")
        f.write(f"**重点关注论文数量**: {len(priority_analyses)}\n")
        f.write(f"**了解领域论文数量**: {len(secondary_analyses)}\n")
        if irrelevant_papers:
            f.write(f"**不相关论文数量**: {len(irrelevant_papers)}\n")
        f.write("\n")
        f.write("---\n\n")
        
        # 写入重点关注的论文（完整分析）
        if priority_analyses:
            f.write("# 重点关注论文（完整分析）\n\n")
            for i, (paper, analysis) in enumerate(priority_analyses, 1):
                author_names = [author.name for author in paper.authors]
                
                # 处理过长的标题
                title = paper.title
                if len(title) > 80:
                    title = title[:77] + "..."
                
                f.write(f"## {i}. {title}\n\n")
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
                
                # 处理过长的标题
                title = paper.title
                if len(title) > 80:
                    title = title[:77] + "..."
                
                f.write(f"## {i}. {title}\n\n")
                
                # 提取中文标题
                if translation and "**中文标题**:" in translation:
                    # 解析翻译结果，提取中文标题
                    lines = translation.split('\n')
                    chinese_title = ""
                    for line in lines:
                        if line.startswith("**中文标题**:"):
                            chinese_title = line.replace("**中文标题**:", "").strip()
                            break
                    if chinese_title:
                        f.write(f"**中文标题**: {chinese_title}\n\n")
                
                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**ArXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"### 摘要翻译\n\n{translation}\n\n")
                f.write("---\n\n")
        
        # 写入不相关论文（基本信息）
        if irrelevant_papers:
            f.write("# 不相关论文（基本信息）\n\n")
            for i, (paper, reason, title_translation) in enumerate(irrelevant_papers, 1):
                author_names = [author.name for author in paper.authors]
                
                # 处理过长的标题
                title = paper.title
                if len(title) > 80:
                    title = title[:77] + "..."
                
                f.write(f"## {i}. {title}\n\n")
                
                # 提取中文标题
                if title_translation and "**中文标题**:" in title_translation:
                    # 解析翻译结果，提取中文标题
                    lines = title_translation.split('\n')
                    chinese_title = ""
                    for line in lines:
                        if line.startswith("**中文标题**:"):
                            chinese_title = line.replace("**中文标题**:", "").strip()
                            break
                    if chinese_title:
                        f.write(f"**中文标题**: {chinese_title}\n\n")
                
                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**ArXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"**摘要**: {paper.summary}\n\n")
                f.write("---\n\n")
    
    logger.info(f"分析结果已写入 {conclusion_file.absolute()}")
    return conclusion_file

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

def download_paper(paper, output_dir):
    """将论文PDF下载到指定目录"""
    pdf_path = output_dir / f"{paper.get_short_id().replace('/', '_')}.pdf"
    
    # 如果已下载则跳过
    if pdf_path.exists():
        logger.info(f"论文已下载: {pdf_path}")
        return pdf_path
    
    try:
        logger.info(f"正在下载: {paper.title}")
        paper.download_pdf(str(pdf_path))
        logger.info(f"已下载到 {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"下载论文失败 {paper.title}: {str(e)}")
        return None
