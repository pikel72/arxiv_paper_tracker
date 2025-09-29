#!/usr/bin/env python3
# ArXiv论文追踪与分析器 - 主程序

import datetime
import logging
import sys
import time

from config import (
    CATEGORIES, MAX_PAPERS, PAPERS_DIR, RESULTS_DIR,
    PRIORITY_ANALYSIS_DELAY, SECONDARY_ANALYSIS_DELAY,
    PRIORITY_TOPICS, SECONDARY_TOPICS
)
from crawler import get_recent_papers
from analyzer import check_topic_relevance, analyze_paper
from translator import translate_abstract_with_deepseek
from emailer import send_email, format_email_content
from utils import write_to_conclusion, delete_pdf, download_paper

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                   handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def main():
    logger.info("开始arXiv论文跟踪")
    logger.info(f"配置信息:")
    logger.info(f"- 搜索类别: {', '.join(CATEGORIES)}")
    logger.info(f"- 最大论文数: {MAX_PAPERS}")
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
    irrelevant_papers = []  # 不相关论文的基本信息
    
    priority_count = 0
    secondary_count = 0
    irrelevant_count = 0
    
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
                analysis = analyze_paper(pdf_path, paper)
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
            # 不相关论文：记录基本信息
            irrelevant_count += 1
            logger.info(f"不相关论文 {irrelevant_count}: {paper.title}")
            
            # 为不相关论文翻译标题
            time.sleep(SECONDARY_ANALYSIS_DELAY)  # 使用环境变量配置的延时
            title_translation = translate_abstract_with_deepseek(paper, translate_title_only=True)
            irrelevant_papers.append((paper, reason, title_translation))
    
    logger.info(f"处理完成 - 重点关注: {priority_count}篇, 了解领域: {secondary_count}篇, 不相关: {irrelevant_count}篇")
    
    if not priority_analyses and not secondary_analyses and not irrelevant_papers:
        logger.info("没有找到任何论文，不发送邮件。")
        return
    
    # 将分析结果写入带时间戳的.md文件
    result_file = write_to_conclusion(priority_analyses, secondary_analyses, irrelevant_papers)
    
    # 发送邮件，包含附件
    email_content = format_email_content(priority_analyses, secondary_analyses, irrelevant_papers)
    email_success = send_email(email_content, attachment_path=result_file)
    
    if email_success:
        logger.info("邮件发送完成")
    else:
        logger.warning("邮件发送可能失败，请手动检查")
    
    logger.info("ArXiv论文追踪和分析完成")
    logger.info(f"结果已保存至 {result_file.absolute()}")

if __name__ == "__main__":
    main()
