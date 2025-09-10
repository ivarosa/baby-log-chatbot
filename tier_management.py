# tier_management.py
"""
User tier and subscription management
Extracted from main.py for better organization
"""
import os
import logging
from datetime import datetime, date
from typing import Dict, Any
from database_pool import DatabasePool
from database_security import DatabaseSecurity
from error_handler import ErrorHandler

# Initialize the singleton pool
db_pool = DatabasePool()

@ErrorHandler.handle_database_error
def get_user_tier(user: str) -> Dict[str, Any]:
    """Get user tier information with automatic daily reset"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('user_tiers')
    
    try:
        with db_pool.get_connection() as conn:
            c = conn.cursor()
            
            if database_url:
                c.execute(f'SELECT tier, messages_today, last_reset FROM {table_name} WHERE {user_col}=%s', (user,))
            else:
                c.execute(f'SELECT tier, messages_today, last_reset FROM {table_name} WHERE {user_col}=?', (user,))
            
            row = c.fetchone()
            
            if not row:
                # Insert new user
                if database_url:
                    c.execute(f'''
                        INSERT INTO {table_name} ({user_col}, tier, messages_today, last_reset) 
                        VALUES (%s, %s, %s, %s)
                    ''', (user, 'free', 0, date.today()))
                else:
                    c.execute(f'''
                        INSERT INTO {table_name} ({user_col}, tier, messages_today, last_reset) 
                        VALUES (?, ?, ?, ?)
                    ''', (user, 'free', 0, date.today()))
                result = {'tier': 'free', 'messages_today': 0}
            else:
                # Check if need to reset daily count
                if isinstance(row, dict):  # PostgreSQL
                    last_reset = row['last_reset']
                    tier = row['tier']
                    messages_today = row['messages_today']
                else:  # SQLite
                    last_reset = row[2]
                    tier = row[0]
                    messages_today = row[1]
                
                if last_reset != date.today():
                    # Reset daily count
                    if database_url:
                        c.execute(f'''
                            UPDATE {table_name} 
                            SET messages_today=0, last_reset=%s 
                            WHERE {user_col}=%s
                        ''', (date.today(), user))
                    else:
                        c.execute(f'''
                            UPDATE {table_name} 
                            SET messages_today=0, last_reset=? 
                            WHERE {user_col}=?
                        ''', (date.today(), user))
                    result = {'tier': tier, 'messages_today': 0}
                else:
                    result = {'tier': tier, 'messages_today': messages_today}
        
        return result
    except Exception as e:
        logging.error(f"Error getting user tier: {e}")
        return {'tier': 'free', 'messages_today': 0}

@ErrorHandler.handle_database_error
def check_subscription_status(user: str) -> Dict[str, Any]:
    """Check if user has an active premium subscription"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    subscription_table = DatabaseSecurity.validate_table_name('user_subscriptions')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        
        # Check user_subscriptions table for active subscription
        if database_url:
            c.execute(f'''
                SELECT subscription_tier, subscription_end 
                FROM {subscription_table} 
                WHERE {user_col}=%s
            ''', (user,))
        else:
            c.execute(f'''
                SELECT subscription_tier, subscription_end 
                FROM {subscription_table} 
                WHERE {user_col}=?
            ''', (user,))
        
        subscription = c.fetchone()
        
        if subscription:
            # Check if subscription is valid
            if isinstance(subscription, dict):  # PostgreSQL
                tier = subscription['subscription_tier'] 
                end_date = subscription['subscription_end']
            else:  # SQLite
                tier = subscription[0]
                end_date = subscription[1]
                
            if tier == 'premium' and end_date and end_date > datetime.now():
                # Valid premium subscription
                return {'tier': 'premium', 'valid_until': end_date, 'messages_today': 0}
    
    # If no valid subscription found, fall back to user_tiers table
    return get_user_tier(user)

def get_tier_limits(user: str) -> Dict[str, Any]:
    """Get tier-based feature limits for user"""
    user_info = check_subscription_status(user)
    
    if user_info['tier'] == 'premium':
        return {
            "history_days": None,      # Unlimited
            "growth_entries": None,    # Unlimited
            "active_reminders": None,  # Unlimited
            "children_count": 5,       # Up to 5 children
            "mpasi_entries": None,     # Unlimited
            "pumping_entries": None,   # Unlimited
            "sleep_record": None,      # Unlimited
            "pdf_reports": True,       # PDF export allowed
            "advanced_analytics": True # Advanced features
        }
    else:  # Free tier
        return {
            "history_days": 7,         # Last 7 days only
            "growth_entries": 10,      # Last 10 entries
            "active_reminders": 3,     # Max 3 active reminders
            "children_count": 1,       # Single child only
            "mpasi_entries": 10,       # Last 10 entries
            "pumping_entries": 10,     # Last 10 entries
            "sleep_record": 10,        # Max 10 sleep records
            "pdf_reports": False,      # No PDF export
            "advanced_analytics": False # Basic features only
        }

