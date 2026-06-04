# crawler.py - 爬取论文模块

import datetime
import feedparser
import logging
import time
from typing import Optional, Tuple

import requests

from config import SEARCH_DAYS, MAX_PAPERS
from models import SimplePaper

logger = logging.getLogger(__name__)


def _get_retry_after_seconds(response, fallback: int) -> int:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return max(int(retry_after), fallback)
        except (TypeError, ValueError):
            pass
    return fallback


def _fetch_arxiv_response(url: str, max_retries: int = 4, timeout: int = 30):
    backoff = 10
    last_status = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response

            last_status = response.status_code
            if response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                wait_time = _get_retry_after_seconds(response, backoff)
                logger.warning(f"arXiv 暂时不可用，状态码: {response.status_code}，第 {attempt}/{max_retries} 次重试，等待 {wait_time}s")
                time.sleep(wait_time)
                backoff *= 2
                continue

            logger.error(f"Failed to fetch data from arXiv, status: {response.status_code}")
            return None
        except requests.RequestException as e:
            if attempt < max_retries:
                logger.warning(f"请求 arXiv 失败: {str(e)}，第 {attempt}/{max_retries} 次重试")
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.error(f"请求 arXiv 最终失败: {str(e)}")
            return None

    if last_status is not None:
        logger.error(f"Failed to fetch data from arXiv, status: {last_status}")
    return None


def _search_window_for_date(date: datetime.datetime) -> Tuple[datetime.datetime, datetime.datetime]:
    """
    给定一个公告日期，返回对应的 submittedDate 搜索窗口（UTC）。

    arXiv 节奏：工作日 18:00 UTC 截止提交 → 下一个工作日公告。
    周末提交 → 周一公告（和上周五一起）。

    - 周一公告 = 只有周五提交的 → 搜索 [D-3 18:00, D-2 18:00]
    - 周二公告 = 周六+周日+周一提交的 → 搜索 [D-3 18:00, D-1 18:00]
    - 周三~周五公告 = 前一天提交的 → 搜索 [D-2 18:00, D-1 18:00]
    """
    tz = datetime.timezone.utc
    base = date.replace(hour=18, minute=0, second=0, microsecond=0, tzinfo=tz)
    weekday = date.weekday()

    if weekday == 0:  # 周一：只有周五的论文
        return base - datetime.timedelta(days=3), base - datetime.timedelta(days=2)
    elif weekday == 1:  # 周二：周六+周日+周一的论文
        return base - datetime.timedelta(days=3), base - datetime.timedelta(days=1)
    else:  # 周三~周五：前一天的论文
        return base - datetime.timedelta(days=2), base - datetime.timedelta(days=1)


def parse_date_arg(date_str: str) -> Tuple[datetime.datetime, datetime.datetime]:
    """
    解析日期参数，支持单日期和日期范围

    格式:
        - 单日期: "20251225" 或 "2025-12-25"
        - 日期范围: "20251220:20251225" 或 "2025-12-20:2025-12-25"

    Returns:
        (start_time, end_time) UTC 时间元组，对应 submittedDate 搜索窗口
    """
    def parse_single_date(s: str) -> datetime.datetime:
        """解析单个日期，支持 YYYYMMDD 和 YYYY-MM-DD 格式"""
        s = s.strip()
        if '-' in s:
            return datetime.datetime.strptime(s, '%Y-%m-%d')
        else:
            return datetime.datetime.strptime(s, '%Y%m%d')

    if ':' in date_str:
        start_str, end_str = date_str.split(':', 1)
        start_date = parse_single_date(start_str)
        end_date = parse_single_date(end_str)
    else:
        start_date = parse_single_date(date_str)
        end_date = start_date

    search_start, _ = _search_window_for_date(start_date)
    _, search_end = _search_window_for_date(end_date)

    return search_start, search_end


def _format_arxiv_datetime(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime('%Y%m%d%H%M')


def get_recent_papers(categories, max_results=MAX_PAPERS, target_date: Optional[str] = None):
    """
    获取最近几天内发布或更新的指定类别的论文（基于最后更新日期）
    
    Args:
        categories: arXiv 类别列表
        max_results: 最大返回数量
        target_date: 指定日期，格式 "20251225" 或 "20251220:20251225" (也支持 "2025-12-25" 格式)
                    如果为 None，则按当前日期和星期自动计算
    """
    today = datetime.datetime.now(datetime.timezone.utc)
    
    # 如果指定了日期，直接使用
    if target_date:
        try:
            start_time, end_time = parse_date_arg(target_date)
            logger.info(f"使用指定日期范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
        except ValueError as e:
            logger.error(f"日期格式错误: {target_date}，应为 YYYYMMDD 或 YYYYMMDD:YYYYMMDD (也支持 YYYY-MM-DD 格式)")
            return []
    else:
        # 原有的按星期自动计算逻辑
        weekday = today.weekday()  # 0=周一, 1=周二, ..., 6=周日

        # 按星期逻辑确定检索区间（arXiv: 工作日18:00 UTC截止→次日公告，周末→周一公告）
        if weekday == 0:  # 周一公告 = 只有周五提交的论文
            start_time = (today - datetime.timedelta(days=5)).replace(hour=18, minute=0, second=0, microsecond=0)
            end_time = (today - datetime.timedelta(days=4)).replace(hour=18, minute=0, second=0, microsecond=0)
        elif weekday == 1:  # 周二公告 = 周六+周日+周一提交的论文
            start_time = (today - datetime.timedelta(days=3)).replace(hour=18, minute=0, second=0, microsecond=0)
            end_time = (today - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        elif weekday in (2, 3, 4):  # 周三~周五公告 = 前一天提交的论文
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
    start_date = _format_arxiv_datetime(start_time)
    end_date = _format_arxiv_datetime(end_time)
        # 使用submittedDate参数，格式为YYYYMMDDHHMM
    url = f"https://export.arxiv.org/api/query?search_query=({category_query}) AND submittedDate:[{start_date} TO {end_date}]&sortBy=submittedDate&max_results={max_results}"

    logger.info(f"API请求URL: {url}")
    logger.info(f"最大论文数: {max_results}")
    
    # 发送请求
    response = _fetch_arxiv_response(url)
    if response is None:
        return []
    
    # 解析XML
    feed = feedparser.parse(response.content)
    logger.info(f"API返回的总条目数: {len(feed.entries)}")

    papers = []
    for entry in feed.entries:
        submit_date = datetime.datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        if start_time <= submit_date < end_time:
            papers.append(SimplePaper(entry))

    logger.info(f"找到{len(papers)}篇符合条件的论文")
    return papers
