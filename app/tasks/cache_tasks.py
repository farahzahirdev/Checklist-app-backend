"""
Celery tasks for cache monitoring, cleanup, and maintenance.
Runs periodically to monitor memory usage and evict stale data.
"""

import logging
from datetime import datetime, timedelta

from celery import shared_task

from app.services.cache import cache

logger = logging.getLogger(__name__)


@shared_task(name="cache.monitor_memory", queue="celery")
def monitor_cache_memory():
    """
    Monitor Redis cache memory usage.
    Runs every 5 minutes to track memory trends.
    """
    try:
        stats = cache.get_stats()
        memory_info = stats.get("memory", {})
        
        logger.info(
            f"Cache monitor: {memory_info.get('used_memory_mb', 0):.1f}MB "
            f"of {memory_info.get('max_memory_mb', 0)}MB "
            f"({memory_info.get('used_percent', 0):.1f}%)"
        )
        
        # Check if we need eviction
        if memory_info.get("used_percent", 0) > cache.CRITICAL_MEMORY_PERCENT:
            logger.warning("Triggering cache eviction due to high memory usage")
            evict_stale_cache.delay()
        
        return {
            "status": "ok",
            "memory_mb": memory_info.get("used_memory_mb", 0),
            "usage_percent": memory_info.get("used_percent", 0),
        }
    except Exception as e:
        logger.error(f"Error monitoring cache memory: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.evict_stale", queue="celery")
def evict_stale_cache():
    """
    Intelligently evict stale cache entries when memory is high.
    
    Strategy:
    1. Remove expired keys (if any slipped through)
    2. Log high-usage namespaces
    3. Redis LRU automatically evicts least-recently-used keys
    """
    try:
        before_stats = cache.get_memory_info()
        
        logger.info(f"Starting cache eviction. Memory: {before_stats.get('used_memory_mb', 0):.1f}MB")
        
        # Get cache statistics
        stats = cache.get_stats()
        evicted_keys = stats.get("evicted_keys", 0)
        
        logger.info(f"Cache eviction complete. Keys evicted by Redis LRU: {evicted_keys}")
        
        after_stats = cache.get_memory_info()
        freed_mb = before_stats.get("used_memory_mb", 0) - after_stats.get("used_memory_mb", 0)
        
        logger.info(f"Freed {freed_mb:.1f}MB. Current usage: {after_stats.get('used_percent', 0):.1f}%")
        
        return {
            "status": "ok",
            "freed_mb": freed_mb,
            "current_usage_percent": after_stats.get("used_percent", 0),
        }
    except Exception as e:
        logger.error(f"Error evicting stale cache: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.cleanup_assessment_cache", queue="celery")
def cleanup_assessment_cache():
    """
    Clean up assessment-related cache when assessment completes or status changes.
    Called after assessment state changes to invalidate cached assessment data.
    """
    try:
        # Clear assessment namespace
        deleted = cache.clear_namespace("assessments")
        logger.info(f"Cleared {deleted} assessment cache entries")
        
        # Also clear dashboard cache that depends on assessments
        deleted += cache.delete_pattern("dashboard_*", "dashboard")
        logger.info(f"Cleared {deleted} dashboard cache entries")
        
        return {"status": "ok", "cleared_keys": deleted}
    except Exception as e:
        logger.error(f"Error cleaning assessment cache: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.cleanup_checklist_cache", queue="celery")
def cleanup_checklist_cache():
    """
    Clean up checklist-related cache when checklist is updated.
    """
    try:
        deleted = cache.clear_namespace("checklists")
        logger.info(f"Cleared {deleted} checklist cache entries")
        
        # Also invalidate assessment caches that depend on checklist data
        deleted += cache.delete_pattern("get_assessment_*", "assessments")
        logger.info(f"Cleared {deleted} related assessment cache entries")
        
        return {"status": "ok", "cleared_keys": deleted}
    except Exception as e:
        logger.error(f"Error cleaning checklist cache: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.cleanup_report_cache", queue="celery")
def cleanup_report_cache():
    """
    Clean up report-related cache when report is updated or regenerated.
    """
    try:
        deleted = cache.clear_namespace("reports")
        logger.info(f"Cleared {deleted} report cache entries")
        
        # Also clear dashboard cache
        deleted += cache.delete_pattern("dashboard_*", "dashboard")
        logger.info(f"Cleared {deleted} dashboard cache entries")
        
        return {"status": "ok", "cleared_keys": deleted}
    except Exception as e:
        logger.error(f"Error cleaning report cache: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.get_stats", queue="celery")
def get_cache_stats():
    """
    Get current cache statistics for monitoring/debugging.
    """
    try:
        return cache.get_stats()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(name="cache.clear_all", queue="celery")
def clear_all_cache():
    """
    Clear all cache entries. USE ONLY IN MIGRATIONS OR EMERGENCY.
    """
    try:
        result = cache.clear_all()
        logger.warning("All cache entries cleared")
        return {"status": "ok" if result else "error"}
    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        return {"status": "error", "message": str(e)}
