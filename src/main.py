#!/usr/bin/env python3
# ArXiv论文追踪与分析器 - 主程序

import argparse
import datetime
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from config import (
    CATEGORIES, MAX_PAPERS, PAPERS_DIR, RESULTS_DIR,
    PRIORITY_ANALYSIS_DELAY, SECONDARY_ANALYSIS_DELAY,
    PRIORITY_TOPICS, SECONDARY_TOPICS, MAX_THREADS
)
from crawler import get_recent_papers
from analyzer import check_topic_relevance, analyze_paper, extract_pdf_text
from translator import translate_abstract_with_deepseek
from emailer import send_email, format_email_content
from utils import write_to_conclusion, delete_pdf, download_paper

import requests
from models import SimplePaper

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                   handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def process_single_paper_task(paper, index, total):
    """处理单篇论文的任务函数，用于多线程"""
    try:
        # 线程启动时稍微错开，避免瞬间并发过高
        import random
        time.sleep(random.uniform(0, 2))
        
        logger.info(f"正在处理论文 {index}/{total}: {paper.title}")
        
        # 检查主题相关性和优先级
        priority, reason = check_topic_relevance(paper)
        
        if priority == 1:
            # 重点关注论文：下载PDF并进行完整分析
            logger.info(f"重点关注论文: {paper.title} ({reason})")
            
            pdf_path = download_paper(paper, PAPERS_DIR)
            if pdf_path:
                time.sleep(PRIORITY_ANALYSIS_DELAY)
                analysis = analyze_paper(pdf_path, paper)
                # 不在这里删除 PDF，返回 pdf_path 供后续统一清理
                return 1, (paper, analysis, pdf_path)
            else:
                # 如果下载失败，降级为摘要翻译
                logger.warning(f"PDF下载失败，降级处理: {paper.title}")
                time.sleep(SECONDARY_ANALYSIS_DELAY)
                translation = translate_abstract_with_deepseek(paper)
                return 2, (paper, translation)
                
        elif priority == 2:
            # 了解领域论文：只翻译摘要
            logger.info(f"了解领域论文: {paper.title} ({reason})")
            
            time.sleep(SECONDARY_ANALYSIS_DELAY)
            translation = translate_abstract_with_deepseek(paper)
            return 2, (paper, translation)
            
        else:
            # 不相关论文：记录基本信息
            logger.info(f"不相关论文: {paper.title}")
            
            # 为不相关论文翻译标题
            time.sleep(SECONDARY_ANALYSIS_DELAY)
            title_translation = translate_abstract_with_deepseek(paper, translate_title_only=True)
            return 0, (paper, reason, title_translation)
    except Exception as e:
        logger.error(f"处理论文出错 {paper.title}: {str(e)}")
        return -1, None

