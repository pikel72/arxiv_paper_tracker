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
    # 计算需要检索的日期范围，精确到前一天18:00到当天18:00，保留原有按星期逻辑
    today = datetime.datetime.utcnow()
    weekday = today.weekday()  # 0=周一, 1=周二, ..., 6=周日

    # 按星期逻辑确定检索区间
    if weekday == 0:  # 周一：检索上周四18:00 ~ 上周五18:00（UTC）
        start_time = (today - datetime.timedelta(days=4)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = (today - datetime.timedelta(days=3)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif weekday == 1:  # 周二：检索上周五18:00 ~ 本周一18:00（UTC）
        start_time = (today - datetime.timedelta(days=4)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = (today - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif weekday == 2:  # 周三：检索本周一18:00 ~ 本周二18:00（UTC）
        start_time = (today - datetime.timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = (today - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif weekday == 3:  # 周四：检索本周二18:00 ~ 本周三18:00（UTC）
        start_time = (today - datetime.timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = (today - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif weekday == 4:  # 周五：检索本周三18:00 ~ 本周四18:00（UTC）
        start_time = (today - datetime.timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = (today - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif weekday == 5 or weekday == 6:  # 周六、周日：跳过检索
        logger.info(f"今天是周{weekday+1}，跳过论文检索")
        return []
    else:  # 兜底
        start_time = (today - datetime.timedelta(days=SEARCH_DAYS)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_time = today.replace(hour=18, minute=0, second=0, microsecond=0)

    logger.info(f"今天是周{weekday+1}, 搜索区间: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    # arXiv API URL - 按最后更新日期排序（包括新发布和更新的论文）
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    url = f"https://export.arxiv.org/api/query?search_query={category_query}&sortBy=lastUpdatedDate&max_results={max_results}"

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

        # 检查是否在指定区间内
        if start_time <= updated_date < end_time:
            papers.append(SimplePaper(entry))
        elif updated_date < start_time:
            # 由于结果是按更新日期降序排列，可以提前停止
            logger.info(f"停止于更新日期: {updated_date}, 区间起点: {start_time}")
            break
    
    logger.info(f"找到{len(papers)}篇符合条件的论文")
    return papers
