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
        # Not as straightforward with Redis; you can scan keys if needed
        pass
