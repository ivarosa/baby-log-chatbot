from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading
import time
import logging

class SessionManager:
    """Manage user sessions with automatic cleanup"""
    
    def __init__(self, timeout_minutes: int = 30):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.timeout_minutes = timeout_minutes
        self.lock = threading.RLock()
        self._start_cleanup_thread()
    
    def get_session(self, user_id: str) -> Dict[str, Any]:
        """Get or create user session"""
        with self.lock:
            if user_id not in self.sessions:
                self.sessions[user_id] = {
                    "state": None,
                    "data": {},
                    "last_activity": datetime.now(),
                    "created_at": datetime.now()
                }
            else:
                # Update last activity
                self.sessions[user_id]["last_activity"] = datetime.now()
            
            return self.sessions[user_id]
    
    def update_session(self, user_id: str, state: Optional[str] = None, 
                      data: Optional[Dict] = None) -> None:
        """Update session state and/or data"""
        with self.lock:
            session = self.get_session(user_id)
            if state is not None:
                session["state"] = state
            if data is not None:
                session["data"] = data
            session["last_activity"] = datetime.now()
    
    def clear_session(self, user_id: str) -> None:
        """Clear specific user session"""
        with self.lock:
            if user_id in self.sessions:
                del self.sessions[user_id]
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions, returns count of removed sessions"""
        with self.lock:
            current_time = datetime.now()
            expired_users = []
            
            for user_id, session in self.sessions.items():
                if current_time - session["last_activity"] > timedelta(minutes=self.timeout_minutes):
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                del self.sessions[user_id]
                logging.info(f"Cleaned up expired session for user: {user_id}")
            
            return len(expired_users)
    
    def _cleanup_worker(self):
        """Background thread for session cleanup"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                removed = self.cleanup_expired_sessions()
                if removed > 0:
                    logging.info(f"Session cleanup: removed {removed} expired sessions")
            except Exception as e:
                logging.error(f"Error in session cleanup: {e}")
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        cleanup_thread.start()
        logging.info("Session cleanup thread started")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        with self.lock:
            return {
                "total_sessions": len(self.sessions),
                "timeout_minutes": self.timeout_minutes,
                "sessions": {
                    user_id: {
                        "state": session["state"],
                        "last_activity": session["last_activity"].isoformat(),
                        "inactive_minutes": (datetime.now() - session["last_activity"]).seconds // 60
                    }
                    for user_id, session in self.sessions.items()
                }
            }

# Replace in main.py:
# OLD: user_sessions = {}
# NEW:
from session_manager import SessionManager
session_manager = SessionManager(timeout_minutes=30)

# Replace all occurrences:
# OLD: session = user_sessions.get(user, {"state": None, "data": {}})
# NEW:
session = session_manager.get_session(user)

# OLD: user_sessions[user] = session
# NEW:
session_manager.update_session(user, state=session["state"], data=session["data"])

# Add new endpoint for monitoring:
@app.get("/admin/sessions")
async def get_session_stats():
    """Admin endpoint to monitor sessions"""
    return session_manager.get_stats()
