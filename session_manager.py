import redis
import json
from datetime import datetime, timedelta

class SessionManager:
    def __init__(self, redis_url='redis://localhost:6379/0', timeout_minutes=30):
        self.redis = redis.StrictRedis.from_url(redis_url, decode_responses=True)
        self.timeout_minutes = timeout_minutes

    def _session_key(self, user_id):
        return f"session:{user_id}"

    def get_session(self, user_id):
        session_data = self.redis.get(self._session_key(user_id))
        if session_data:
            session = json.loads(session_data)
        else:
            session = {"state": None, "data": {}, "last_activity": datetime.now().isoformat()}
        # Always update last_activity
        session["last_activity"] = datetime.now().isoformat()
        self.redis.setex(self._session_key(user_id), timedelta(minutes=self.timeout_minutes), json.dumps(session))
        return session

    def update_session(self, user_id, state=None, data=None):
        session = self.get_session(user_id)
        if state is not None:
            session["state"] = state
        if data is not None:
            session["data"] = data
        session["last_activity"] = datetime.now().isoformat()
        self.redis.setex(self._session_key(user_id), timedelta(minutes=self.timeout_minutes), json.dumps(session))

    def clear_session(self, user_id):
        self.redis.delete(self._session_key(user_id))

    def cleanup_expired_sessions(self):
        # Redis handles expiration automatically
        return 0

    def get_stats(self):
        # Scan all session keys and count them
        try:
            count = 0
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor=cursor, match="session:*", count=100)
                count += len(keys)
                if cursor == 0:
                    break
            return {
                "total_sessions": count,
                "timeout_minutes": self.timeout_minutes
            }
        except Exception as e:
            return {
                "total_sessions": 0,
                "timeout_minutes": self.timeout_minutes,
                "error": str(e)
            }
