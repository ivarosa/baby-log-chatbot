# utils/rate_limiter.py
"""
Rate limiting and cost tracking to prevent abuse and monitor expenses
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import defaultdict
import logging

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = defaultdict(list)  # {user: [timestamps]}
        self.limits = {
            'per_minute': 5,    # Max 5 messages per minute
            'per_hour': 20,     # Max 20 messages per hour
            'per_day': 100      # Max 100 messages per day
        }
        self.logger = logging.getLogger(__name__)
        self.blocked_users = {}  # {user: blocked_until}
    
    def check_limit(self, user: str) -> tuple[bool, Optional[str]]:
        """
        Check if user is within rate limits
        Returns: (allowed, error_message)
        """
        now = datetime.now()
        
        # Check if user is blocked
        if user in self.blocked_users:
            blocked_until = self.blocked_users[user]
            if now < blocked_until:
                remaining = (blocked_until - now).seconds
                return False, f"⏳ Anda diblokir sementara. Coba lagi dalam {remaining} detik."
            else:
                del self.blocked_users[user]
        
        # Clean old timestamps
        self._cleanup_old_requests(user)
        
        # Get recent requests
        user_requests = self.requests[user]
        
        # Check per-minute limit
        recent_minute = [ts for ts in user_requests if (now - ts).seconds < 60]
        if len(recent_minute) >= self.limits['per_minute']:
            self.logger.warning(f"Rate limit exceeded (per minute): {user}")
            return False, "⏳ Terlalu cepat! Tunggu sebentar sebelum mengirim pesan lagi."
        
        # Check per-hour limit
        recent_hour = [ts for ts in user_requests if (now - ts).seconds < 3600]
        if len(recent_hour) >= self.limits['per_hour']:
            self.logger.warning(f"Rate limit exceeded (per hour): {user}")
            # Block for 10 minutes
            self.blocked_users[user] = now + timedelta(minutes=10)
            return False, "⏳ Batas pesan per jam tercapai. Coba lagi dalam 10 menit."
        
        # Check per-day limit
        recent_day = [ts for ts in user_requests if (now - ts).seconds < 86400]
        if len(recent_day) >= self.limits['per_day']:
            self.logger.warning(f"Rate limit exceeded (per day): {user}")
            # Block until midnight
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            self.blocked_users[user] = tomorrow
            return False, "⏳ Batas pesan harian tercapai. Coba lagi besok."
        
        # All checks passed
        user_requests.append(now)
        return True, None
    
    def _cleanup_old_requests(self, user: str):
        """Remove requests older than 24 hours"""
        cutoff = datetime.now() - timedelta(days=1)
        self.requests[user] = [
            ts for ts in self.requests[user]
            if ts > cutoff
        ]
    
    def get_user_stats(self, user: str) -> Dict:
        """Get user's current usage stats"""
        now = datetime.now()
        user_requests = self.requests.get(user, [])
        
        minute_count = len([ts for ts in user_requests if (now - ts).seconds < 60])
        hour_count = len([ts for ts in user_requests if (now - ts).seconds < 3600])
        day_count = len([ts for ts in user_requests if (now - ts).seconds < 86400])
        
        return {
            'last_minute': f"{minute_count}/{self.limits['per_minute']}",
            'last_hour': f"{hour_count}/{self.limits['per_hour']}",
            'today': f"{day_count}/{self.limits['per_day']}",
            'is_blocked': user in self.blocked_users
        }


