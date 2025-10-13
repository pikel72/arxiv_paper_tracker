# crawler.py - 爬取论文模块

import datetime
import requests
import feedparser
import logging

from config import SEARCH_DAYS, MAX_PAPERS
from models import SimplePaper

logger = logging.getLogger(__name__)

def get_recent_papers(categories, max_results=MAX_PAPERS):
    """获取最近几天内发布或更新的指定类别的论文（基于最后更新日期）"""
    # 计算需要检索的日期范围，精确匹配arXiv的发布周期
    today = datetime.datetime.now()
    weekday = today.weekday()  # 0=周一, 1=周二, ..., 6=周日
    
    # arXiv发布规则：
    # 周一：发布上周五的提交
    # 周二：发布上周六、周日和周一的提交
    # 周三：发布前一天的提交（周二）
    # 周四：发布前一天的提交（周三）
    # 周五和周六：不进行检索
    # 周日：正常检索最近几天
    
    if weekday == 0:  # 周一：检索上周五
        days_ago = today - datetime.timedelta(days=3)  # 上周五
    elif weekday == 1:  # 周二：检索上周六、周日和周一
        days_ago = today - datetime.timedelta(days=3)  # 上周六开始
    elif weekday == 2:  # 周三：检索周二
        days_ago = today - datetime.timedelta(days=1)  # 周二
    elif weekday == 3:  # 周四：检索周三
        days_ago = today - datetime.timedelta(days=1)  # 周三
    elif weekday == 4 or weekday == 5:  # 周五和周六：跳过检索
        logger.info(f"今天是周{weekday+1}，跳过论文检索")
        return []
    else:  # 周日：正常检索最近几天
        days_ago = today - datetime.timedelta(days=SEARCH_DAYS)
    
    logger.info(f"今天是周{weekday+1}, 搜索起始日期: {days_ago.strftime('%Y-%m-%d')}")
    
    # arXiv API URL - 按最后更新日期排序（包括新发布和更新的论文）
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    url = f"https://export.arxiv.org/api/query?search_query={category_query}&sortBy=lastUpdatedDate&sortOrder=descending&max_results={max_results}"
    
    logger.info(f"API请求URL: {url}")
    logger.info(f"最大论文数: {max_results}")
    
    # 发送请求
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"Failed to fetch data from arXiv, status: {response.status_code}")
        return []
    
    # 解析XML
    feed = feedparser.parse(response.content)
    logger.info(f"API返回的总条目数: {len(feed.entries)}")
    
    papers = []
    for entry in feed.entries:
        # 获取最后更新日期（使用updated字段）
        updated_date = datetime.datetime.strptime(entry.updated, "%Y-%m-%dT%H:%M:%SZ")
        
        # 检查是否在最近几天内更新过
        if updated_date >= days_ago:
            papers.append(SimplePaper(entry))
        else:
            # 由于结果是按更新日期降序排列，可以提前停止
            logger.info(f"停止于更新日期: {updated_date}, 目标日期: {days_ago}")
            break
    
    logger.info(f"找到{len(papers)}篇符合条件的论文")
    return papers
