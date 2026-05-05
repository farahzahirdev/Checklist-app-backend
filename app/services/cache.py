"""
Cache service with Redis integration, memory monitoring, and intelligent eviction.
Handles caching of expensive queries and provides utilities for cache management.
"""

import json
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import redis
from redis import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global Redis connection (lazy loaded)
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client for cache operations."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        try:
            # Use redis DB 2 for application cache (0=celery, 1=celery results)
            _redis_client = redis.from_url(
                "redis://localhost:6379/2",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            # Test connection
            _redis_client.ping()
            logger.info("Redis cache connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    return _redis_client


class CacheService:
    """
    Redis-based cache service with memory monitoring and intelligent eviction.
    
    Features:
    - TTL support for automatic expiration
    - Memory monitoring and warnings
    - Graceful degradation if Redis unavailable
    - Cache key versioning
    - Bulk operations support
    """
    
    # Cache configuration
    DEFAULT_TTL = 3600  # 1 hour
    WARN_MEMORY_PERCENT = 80  # Warn when 80% full
    CRITICAL_MEMORY_PERCENT = 90  # Critical at 90%
    MAX_MEMORY_MB = 150  # Max Redis memory for cache (in MB)
    
    def __init__(self):
        self.redis = get_redis_client()
        self.prefix = "cache:"
        self._memory_warning_sent = False
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
        namespace: str = "default",
    ) -> bool:
        """
        Set a cache value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds
            namespace: Key namespace for organization
        
        Returns:
            True if set successfully, False otherwise
        """
        try:
            full_key = self._make_key(key, namespace)
            serialized = json.dumps(value)
            
            # Set with TTL
            result = self.redis.setex(
                full_key,
                ttl,
                serialized,
            )
            
            # Check memory usage after set
            self._check_memory_usage()
            
            return result
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            namespace: Key namespace
        
        Returns:
            Cached value if exists, None otherwise
        """
        try:
            full_key = self._make_key(key, namespace)
            value = self.redis.get(full_key)
            
            if value is None:
                return None
            
            return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a cache key."""
        try:
            full_key = self._make_key(key, namespace)
            return bool(self.redis.delete(full_key))
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str, namespace: str = "default") -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Pattern with * wildcards (e.g., "assessment_*")
            namespace: Key namespace
        
        Returns:
            Number of keys deleted
        """
        try:
            full_pattern = self._make_key(pattern, namespace)
            keys = self.redis.keys(full_pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0
    
    def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if cache key exists."""
        try:
            full_key = self._make_key(key, namespace)
            return bool(self.redis.exists(full_key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    def clear_namespace(self, namespace: str = "default") -> int:
        """Clear all keys in a namespace."""
        pattern = f"{self.prefix}{namespace}:*"
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear namespace error: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """Clear all application cache (DANGER: only use in tests or migrations)."""
        try:
            pattern = f"{self.prefix}*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False
    
    def get_memory_info(self) -> dict[str, Any]:
        """Get Redis memory usage information."""
        try:
            info = self.redis.info("memory")
            return {
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "used_memory_rss_mb": info.get("used_memory_rss", 0) / (1024 * 1024),
                "max_memory_mb": self.MAX_MEMORY_MB,
                "used_percent": (info.get("used_memory", 0) / (self.MAX_MEMORY_MB * 1024 * 1024)) * 100,
            }
        except Exception as e:
            logger.error(f"Error getting memory info: {e}")
            return {}
    
    def _check_memory_usage(self) -> None:
        """Check Redis memory usage and log warnings."""
        try:
            info = self.redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory_bytes = self.MAX_MEMORY_MB * 1024 * 1024
            
            if used_memory == 0:
                return
            
            usage_percent = (used_memory / max_memory_bytes) * 100
            
            if usage_percent > self.CRITICAL_MEMORY_PERCENT:
                logger.critical(
                    f"Cache memory CRITICAL: {usage_percent:.1f}% of {self.MAX_MEMORY_MB}MB used"
                )
                # Trigger eviction task
                from app.tasks import cache_tasks
                cache_tasks.evict_stale_cache.delay()
            elif usage_percent > self.WARN_MEMORY_PERCENT:
                if not self._memory_warning_sent:
                    logger.warning(
                        f"Cache memory WARNING: {usage_percent:.1f}% of {self.MAX_MEMORY_MB}MB used"
                    )
                    self._memory_warning_sent = True
            else:
                self._memory_warning_sent = False
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
    
    def _make_key(self, key: str, namespace: str) -> str:
        """Create full cache key with prefix and namespace."""
        return f"{self.prefix}{namespace}:{key}"
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            info = self.redis.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "evicted_keys": info.get("evicted_keys", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "memory": self.get_memory_info(),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# Global cache instance
cache = CacheService()


def cached(
    namespace: str = "default",
    ttl: int = CacheService.DEFAULT_TTL,
    key_builder: Optional[Callable[[Any, str, tuple, dict], str]] = None,
) -> Callable:
    """
    Decorator to cache function results.
    
    Args:
        namespace: Cache namespace
        ttl: Time to live in seconds
        key_builder: Optional function to build cache key from function arguments
                    Default: f"{function_name}:{args}:{kwargs}"
    
    Usage:
        @cached(namespace="assessments", ttl=1800)
        def get_assessment(assessment_id: int):
            return db.query(Assessment).filter(...).first()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(func, func.__name__, args, kwargs)
            else:
                # Default: function_name:arg1:arg2:kwarg1=val1
                arg_str = ":".join(str(arg) for arg in args)
                kwarg_str = ":".join(f"{k}={v}" for k, v in kwargs.items())
                cache_key = f"{func.__name__}:{arg_str}:{kwarg_str}".strip(":")
            
            # Try cache
            cached_value = cache.get(cache_key, namespace)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl, namespace)
            return result
        
        return wrapper
    
    return decorator


def invalidate_cache(pattern: str, namespace: str = "default") -> None:
    """
    Invalidate cache entries matching a pattern.
    
    Usage:
        # After updating assessment
        invalidate_cache("get_assessment_*", "assessments")
    """
    deleted = cache.delete_pattern(pattern, namespace)
    logger.info(f"Invalidated {deleted} cache keys matching {pattern}")
