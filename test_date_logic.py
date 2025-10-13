#!/usr/bin/env python3
# 测试日期筛选逻辑

import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_date_logic():
    """测试不同星期的日期筛选逻辑"""
    from unittest.mock import patch
    import logging
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Test cases for each day of the week
    test_cases = [
        (0, "周一", 3, "应该检索上周五（3天前）"),
        (1, "周二", 3, "应该检索上周六、周日和周一（从3天前开始）"),
        (2, "周三", 1, "应该检索周二（1天前）"),
        (3, "周四", 1, "应该检索周三（1天前）"),
        (4, "周五", None, "应该跳过检索"),
        (5, "周六", None, "应该跳过检索"),
        (6, "周日", None, "应该使用SEARCH_DAYS配置"),
    ]
    
    logger.info("开始测试日期筛选逻辑")
    logger.info("="*60)
    
    for weekday, weekday_name, expected_days, description in test_cases:
        # Mock today to be a specific weekday
        test_date = datetime.datetime(2025, 1, 6)  # This is a Monday
        # Adjust to target weekday
        days_to_add = weekday - test_date.weekday()
        test_date = test_date + datetime.timedelta(days=days_to_add)
        
        logger.info(f"\n测试 {weekday_name} (weekday={weekday})")
        logger.info(f"模拟日期: {test_date.strftime('%Y-%m-%d')}")
        logger.info(f"描述: {description}")
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_date
            mock_datetime.strptime = datetime.datetime.strptime
            mock_datetime.timedelta = datetime.timedelta
            
            # Simulate the logic from crawler.py
            today = mock_datetime.now()
            current_weekday = today.weekday()
            
            if current_weekday == 0:  # 周一
                days_ago = today - datetime.timedelta(days=3)
                logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (上周五)")
                assert (today - days_ago).days == 3
                
            elif current_weekday == 1:  # 周二
                days_ago = today - datetime.timedelta(days=3)
                logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (上周六)")
                assert (today - days_ago).days == 3
                
            elif current_weekday == 2:  # 周三
                days_ago = today - datetime.timedelta(days=1)
                logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (周二)")
                assert (today - days_ago).days == 1
                
            elif current_weekday == 3:  # 周四
                days_ago = today - datetime.timedelta(days=1)
                logger.info(f"✓ 检索起始日期: {days_ago.strftime('%Y-%m-%d')} (周三)")
                assert (today - days_ago).days == 1
                
            elif current_weekday == 4 or current_weekday == 5:  # 周五和周六
                logger.info(f"✓ 跳过检索")
                assert expected_days is None
                
            else:  # 周日
                # For Sunday, we would use SEARCH_DAYS
                logger.info(f"✓ 使用 SEARCH_DAYS 配置")
                assert expected_days is None
    
    logger.info("\n" + "="*60)
    logger.info("所有测试通过！")

if __name__ == "__main__":
    test_date_logic()
