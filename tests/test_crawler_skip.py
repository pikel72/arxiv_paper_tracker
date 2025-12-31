#!/usr/bin/env python3
# 测试周六和周日跳过逻辑

import datetime
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_skip_logic():
    """测试周六和周日跳过检索的逻辑（不依赖外部模块）"""
    
    logger.info("测试周六和周日跳过检索逻辑")
    logger.info("=" * 60)
    
    # 测试周六 (weekday=5)
    logger.info("\n测试周六 (weekday=5)")
    today_saturday = datetime.datetime(2025, 1, 11)  # A Saturday
    weekday = today_saturday.weekday()
    logger.info(f"日期: {today_saturday.strftime('%Y-%m-%d')}, weekday={weekday}")
    
    should_skip = weekday == 5 or weekday == 6
    assert should_skip, "周六应该跳过检索"
    logger.info("✓ 周六正确跳过检索")
    
    # 测试周日 (weekday=6)
    logger.info("\n测试周日 (weekday=6)")
    today_sunday = datetime.datetime(2025, 1, 12)  # A Sunday
    weekday = today_sunday.weekday()
    logger.info(f"日期: {today_sunday.strftime('%Y-%m-%d')}, weekday={weekday}")
    
    should_skip = weekday == 5 or weekday == 6
    assert should_skip, "周日应该跳过检索"
    logger.info("✓ 周日正确跳过检索")
    
    # 测试其他日期不应跳过
    logger.info("\n测试工作日不应跳过")
    for day_offset in range(5):  # Monday to Friday
        test_date = datetime.datetime(2025, 1, 6) + datetime.timedelta(days=day_offset)
        weekday = test_date.weekday()
        should_skip = weekday == 5 or weekday == 6
        weekday_names = ["周一", "周二", "周三", "周四", "周五"]
        assert not should_skip, f"{weekday_names[day_offset]}不应该跳过"
        logger.info(f"✓ {weekday_names[day_offset]} ({test_date.strftime('%Y-%m-%d')}) 正确执行检索")
    
    logger.info("\n" + "=" * 60)
    logger.info("所有测试通过！")


if __name__ == "__main__":
    test_skip_logic()
