import redis
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class SessionManager:
    """Session manager with Railway Redis support and in-memory fallback"""
    
    def __init__(self, redis_url: Optional[str] = None, timeout_minutes: int = 30):
        self.timeout_minutes = timeout_minutes
        self.redis = None
        self._memory_sessions = {}
        
        # Get Redis URL from environment or parameter
        if redis_url is None:
            redis_url = os.getenv('REDIS_URL')
        
        # Try to connect to Redis
        if redis_url:
            try:
                self.redis = redis.StrictRedis.from_url(
                    redis_url, 
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis.ping()
                logging.info(f"✅ Redis connected successfully at {redis_url.split('@')[1] if '@' in redis_url else 'localhost'}")
            except redis.ConnectionError as e:
                logging.warning(f"⚠️ Redis connection failed: {e}")
                logging.warning(f"⚠️ Falling back to in-memory sessions")
                self.redis = None
            except Exception as e:
                logging.error(f"❌ Redis error: {e}")
                self.redis = None
        else:
            logging.warning(f"⚠️ No REDIS_URL environment variable found, using in-memory sessions")

    def _session_key(self, user_id: str) -> str:
        """Generate Redis key for session"""
        return f"session:{user_id}"

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """Get session with automatic fallback to in-memory"""
        default_session = {
            "state": None, 
            "data": {}, 
            "last_activity": datetime.now().isoformat()
        }
        
        # Try Redis first
        if self.redis:
            try:
                session_data = self.redis.get(self._session_key(user_id))
                if session_data:
                    session = json.loads(session_data)
                else:
                    session = default_session.copy()
            except Exception as e:
                logging.warning(f"Redis get error for {user_id}: {e}, using in-memory")
                session = self._memory_sessions.get(user_id, default_session.copy())
        else:
            # Use in-memory
            session = self._memory_sessions.get(user_id, default_session.copy())
        
        # Update last activity timestamp
        session["last_activity"] = datetime.now().isoformat()
        
        # Save back to storage
        if self.redis:
            try:
                self.redis.setex(
                    self._session_key(user_id), 
                    timedelta(minutes=self.timeout_minutes), 
                    json.dumps(session)
                )
            except Exception as e:
                logging.warning(f"Redis setex error for {user_id}: {e}")
                self._memory_sessions[user_id] = session
        else:
            self._memory_sessions[user_id] = session
        
        return session

    def update_session(self, user_id: str, state=None, data=None):
        """Update session with fallback support"""
        session = self.get_session(user_id)
        
        if state is not None:
            session["state"] = state
        if data is not None:
            session["data"] = data
        
        session["last_activity"] = datetime.now().isoformat()
        
        # Save to Redis
        if self.redis:
            try:
                self.redis.setex(
                    self._session_key(user_id), 
                    timedelta(minutes=self.timeout_minutes), 
                    json.dumps(session)
                )
            except Exception as e:
                logging.warning(f"Redis update error for {user_id}: {e}")
                self._memory_sessions[user_id] = session
        else:
            self._memory_sessions[user_id] = session

    def clear_session(self, user_id: str):
        """Clear session from both Redis and memory"""
        if self.redis:
            try:
                self.redis.delete(self._session_key(user_id))
            except Exception as e:
                logging.warning(f"Redis delete error for {user_id}: {e}")
        
        # Always clear from in-memory
        self._memory_sessions.pop(user_id, None)

    def cleanup_expired_sessions(self):
        """
        Redis handles expiration automatically via TTL.
        For in-memory sessions, clean up old ones.
        """
        if not self.redis and self._memory_sessions:
            cutoff = (datetime.now() - timedelta(minutes=self.timeout_minutes)).isoformat()
            expired_users = [
                user_id for user_id, session in self._memory_sessions.items()
                if session.get("last_activity", "") < cutoff
            ]
            for user_id in expired_users:
                self._memory_sessions.pop(user_id, None)
            
            if expired_users:
                logging.info(f"Cleaned up {len(expired_users)} expired in-memory sessions")
            
            return len(expired_users)
        
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get session manager statistics"""
        stats = {
            "timeout_minutes": self.timeout_minutes,
            "backend": "redis" if self.redis else "in-memory",
            "redis_connected": self.redis is not None
        }
        
        if self.redis:
            try:
                # Count session keys in Redis
                cursor = 0
                count = 0
                while True:
                    cursor, keys = self.redis.scan(cursor=cursor, match="session:*", count=100)
                    count += len(keys)
                    if cursor == 0:
                        break
                stats["total_sessions"] = count
            except Exception as e:
                stats["total_sessions"] = 0
                stats["error"] = str(e)
        else:
            stats["total_sessions"] = len(self._memory_sessions)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for session manager"""
        health = {
            "healthy": True,
            "backend": "redis" if self.redis else "in-memory"
        }
        
        if self.redis:
            try:
                self.redis.ping()
                health["redis_status"] = "connected"
            except Exception as e:
                health["healthy"] = False
                health["redis_status"] = f"error: {str(e)}"
        else:
            health["redis_status"] = "not_configured"
        
        return health
