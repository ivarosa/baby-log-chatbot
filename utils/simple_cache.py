"""
Ultra-simple in-memory cache for high-value data only
NO external dependencies, just Python dict
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Dict

class SimpleCache:
    """
    Minimal cache for 3 specific use cases:
    1. Child data (rarely changes)
    2. User settings (almost never changes)
    3. User reminders (changes rarely)
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self.stats = {'hits': 0, 'misses': 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache if not expired"""
        if key not in self._cache:
            self.stats['misses'] += 1
            return None
        
        entry = self._cache[key]
        
        # Check expiry
        if datetime.now() > entry['expires_at']:
            del self._cache[key]
            self.stats['misses'] += 1
            return None
        
        self.stats['hits'] += 1
        return entry['value']
    
    def set(self, key: str, value: Any, ttl_seconds: int):
        """Set cache with TTL"""
        self._cache[key] = {
            'value': value,
            'expires_at': datetime.now() + timedelta(seconds=ttl_seconds)
        }
    
    def delete(self, key: str):
        """Delete specific key (for cache invalidation)"""
        if key in self._cache:
            del self._cache[key]
    
    def clear_user(self, user: str):
        """Clear all cache for a user (when they update data)"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{user}:")]
        for key in keys_to_delete:
            del self._cache[key]
    
    def get_stats(self) -> dict:
        """Get cache performance stats"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'size': len(self._cache)
        }

# Initialize global cache (in main.py)
simple_cache = SimpleCache()
