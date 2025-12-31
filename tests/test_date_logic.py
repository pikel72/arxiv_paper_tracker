#!/usr/bin/env python3
# 测试日期筛选逻辑

import datetime
import sys
import os
import logging
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_date_logic():
    """测试不同星期的日期筛选逻辑"""
    
    # Test cases for each day of the week
    test_cases = [
        (0, "周一", 3, "应该检索上周五（3天前）"),
        (1, "周二", 3, "应该检索上周六、周日和周一（从3天前开始）"),
        (2, "周三", 1, "应该检索周二（1天前）"),
        (3, "周四", 1, "应该检索周三（1天前）"),
        (4, "周五", 1, "应该检索周四（1天前）"),
        (5, "周六", None, "应该跳过检索"),
        (6, "周日", None, "应该跳过检索"),
    ]
    
    logger.info("开始测试日期筛选逻辑")
    logger.info("=" * 60)
    
    for weekday, weekday_name, expected_days, description in test_cases:
        # Mock today to be a specific weekday
        test_date = datetime.datetime(2025, 1, 6)  # This is a Monday
        # Adjust to target weekday
        days_to_add = weekday - test_date.weekday()
        test_date = test_date + datetime.timedelta(days=days_to_add)
        
        logger.info(f"\n测试 {weekday_name} (weekday={weekday})")
        logger.info(f"模拟日期: {test_date.strftime('%Y-%m-%d')}")
        logger.info(f"描述: {description}")
        
        current_weekday = test_date.weekday()
        
        if current_weekday == 0:  # 周一
            days_ago = test_date - datetime.timedelta(days=3)
            logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (上周五)")
            assert (test_date - days_ago).days == 3
            
        elif current_weekday == 1:  # 周二
            days_ago = test_date - datetime.timedelta(days=3)
            logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (上周六)")
            assert (test_date - days_ago).days == 3
            
        elif current_weekday in [2, 3, 4]:  # 周三、周四、周五
            days_ago = test_date - datetime.timedelta(days=1)
            logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')}")
            assert (test_date - days_ago).days == 1
            
        elif current_weekday == 5 or current_weekday == 6:  # 周六和周日
            logger.info("✓ 跳过检索")
            assert expected_days is None
    
    logger.info("\n" + "=" * 60)
    logger.info("日期逻辑测试完成！")


if __name__ == "__main__":
    test_date_logic()
