# utils/cache_manager.py
"""
In-memory caching to reduce database queries
Reduces both DB load and Railway resource usage
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
import json
import logging

class SimpleCache:
    """Simple in-memory cache to reduce DB queries"""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self.cache: Dict[str, Dict] = {}
        self.default_ttl = default_ttl
        self.logger = logging.getLogger(__name__)
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        # Check if expired
        if datetime.now() > entry['expires_at']:
            del self.cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires_at': datetime.now() + timedelta(seconds=ttl),
            'created_at': datetime.now()
        }
    
    def delete(self, key: str):
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        """Clear all cache"""
        self.cache = {}
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'estimated_db_queries_saved': self.hits
        }
    
    def cleanup_expired(self):
        """Remove expired entries"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


class CachedDatabaseOperations:
    """Wrapper for database operations with caching"""
    
    def __init__(self):
        self.cache = SimpleCache(default_ttl=300)  # 5 min
        self.logger = logging.getLogger(__name__)
    
    def get_child_data(self, user: str, db_func) -> Optional[Dict]:
        """Get child data with caching"""
        cache_key = f"child:{user}"
        
        # Try cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            self.logger.debug(f"Cache HIT: {cache_key}")
            return cached
        
        # Cache miss - query DB
        self.logger.debug(f"Cache MISS: {cache_key}")
        data = db_func(user)
        
        if data:
            # Cache for 10 minutes (child data doesn't change often)
            self.cache.set(cache_key, data, ttl=600)
        
        return data
    
    def get_user_reminders(self, user: str, db_func) -> list:
        """Get reminders with caching"""
        cache_key = f"reminders:{user}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        data = db_func(user)
        if data:
            # Cache for 5 minutes
            self.cache.set(cache_key, data, ttl=300)
        
        return data or []
    
    def get_daily_summary(self, user: str, date: str, db_func) -> Dict:
        """Get daily summary with caching"""
        cache_key = f"summary:{user}:{date}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        data = db_func(user, date)
        if data:
            # Cache for 2 minutes (summaries can be queried frequently)
            self.cache.set(cache_key, data, ttl=120)
        
        return data or {}
    
    def invalidate_user_cache(self, user: str, cache_type: Optional[str] = None):
        """Invalidate cache when data changes"""
        if cache_type:
            # Invalidate specific cache
            self.cache.delete(f"{cache_type}:{user}")
        else:
            # Invalidate all user caches
            patterns = ['child:', 'reminders:', 'summary:']
            for pattern in patterns:
                keys_to_delete = [
                    key for key in self.cache.cache.keys()
                    if key.startswith(f"{pattern}{user}")
                ]
                for key in keys_to_delete:
                    self.cache.delete(key)
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance stats"""
        stats = self.cache.get_stats()
        
        # Calculate cost savings
        # Assuming each DB query costs ~1ms server time
        # And Railway charges based on CPU time
        queries_saved = stats['estimated_db_queries_saved']
        
        stats['estimated_time_saved_ms'] = queries_saved * 1
        stats['estimated_cost_savings'] = f"${queries_saved * 0.000001:.6f}"  # Rough estimate
        
        return stats


# Batch query optimizer
class BatchQueryOptimizer:
    """Batch multiple DB queries into single queries"""
    
    @staticmethod
    def batch_get_summaries(user: str, dates: list, db_func) -> Dict[str, Any]:
        """Get summaries for multiple dates in one query"""
        # Instead of querying each date separately:
        # for date in dates:
        #     get_summary(user, date)  # 7 queries
        
        # Query once with date range:
        start_date = min(dates)
        end_date = max(dates)
        
        all_data = db_func(user, start_date, end_date)
        
        # Group by date
        by_date = {}
        for date in dates:
            by_date[date] = [d for d in all_data if d['date'] == date]
        
        return by_date
    
    @staticmethod
    def optimize_summary_query(user: str, date: str) -> str:
        """Create optimized SQL for summary"""
        # Single query instead of multiple:
        return f"""
        WITH mpasi_summary AS (
            SELECT COUNT(*) as count, SUM(volume_ml) as total_ml
            FROM mpasi_log 
            WHERE user_id = %s AND date = %s
        ),
        milk_summary AS (
            SELECT COUNT(*) as count, SUM(volume_ml) as total_ml
            FROM milk_intake
            WHERE user_id = %s AND date = %s
        ),
        sleep_summary AS (
            SELECT COUNT(*) as sessions, SUM(duration_minutes) as total_minutes
            FROM sleep_log
            WHERE user_id = %s AND date = %s
        )
        SELECT * FROM mpasi_summary, milk_summary, sleep_summary;
        """


# Integration in handlers
"""
# In your main.py or handlers initialization:
cache_manager = CachedDatabaseOperations()

# In handlers, replace direct DB calls:
# OLD:
child_data = get_child(user)

# NEW:
child_data = cache_manager.get_child_data(user, get_child)

# When updating data, invalidate cache:
save_child(user, data)
cache_manager.invalidate_user_cache(user, 'child')

# Monitor performance:
cache_stats = cache_manager.get_cache_stats()
logger.info(f"Cache stats: {cache_stats}")
"""


# Connection pool optimization
class OptimizedConnectionPool:
    """Optimize database connection pool"""
    
    @staticmethod
    def get_optimal_pool_size(max_concurrent_users: int = 10) -> Dict[str, int]:
        """Calculate optimal pool size"""
        return {
            'min_connections': 2,  # Keep 2 always open
            'max_connections': max_concurrent_users + 2,  # One per user + buffer
            'idle_timeout': 300,  # 5 minutes
            'max_overflow': 5  # Allow temporary burst
        }
    
    @staticmethod
    def optimize_query_timeout() -> int:
        """Get optimal query timeout"""
        return 5  # 5 seconds max per query


# Cost estimation
class CostEstimator:
    """Estimate cost savings from optimization"""
    
    @staticmethod
    def estimate_db_cost_savings(queries_per_day_before: int, 
                                 queries_per_day_after: int) -> Dict:
        """Estimate DB cost savings"""
        # Railway charges based on total resource usage
        # Each query uses ~1ms CPU time
        
        time_saved_per_day = (queries_per_day_before - queries_per_day_after) * 0.001  # seconds
        
        # Railway costs roughly $0.000008 per CPU second
        cost_saved_per_day = time_saved_per_day * 0.000008
        cost_saved_per_month = cost_saved_per_day * 30
        
        return {
            'queries_saved_per_day': queries_per_day_before - queries_per_day_after,
            'time_saved_per_day_seconds': time_saved_per_day,
            'cost_saved_per_month': f"${cost_saved_per_month:.4f}",
            'improvement_percent': f"{((queries_per_day_before - queries_per_day_after) / queries_per_day_before * 100):.1f}%"
        }
