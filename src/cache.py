# cache.py - 缓存模块
# 用于保存中间结果，避免重复调用大模型

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent / ".cache"

# 缓存过期时间（小时）
CACHE_EXPIRY_HOURS = {
    "papers": 24,           # 论文列表缓存24小时
    "classification": 72,   # 分类结果缓存72小时
    "analysis": 168,        # 分析结果缓存7天
    "translation": 168,     # 翻译结果缓存7天
}


def _ensure_cache_dir():
    """确保缓存目录存在"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 创建 .gitignore 防止缓存被提交
    gitignore = CACHE_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n")


def _get_cache_path(cache_type: str, key: str) -> Path:
    """获取缓存文件路径"""
    _ensure_cache_dir()
    # 使用 MD5 哈希处理 key，避免文件名过长或含特殊字符
    safe_key = hashlib.md5(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{cache_type}_{safe_key}.json"


def _is_cache_valid(cache_data: dict, cache_type: str) -> bool:
    """检查缓存是否有效（未过期）"""
    if "timestamp" not in cache_data:
        return False
    
    cached_time = datetime.fromisoformat(cache_data["timestamp"])
    expiry_hours = CACHE_EXPIRY_HOURS.get(cache_type, 24)
    return datetime.now() - cached_time < timedelta(hours=expiry_hours)


def get_cache(cache_type: str, key: str) -> Optional[Any]:
    """
    获取缓存数据
    
    Args:
        cache_type: 缓存类型 (papers, classification, analysis, translation)
        key: 缓存键（如 arxiv_id 或日期字符串）
    
    Returns:
        缓存的数据，如果不存在或已过期则返回 None
    """
    cache_path = _get_cache_path(cache_type, key)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        if _is_cache_valid(cache_data, cache_type):
            logger.debug(f"缓存命中: {cache_type}/{key}")
            return cache_data.get("data")
        else:
            logger.debug(f"缓存过期: {cache_type}/{key}")
            return None
            
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"缓存读取失败: {cache_path}, 错误: {e}")
        return None


def set_cache(cache_type: str, key: str, data: Any) -> bool:
    """
    设置缓存数据
    
    Args:
        cache_type: 缓存类型
        key: 缓存键
        data: 要缓存的数据
    
    Returns:
        是否成功
    """
    cache_path = _get_cache_path(cache_type, key)
    
    try:
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "cache_type": cache_type,
            "key": key,
            "data": data
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"缓存写入: {cache_type}/{key}")
        return True
        
    except Exception as e:
        logger.warning(f"缓存写入失败: {cache_path}, 错误: {e}")
        return False


def clear_cache(cache_type: Optional[str] = None) -> int:
    """
    清除缓存
    
    Args:
        cache_type: 要清除的缓存类型，None 表示清除所有
    
    Returns:
        清除的文件数量
    """
    if not CACHE_DIR.exists():
        return 0
    
    count = 0
    pattern = f"{cache_type}_*.json" if cache_type else "*.json"
    
    for cache_file in CACHE_DIR.glob(pattern):
        try:
            cache_file.unlink()
            count += 1
        except Exception as e:
            logger.warning(f"删除缓存失败: {cache_file}, 错误: {e}")
    
    logger.info(f"清除了 {count} 个缓存文件")
    return count


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    if not CACHE_DIR.exists():
        return {"total": 0, "by_type": {}, "size_mb": 0}
    
    stats = {"total": 0, "by_type": {}, "size_mb": 0}
    total_size = 0
    
    for cache_file in CACHE_DIR.glob("*.json"):
        stats["total"] += 1
        total_size += cache_file.stat().st_size
        
        # 按类型统计
        cache_type = cache_file.stem.rsplit('_', 1)[0]
        stats["by_type"][cache_type] = stats["by_type"].get(cache_type, 0) + 1
    
    stats["size_mb"] = round(total_size / 1024 / 1024, 2)
    return stats


# ============ 便捷函数 ============

def cache_papers_list(date_key: str, papers_data: list) -> bool:
    """缓存论文列表"""
    return set_cache("papers", date_key, papers_data)


def get_cached_papers_list(date_key: str) -> Optional[list]:
    """获取缓存的论文列表"""
    return get_cache("papers", date_key)


def cache_classification(arxiv_id: str, priority: int, reason: str) -> bool:
    """缓存论文分类结果"""
    return set_cache("classification", arxiv_id, {"priority": priority, "reason": reason})


def get_cached_classification(arxiv_id: str) -> Optional[tuple]:
    """获取缓存的分类结果，返回 (priority, reason) 或 None"""
    data = get_cache("classification", arxiv_id)
    if data:
        return (data["priority"], data["reason"])
    return None


def cache_analysis(arxiv_id: str, analysis: str) -> bool:
    """缓存论文分析结果"""
    return set_cache("analysis", arxiv_id, analysis)


def get_cached_analysis(arxiv_id: str) -> Optional[str]:
    """获取缓存的分析结果"""
    return get_cache("analysis", arxiv_id)


def cache_translation(arxiv_id: str, translation: str, title_only: bool = False) -> bool:
    """缓存翻译结果"""
    cache_key = f"{arxiv_id}_title" if title_only else arxiv_id
    return set_cache("translation", cache_key, translation)


def get_cached_translation(arxiv_id: str, title_only: bool = False) -> Optional[str]:
    """获取缓存的翻译结果"""
    cache_key = f"{arxiv_id}_title" if title_only else arxiv_id
    return get_cache("translation", cache_key)
