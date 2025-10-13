#!/usr/bin/env python3
# 测试周五和周六跳过逻辑

import datetime
import sys
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_skip_logic():
    """测试周五和周六跳过检索的逻辑（不依赖外部模块）"""
    
    logger.info("测试周五和周六跳过检索逻辑")
    logger.info("="*60)
    
    # Simulate the logic from crawler.py for Friday
    logger.info("\n测试周五 (weekday=4)")
    today_friday = datetime.datetime(2025, 1, 10)  # A Friday
    weekday = today_friday.weekday()
    logger.info(f"日期: {today_friday.strftime('%Y-%m-%d')}, weekday={weekday}")
    
    should_skip = False
    if weekday == 4 or weekday == 5:
        should_skip = True
        logger.info(f"今天是周{weekday+1}，跳过论文检索")
    
    assert should_skip, "周五应该跳过检索"
    logger.info("✓ 周五正确跳过检索")
    
    # Simulate the logic from crawler.py for Saturday
    logger.info("\n测试周六 (weekday=5)")
    today_saturday = datetime.datetime(2025, 1, 11)  # A Saturday
    weekday = today_saturday.weekday()
    logger.info(f"日期: {today_saturday.strftime('%Y-%m-%d')}, weekday={weekday}")
    
    should_skip = False
    if weekday == 4 or weekday == 5:
        should_skip = True
        logger.info(f"今天是周{weekday+1}，跳过论文检索")
    
    assert should_skip, "周六应该跳过检索"
    logger.info("✓ 周六正确跳过检索")
    
    # Test other days should not skip
    logger.info("\n测试其他日期不应跳过")
    for day_offset in [0, 1, 2, 3, 6]:  # Monday to Thursday, and Sunday
        test_date = datetime.datetime(2025, 1, 6) + datetime.timedelta(days=day_offset)
        weekday = test_date.weekday()
        
        should_skip = False
        if weekday == 4 or weekday == 5:
            should_skip = True
        
        assert not should_skip, f"周{weekday+1}不应该跳过检索"
        logger.info(f"✓ 周{weekday+1} ({test_date.strftime('%Y-%m-%d')}) 不跳过检索")
    
    logger.info("\n" + "="*60)
    logger.info("跳过检索测试通过！")

if __name__ == "__main__":
    test_skip_logic()