def main():
    parser = argparse.ArgumentParser(
        description="ArXiv 论文追踪与分析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  批量模式（自动日期）:
    python src/main.py
  
  批量模式（指定日期）:
    python src/main.py --date 2025-12-25
    python src/main.py --date 2025-12-20:2025-12-25
  
  单论文分析（arXiv ID）:
    python src/main.py --arxiv 2401.12345
    python src/main.py --arxiv 2401.12345 -p all
  
  单PDF分析（本地文件）:
    python src/main.py --pdf ./papers/some_paper.pdf
    python src/main.py --pdf ./paper.pdf -p 20
  
  缓存管理:
    python src/main.py --cache-stats
    python src/main.py --clear-cache
    python src/main.py --clear-cache analysis
        """
    )
    
    # 批量模式参数
    parser.add_argument('--date', type=str, 
                       help='指定抓取日期，格式: YYYY-MM-DD 或 YYYY-MM-DD:YYYY-MM-DD（日期范围）')
    
    # 单论文分析参数
    parser.add_argument('--arxiv', type=str, 
                       help='通过 arXiv ID 分析论文，例如 2401.12345')
    parser.add_argument('--pdf', type=str, 
                       help='直接分析本地 PDF 文件路径')
    parser.add_argument('-p', '--pages', type=str, default='10', 
                       help='最大PDF提取页数，数字或 all（全部页），默认 10')
    
    # 兼容旧参数
    parser.add_argument('--single', type=str, 
                       help='[已废弃] 请使用 --arxiv 代替')
    
    # 缓存管理
    parser.add_argument('--cache-stats', action='store_true', 
                       help='显示缓存统计信息')
    parser.add_argument('--clear-cache', type=str, nargs='?', const='all', 
                       help='清除缓存，可选类型: classification, analysis, translation, papers, all')
    
    args = parser.parse_args()

    # 缓存管理命令
    if args.cache_stats:
        from cache import get_cache_stats
        stats = get_cache_stats()
        print(f"📦 缓存统计:")
        print(f"   总文件数: {stats['total']}")
        print(f"   总大小: {stats['size_mb']} MB")
        print(f"   按类型:")
        for cache_type, count in stats.get('by_type', {}).items():
            print(f"     - {cache_type}: {count} 个")
        return
    
    if args.clear_cache:
        from cache import clear_cache
        cache_type = None if args.clear_cache == 'all' else args.clear_cache
        count = clear_cache(cache_type)
        type_str = args.clear_cache if args.clear_cache != 'all' else '所有'
        print(f"🗑️ 已清除 {count} 个{type_str}缓存文件")
        return

    # 解析 pages 参数
    if args.pages.lower() == 'all':
        max_pages = None
    else:
        try:
            max_pages = int(args.pages)
        except Exception:
            max_pages = 10

    # 单 PDF 分析模式（新增）
    if args.pdf:
        analyze_local_pdf(args.pdf, max_pages=max_pages)
        return

    # 单论文分析模式（通过 arXiv ID）
    arxiv_id = args.arxiv or args.single  # 兼容旧参数
    if arxiv_id:
        if args.single:
            logger.warning("--single 参数已废弃，请使用 --arxiv 代替")
        analyze_single_paper(arxiv_id, max_pages=max_pages)
        return

    # 批量模式
    start_time = time.time()
    logger.info("开始arXiv论文跟踪")
    logger.info(f"配置信息:")
    logger.info(f"- 搜索类别: {', '.join(CATEGORIES)}")
    logger.info(f"- 最大论文数: {MAX_PAPERS}")
    logger.info(f"- 重点主题数量: {len(PRIORITY_TOPICS)}")
    logger.info(f"- 了解主题数量: {len(SECONDARY_TOPICS)}")
    if args.date:
        logger.info(f"- 指定日期: {args.date}")
    
    # 获取论文（支持指定日期）
    papers = get_recent_papers(CATEGORIES, MAX_PAPERS, target_date=args.date)
    logger.info(f"找到 {len(papers)} 篇论文")
    
    if not papers:
        logger.info("所选时间段没有找到论文。退出。")
        return
    
    # 处理每篇论文
    priority_analyses = []  # 重点关注论文的完整分析
    secondary_analyses = [] # 了解领域论文的摘要翻译
    irrelevant_papers = []  # 不相关论文的基本信息
    
    logger.info(f"使用 {MAX_THREADS} 个线程并行处理论文...")
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # 提交所有任务
        futures = [executor.submit(process_single_paper_task, paper, i, len(papers)) 
                   for i, paper in enumerate(papers, 1)]
        
        # 等待结果
        for future in futures:
            try:
                p_type, data = future.result()
                if p_type == 1:
                    priority_analyses.append(data)
                elif p_type == 2:
                    secondary_analyses.append(data)
                elif p_type == 0:
                    irrelevant_papers.append(data)
            except Exception as e:
                logger.error(f"获取线程执行结果出错: {str(e)}")
    
    priority_count = len(priority_analyses)
    secondary_count = len(secondary_analyses)
    irrelevant_count = len(irrelevant_papers)
    
    logger.info(f"处理完成 - 重点关注: {priority_count}篇, 了解领域: {secondary_count}篇, 不相关: {irrelevant_count}篇")
    
    if not priority_analyses and not secondary_analyses and not irrelevant_papers:
        logger.info("没有找到任何论文，不发送邮件。")
        return
    
    # 提取 PDF 路径列表，用于最后清理
    pdf_paths_to_clean = [data[2] for data in priority_analyses if len(data) > 2 and data[2]]
    
    # 转换数据格式：去掉 pdf_path，保持 (paper, analysis) 格式用于后续处理
    priority_analyses_clean = [(data[0], data[1]) for data in priority_analyses]
    
    # 将分析结果写入带时间戳的.md文件
    result_file = write_to_conclusion(priority_analyses_clean, secondary_analyses, irrelevant_papers)
    
    # 发送邮件，包含附件
    email_content = format_email_content(priority_analyses_clean, secondary_analyses, irrelevant_papers)
    email_success = send_email(email_content, attachment_path=result_file)
    
    if email_success:
        logger.info("邮件发送完成")
    else:
        logger.warning("邮件发送可能失败，请手动检查")
    
    # 所有操作完成后，最后清理 PDF 文件
    if pdf_paths_to_clean:
        logger.info(f"清理 {len(pdf_paths_to_clean)} 个 PDF 文件...")
        for pdf_path in pdf_paths_to_clean:
            delete_pdf(pdf_path)
    
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"ArXiv论文追踪和分析完成，总耗时: {duration:.2f}秒")
    logger.info(f"结果已保存至 {result_file.absolute()}")


def fetch_paper_by_id(arxiv_id):
    """通过 arXiv API 获取单篇论文条目并返回 SimplePaper 对象或 None"""
    import feedparser
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    backoff = 1
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    logger.warning(f"未找到 arXiv ID: {arxiv_id}")
                    return None
                entry = feed.entries[0]
                return SimplePaper(entry)
            else:
                logger.warning(f"尝试 {attempt}: arXiv 返回状态 {resp.status_code}")
        except Exception as e:
            logger.warning(f"尝试 {attempt}: 请求 arXiv 出错: {str(e)}")

        time.sleep(backoff)
        backoff *= 2

    logger.error(f"从 arXiv 获取元数据失败（重试3次）: {arxiv_id}")
    return None


def analyze_single_paper(arxiv_id, max_pages=10):
    """通过 arXiv ID 分析论文：获取元数据、下载PDF、调用AI分析并写入结果。"""
    start_time = time.time()
    logger.info(f"开始单论文分析: {arxiv_id}")

    paper = fetch_paper_by_id(arxiv_id)
    if not paper:
        logger.error(f"未能获取到 arXiv 论文: {arxiv_id}")
        return

    # 下载 PDF
    pdf_path = download_paper(paper, PAPERS_DIR)
    if not pdf_path:
        logger.error("PDF 下载失败，终止分析")
        return

    # 调用分析函数（复用 analyzer.analyze_paper）
    analysis = analyze_paper(pdf_path, paper, max_pages=max_pages)

    # 用单论文专用输出函数生成 Markdown 文件
    safe_id = arxiv_id.replace('/', '_')
    now = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    custom_filename = f"arxiv_{safe_id}_{now}.md"
    from utils import write_single_analysis
    result_file = write_single_analysis(paper, analysis, filename=custom_filename)
    
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"单论文分析完成，总耗时: {duration:.2f}秒，结果保存至: {result_file}")

    # 可选择删除 PDF
    delete_pdf(pdf_path)


def analyze_local_pdf(pdf_path, max_pages=10):
    """直接分析本地 PDF 文件，不依赖 arXiv 元数据"""
    from pathlib import Path
    from analyzer import analyze_pdf_only
    
    start_time = time.time()
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        logger.error(f"PDF 文件不存在: {pdf_path}")
        return
    
    logger.info(f"开始分析本地 PDF: {pdf_path}")
    
    # 调用纯 PDF 分析函数
    analysis = analyze_pdf_only(str(pdf_path), max_pages=max_pages)
    
    # 生成输出文件
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_filename = f"pdf_{pdf_path.stem}_{now}.md"
    output_path = RESULTS_DIR / output_filename
    
    # 从分析结果中提取标题信息
    chinese_title = ""
    english_title = ""
    authors = ""
    
    if analysis:
        for line in analysis.split('\n'):
            if line.startswith("**中文标题**:"):
                chinese_title = line.replace("**中文标题**:", "").strip()
            elif line.startswith("**英文标题**:"):
                english_title = line.replace("**英文标题**:", "").strip()
            elif line.startswith("**作者**:"):
                authors = line.replace("**作者**:", "").strip()
    
    # 写入 Markdown 文件
    datetime_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    from config import AI_MODEL
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"---\n")
        f.write(f"title: \"{chinese_title if chinese_title else pdf_path.stem}\"\n")
        f.write(f"date: {datetime_str}\n")
        f.write(f"source: local_pdf\n")
        if authors:
            f.write(f"description: {authors}\n")
        f.write(f"pdf_file: {pdf_path.name}\n")
        f.write(f"ai_model: {AI_MODEL}\n")
        f.write(f"---\n\n")
        
        if chinese_title:
            f.write(f"# {chinese_title}\n\n")
        if english_title:
            f.write(f"**{english_title}**\n\n")
        if authors:
            f.write(f"**作者**: {authors}\n\n")
        
        f.write(f"---\n\n")
        f.write(f"## 详细分析\n\n{analysis}\n")
    
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"PDF 分析完成，总耗时: {duration:.2f}秒")
    logger.info(f"结果保存至: {output_path.absolute()}")


if __name__ == "__main__":
    main()
