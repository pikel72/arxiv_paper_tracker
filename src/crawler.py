# crawler.py - 爬取论文模块

import datetime
import requests
import feedparser
import logging
from typing import Optional, Tuple

from config import SEARCH_DAYS, MAX_PAPERS
from models import SimplePaper

logger = logging.getLogger(__name__)


def parse_date_arg(date_str: str) -> Tuple[datetime.datetime, datetime.datetime]:
    """
    解析日期参数，支持单日期和日期范围
    
    格式:
        - 单日期: "2025-12-25" 
        - 日期范围: "2025-12-20:2025-12-25"
    
    Returns:
        (start_time, end_time) UTC 时间元组
    """
    tz = datetime.timezone.utc
    
    if ':' in date_str:
        # 日期范围
        start_str, end_str = date_str.split(':', 1)
        start_date = datetime.datetime.strptime(start_str.strip(), '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_str.strip(), '%Y-%m-%d')
    else:
        # 单日期
        start_date = datetime.datetime.strptime(date_str.strip(), '%Y-%m-%d')
        end_date = start_date
    
    # arXiv 论文发布时间是 UTC 18:00，所以我们用前一天18:00到当天18:00
    start_time = start_date.replace(hour=18, minute=0, second=0, microsecond=0, tzinfo=tz) - datetime.timedelta(days=1)
    end_time = end_date.replace(hour=18, minute=0, second=0, microsecond=0, tzinfo=tz)
    
    return start_time, end_time


def get_recent_papers(categories, max_results=MAX_PAPERS, target_date: Optional[str] = None):
    """
    获取最近几天内发布或更新的指定类别的论文（基于最后更新日期）
    
    Args:
        categories: arXiv 类别列表
        max_results: 最大返回数量
        target_date: 指定日期，格式 "2025-12-25" 或 "2025-12-20:2025-12-25"
                    如果为 None，则按当前日期和星期自动计算
    """
    today = datetime.datetime.now(datetime.timezone.utc)
    
    # 如果指定了日期，直接使用
    if target_date:
        try:
            start_time, end_time = parse_date_arg(target_date)
            logger.info(f"使用指定日期范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
        except ValueError as e:
            logger.error(f"日期格式错误: {target_date}，应为 YYYY-MM-DD 或 YYYY-MM-DD:YYYY-MM-DD")
            return []
    else:
        # 原有的按星期自动计算逻辑
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

        # 根据 SEARCH_DAYS 扩展时间区间宽度（SEARCH_DAYS=1表示基础区间，=2表示向前扩展1天，以此类推）
        if SEARCH_DAYS > 1:
            start_time = start_time - datetime.timedelta(days=SEARCH_DAYS - 1)

        logger.info(f"今天是周{weekday+1}, 搜索区间: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    # arXiv API URL - 按最后更新日期排序（包括新发布和更新的论文）
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    # 添加时间范围参数，确保返回足够论文
    start_date = start_time.strftime('%Y%m%d')
    end_date = end_time.strftime('%Y%m%d')
        # 使用submittedDate参数，格式为YYYYMMDD
    url = f"https://export.arxiv.org/api/query?search_query=({category_query}) AND submittedDate:[{start_date} TO {end_date}]&sortBy=lastUpdatedDate&max_results={max_results}"

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
        title = entry.title if hasattr(entry, 'title') else '(无标题)'
        submit_date = datetime.datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        if start_time <= submit_date < end_time:
            logger.info(f"通过筛选: {title} | 提交时间: {submit_date}")
            papers.append(SimplePaper(entry))
        else:
            logger.info(f"未通过筛选: {title} | 提交时间: {submit_date}")
    
    logger.info(f"找到{len(papers)}篇符合条件的论文")
    return papers
