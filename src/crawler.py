# crawler.py - 爬取论文模块

import datetime
import requests
import feedparser
import logging

from config import SEARCH_DAYS, MAX_PAPERS
from models import SimplePaper

logger = logging.getLogger(__name__)

def get_recent_papers(categories, max_results=MAX_PAPERS):
    """获取最近几天内发布的指定类别的论文"""
    # 计算最近几天的日期
    today = datetime.datetime.now()
    days_ago = today - datetime.timedelta(days=SEARCH_DAYS)
    
    # arXiv API URL
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    url = f"https://export.arxiv.org/api/query?search_query={category_query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    
    # 发送请求
    response = requests.get(url)
    if response.status_code != 200:
        logger.error("Failed to fetch data from arXiv")
        return []
    
    # 解析XML
    feed = feedparser.parse(response.content)
    
    papers = []
    for entry in feed.entries:
        # 获取提交日期
        published_date = datetime.datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
        
        # 检查是否在最近几天内
        if published_date >= days_ago:
            papers.append(SimplePaper(entry))
        else:
            # 由于结果是按日期降序排列，可以提前停止
            break
    
    logger.info(f"找到{len(papers)}篇符合条件的论文")
    return papers