class CostTracker:
    """Track and estimate Twilio costs"""
    
    def __init__(self):
        self.message_log = defaultdict(list)  # {user: [timestamps]}
        self.cost_per_message = 0.005  # $0.005 per Twilio message
        self.logger = logging.getLogger(__name__)
    
    def log_message(self, user: str, message_type: str = "outbound"):
        """Log a sent message"""
        self.message_log[user].append({
            'timestamp': datetime.now(),
            'type': message_type
        })
    
    def get_daily_count(self, user: Optional[str] = None) -> int:
        """Get message count for today"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        
        if user:
            # Single user count
            user_messages = self.message_log.get(user, [])
            return len([m for m in user_messages if m['timestamp'] >= today_start])
        else:
            # All users count
            total = 0
            for user_messages in self.message_log.values():
                total += len([m for m in user_messages if m['timestamp'] >= today_start])
            return total
    
    def get_monthly_count(self, user: Optional[str] = None) -> int:
        """Get message count for this month"""
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        if user:
            user_messages = self.message_log.get(user, [])
            return len([m for m in user_messages if m['timestamp'] >= month_start])
        else:
            total = 0
            for user_messages in self.message_log.values():
                total += len([m for m in user_messages if m['timestamp'] >= month_start])
            return total
    
    def estimate_monthly_cost(self) -> Dict:
        """Estimate monthly Twilio cost"""
        # Get current month stats
        messages_this_month = self.get_monthly_count()
        days_elapsed = datetime.now().day
        
        # Project to end of month
        days_in_month = 30  # approximate
        projected_messages = (messages_this_month / days_elapsed) * days_in_month
        projected_cost = projected_messages * self.cost_per_message
        
        return {
            'messages_sent_this_month': messages_this_month,
            'projected_monthly_messages': int(projected_messages),
            'current_cost': f"${messages_this_month * self.cost_per_message:.2f}",
            'projected_monthly_cost': f"${projected_cost:.2f}",
            'average_per_day': int(messages_this_month / days_elapsed),
            'days_elapsed': days_elapsed
        }
    
    def get_top_users(self, limit: int = 10) -> list:
        """Get users with highest message counts"""
        user_counts = []
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        for user, messages in self.message_log.items():
            count = len([m for m in messages if m['timestamp'] >= month_start])
            user_counts.append({
                'user': user[-10:],  # Last 10 chars for privacy
                'message_count': count,
                'estimated_cost': f"${count * self.cost_per_message:.2f}"
            })
        
        return sorted(user_counts, key=lambda x: x['message_count'], reverse=True)[:limit]
    
    def check_cost_alert(self, monthly_budget: float = 100.0) -> Optional[Dict]:
        """Check if costs are approaching budget"""
        estimate = self.estimate_monthly_cost()
        projected_cost = float(estimate['projected_monthly_cost'].replace('$', ''))
        current_cost = float(estimate['current_cost'].replace('$', ''))
        
        alerts = []
        
        # Warning at 70% of budget
        if current_cost > monthly_budget * 0.7:
            alerts.append({
                'level': 'warning',
                'message': f"⚠️ Biaya sudah mencapai 70% dari budget (${current_cost:.2f}/${monthly_budget:.2f})"
            })
        
        # Critical at 90% of budget
        if current_cost > monthly_budget * 0.9:
            alerts.append({
                'level': 'critical',
                'message': f"🚨 Biaya sudah mencapai 90% dari budget! (${current_cost:.2f}/${monthly_budget:.2f})"
            })
        
        # Projection alert
        if projected_cost > monthly_budget * 1.2:
            alerts.append({
                'level': 'warning',
                'message': f"📊 Proyeksi biaya melebihi budget (${projected_cost:.2f}/${monthly_budget:.2f})"
            })
        
        return alerts if alerts else None


class SmartThrottler:
    """Intelligent message throttling based on usage patterns"""
    
    def __init__(self):
        self.user_patterns = defaultdict(list)  # {user: [message_types]}
    
    def should_send_message(self, user: str, message_type: str) -> bool:
        """Decide if message should be sent based on recent patterns"""
        recent_messages = self.user_patterns[user][-10:]  # Last 10 messages
        
        # Don't send duplicate confirmations
        if message_type == "confirmation" and recent_messages.count("confirmation") >= 2:
            return False
        
        # Don't send help text if sent recently
        if message_type == "help" and "help" in recent_messages[-3:]:
            return False
        
        # Don't send reminder if similar reminder sent recently
        if message_type == "reminder" and "reminder" in recent_messages[-2:]:
            return False
        
        # Log this message type
        self.user_patterns[user].append(message_type)
        return True


# Integration example for main.py
"""
# Initialize at startup
rate_limiter = RateLimiter()
cost_tracker = CostTracker()
throttler = SmartThrottler()

@app.post("/webhook")
async def webhook(request: Request):
    user = form.get("From")
    message = form.get("Body")
    
    # 1. Check rate limit
    allowed, error_msg = rate_limiter.check_limit(user)
    if not allowed:
        resp = MessagingResponse()
        resp.message(error_msg)
        return Response(str(resp), media_type="application/xml")
    
    # 2. Process message
    response = await process_message(user, message)
    
    # 3. Smart throttling
    if throttler.should_send_message(user, "confirmation"):
        # 4. Log for cost tracking
        cost_tracker.log_message(user)
        
        return response
    else:
        # Skip sending to save cost
        logger.info(f"Throttled message to {user}")
        return Response("", status_code=200)


@app.get("/admin/costs")
async def get_cost_stats():
    return {
        'daily_messages': cost_tracker.get_daily_count(),
        'monthly_estimate': cost_tracker.estimate_monthly_cost(),
        'top_users': cost_tracker.get_top_users(),
        'cost_alerts': cost_tracker.check_cost_alert(monthly_budget=100.0)
    }


@app.get("/admin/user/{user}/stats")
async def get_user_stats(user: str):
    return {
        'rate_limits': rate_limiter.get_user_stats(user),
        'daily_messages': cost_tracker.get_daily_count(user),
        'monthly_messages': cost_tracker.get_monthly_count(user)
    }
"""