def can_access_feature(user: str, feature_name: str) -> bool:
    """Check if user can access a specific feature based on their subscription"""
    user_info = check_subscription_status(user)
    
    # Free features - available to everyone
    free_features = [
        "basic_tracking",
        "limited_history", 
        "basic_reminders",
        "simple_summary",
        "child_data",
        "basic_analytics"
    ]
    
    # Premium features - require subscription
    premium_features = [
        "unlimited_history",
        "unlimited_reminders", 
        "weekly_trends",
        "monthly_reports",
        "growth_percentiles",
        "data_export",
        "family_sharing",
        "multiple_children",
        "detailed_analytics",
        "custom_reminders",
        "priority_support",
        "pdf_reports",
        "advanced_charts"
    ]
    
    if feature_name in free_features:
        return True
    
    if feature_name in premium_features:
        return user_info['tier'] == 'premium'
    
    # If feature not explicitly categorized, default to available
    return True

@ErrorHandler.handle_database_error
def increment_message_count(user: str) -> None:
    """Increment daily message count for user"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('user_tiers')
    
    try:
        with db_pool.get_connection() as conn:
            c = conn.cursor()
            if database_url:
                c.execute(f'UPDATE {table_name} SET messages_today = messages_today + 1 WHERE {user_col}=%s', (user,))
            else:
                c.execute(f'UPDATE {table_name} SET messages_today = messages_today + 1 WHERE {user_col}=?', (user,))
    except Exception as e:
        logging.error(f"Error incrementing message count: {e}")

def can_send_reminder(user: str) -> bool:
    """Check if user can receive more reminders today"""
    user_info = get_user_tier(user)
    if user_info['tier'] == 'premium':
        return True
    else:
        return user_info['messages_today'] < 2  # Free tier limit

def get_usage_summary(user: str) -> Dict[str, Any]:
    """Get user's current usage summary"""
    user_info = check_subscription_status(user)
    limits = get_tier_limits(user)
    
    # Get current counts (this would require additional database queries)
    # For now, return basic structure
    return {
        "tier": user_info['tier'],
        "messages_today": user_info.get('messages_today', 0),
        "limits": limits,
        "usage": {
            "reminders_sent_today": user_info.get('messages_today', 0),
            "max_daily_reminders": 2 if user_info['tier'] == 'free' else 'unlimited'
        }
    }

def format_tier_status_message(user: str) -> str:
    """Format tier status message for user"""
    usage = get_usage_summary(user)
    tier = usage['tier']
    
    if tier == 'premium':
        return (
            f"💎 **Status: Premium User**\n\n"
            f"✅ Akses unlimited ke semua fitur\n"
            f"✅ Riwayat data tak terbatas\n"
            f"✅ Pengingat tak terbatas\n"
            f"✅ Export PDF laporan\n"
            f"✅ Analitik lanjutan"
        )
    else:
        limits = usage['limits']
        messages_left = 2 - usage['usage']['reminders_sent_today']
        
        return (
            f"🆓 **Status: Free User**\n\n"
            f"📊 Pengingat hari ini: {usage['usage']['reminders_sent_today']}/2\n"
            f"📅 Riwayat data: {limits['history_days']} hari terakhir\n"
            f"📈 Catatan pertumbuhan: {limits['growth_entries']} terakhir\n"
            f"⏰ Pengingat aktif: maksimal {limits['active_reminders']}\n\n"
            f"💡 Upgrade ke premium untuk akses unlimited!"
        )

# Subscription management functions
@ErrorHandler.handle_database_error
def create_subscription(user: str, tier: str, duration_days: int, payment_reference: str = None) -> bool:
    """Create or update user subscription"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('user_subscriptions')
    
    start_date = datetime.now()
    end_date = start_date + timedelta(days=duration_days)
    
    try:
        with db_pool.get_connection() as conn:
            c = conn.cursor()
            
            # Check if user already has subscription
            if database_url:
                c.execute(f'SELECT id FROM {table_name} WHERE {user_col}=%s', (user,))
            else:
                c.execute(f'SELECT id FROM {table_name} WHERE {user_col}=?', (user,))
            
            existing = c.fetchone()
            
            if existing:
                # Update existing subscription
                if database_url:
                    c.execute(f'''
                        UPDATE {table_name} 
                        SET subscription_tier=%s, subscription_start=%s, subscription_end=%s, 
                            payment_reference=%s, updated_at=%s
                        WHERE {user_col}=%s
                    ''', (tier, start_date, end_date, payment_reference, datetime.now(), user))
                else:
                    c.execute(f'''
                        UPDATE {table_name} 
                        SET subscription_tier=?, subscription_start=?, subscription_end=?, 
                            payment_reference=?, updated_at=?
                        WHERE {user_col}=?
                    ''', (tier, start_date, end_date, payment_reference, datetime.now(), user))
            else:
                # Create new subscription
                if database_url:
                    c.execute(f'''
                        INSERT INTO {table_name} 
                        ({user_col}, subscription_tier, subscription_start, subscription_end, payment_reference)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (user, tier, start_date, end_date, payment_reference))
                else:
                    c.execute(f'''
                        INSERT INTO {table_name} 
                        ({user_col}, subscription_tier, subscription_start, subscription_end, payment_reference)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user, tier, start_date, end_date, payment_reference))
            
            return True
    except Exception as e:
        logging.error(f"Error creating subscription: {e}")
        return False
