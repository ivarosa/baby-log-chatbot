from datetime import datetime, timedelta
import pytz
from typing import Optional

class TimezoneHandler:
    """Centralized timezone management"""
    
    # Define timezone based on user location
    DEFAULT_TZ = pytz.timezone('Asia/Jakarta')  # GMT+7
    
    @staticmethod
    def get_user_timezone(user_phone: str) -> pytz.timezone:
        """Get user's timezone (could be extended to store per-user preferences)"""
        # For now, return default. Later can query user preferences
        return TimezoneHandler.DEFAULT_TZ
    
    @staticmethod
    def now_local(user_phone: str) -> datetime:
        """Get current time in user's timezone"""
        tz = TimezoneHandler.get_user_timezone(user_phone)
        return datetime.now(tz)
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC time"""
        return datetime.now(pytz.UTC)
    
    @staticmethod
    def to_utc(dt: datetime, user_phone: str) -> datetime:
        """Convert user's local time to UTC"""
        if dt.tzinfo is None:
            # Assume it's in user's timezone if naive
            tz = TimezoneHandler.get_user_timezone(user_phone)
            dt = tz.localize(dt)
        return dt.astimezone(pytz.UTC)
    
    @staticmethod
    def to_local(dt: datetime, user_phone: str) -> datetime:
        """Convert UTC to user's local time"""
        if dt.tzinfo is None:
            # Assume it's UTC if naive
            dt = pytz.UTC.localize(dt)
        tz = TimezoneHandler.get_user_timezone(user_phone)
        return dt.astimezone(tz)
    
    @staticmethod
    def parse_user_date_time(date_str: str, time_str: str, user_phone: str) -> datetime:
        """Parse user-provided date and time in their timezone"""
        tz = TimezoneHandler.get_user_timezone(user_phone)
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return tz.localize(dt)
    
    @staticmethod
    def format_for_user(dt: datetime, user_phone: str, include_time: bool = True) -> str:
        """Format datetime for user display"""
        local_dt = TimezoneHandler.to_local(dt, user_phone)
        if include_time:
            return local_dt.strftime("%Y-%m-%d %H:%M")
        return local_dt.strftime("%Y-%m-%d")
