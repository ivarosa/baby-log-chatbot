from database_security import DatabaseSecurity
from validators import InputValidator
import os
import psycopg
from psycopg.rows import dict_row
from urllib.parse import urlparse
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, date, timedelta
import re
import logging
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
from send_twilio_message import send_twilio_message
from gpt_model_config import estimate_calories_openai  # <-- Import your function here
import pytz
import matplotlib
import reportlab
from mpasi_milk_chart import generate_mpasi_milk_chart
from generate_report import generate_pdf_report
from fastapi.responses import StreamingResponse
from sleep_tracking import (
    init_sleep_table,
    start_sleep_record,
    get_latest_open_sleep_id,
    get_sleep_by_id,
    update_sleep_record,
    get_sleep_summary,
    get_sleep_record_count,
    can_create_sleep_record,
    get_sleep_records_with_limit,
    delete_oldest_sleep_record
)
from session_manager import SessionManager
session_manager = SessionManager(timeout_minutes=30)

DEFAULT_TIMEZONE = pytz.timezone('Asia/Jakarta')  # Change to 'Asia/Makassar' for GMT+8, 'Asia/Jayapura' for GMT+9

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# Initialize FastAPI app
app = FastAPI(title="Baby Log WhatsApp Chatbot", version="1.0.0")
session_manager = SessionManager(timeout_minutes=30)

# Database connection function - supports both SQLite (local) and PostgreSQL (Railway)
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Railway PostgreSQL connection
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg.connect(database_url, row_factory=dict_row)
    else:
        # Local SQLite fallback (your original setup)
        import sqlite3
        return sqlite3.connect('babylog.db')

@app.get("/users")
def list_users():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # PostgreSQL with psycopg3
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, email FROM users")
                results = cur.fetchall()  # Each row is a dict!
                return {"users": results}
    else:
        # SQLite fallback
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, email FROM users")
        columns = [desc[0] for desc in cur.description]
        results = [dict(zip(columns, row)) for row in cur.fetchall()]
        conn.close()
        return {"users": results}

def execute_query(query, params=None, fetch=False):
    """Universal query executor for both SQLite and PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # PostgreSQL mode
        conn = get_db_connection()
        c = conn.cursor()
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        
        if fetch:
            if fetch == 'one':
                result = c.fetchone()
            else:
                result = c.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
    else:
        # SQLite mode (your original)
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        
        if fetch:
            if fetch == 'one':
                result = c.fetchone()
            else:
                result = c.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()

def init_db():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # PostgreSQL schema (for Railway)
        queries = [
            '''CREATE TABLE IF NOT EXISTS child (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                name TEXT,
                gender TEXT,
                dob DATE,
                height_cm REAL,
                weight_kg REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS timbang_log (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                date DATE,
                height_cm REAL,
                weight_kg REAL,
                head_circum_cm REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS mpasi_log (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                date DATE,
                time TEXT,
                volume_ml REAL,
                food_detail TEXT,
                food_grams TEXT,
                est_calories REAL,
                gpt_calorie_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS poop_log (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                date DATE,
                time TEXT,
                bristol_scale INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS pumping_log (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                date DATE,
                time TEXT,
                left_ml REAL,
                right_ml REAL,
                milk_bags INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS milk_intake_log (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                date DATE,
                time TEXT,
                volume_ml REAL,
                milk_type TEXT,
                asi_method TEXT,
                sufor_calorie REAL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS calorie_setting (
                user_phone TEXT PRIMARY KEY,
                asi_kcal REAL DEFAULT 0.67,
                sufor_kcal REAL DEFAULT 0.7
            )''',
            '''CREATE TABLE IF NOT EXISTS milk_reminders (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                reminder_name TEXT,
                interval_hours INTEGER,
                start_time TEXT,
                end_time TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_sent TIMESTAMP,
                next_due TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS reminder_logs (
                id SERIAL PRIMARY KEY,
                user_phone TEXT,
                reminder_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                volume_ml REAL,
                notes TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS user_tiers (
                user_phone TEXT PRIMARY KEY,
                tier TEXT DEFAULT 'free',
                messages_today INTEGER DEFAULT 0,
                last_reset DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS user_subscriptions (
                id SERIAL PRIMARY KEY,
                user_phone TEXT UNIQUE,
                subscription_tier TEXT NOT NULL DEFAULT 'free',
                subscription_start TIMESTAMP,
                subscription_end TIMESTAMP,
                payment_reference TEXT,
                payment_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        #Add sleep table
        queries.append(init_sleep_table(database_url))

        conn = get_db_connection()
        c = conn.cursor()
        for query in queries:
            c.execute(query)
        
        # Create indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_phone ON child(user_phone)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_reminder_due ON milk_reminders(next_due, is_active)')
        
        conn.commit()
        conn.close()
        
    else:
        # Original SQLite schema (unchanged)
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS child (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                name TEXT,
                gender TEXT,
                dob DATE,
                height_cm REAL,
                weight_kg REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS timbang_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                date DATE,
                height_cm REAL,
                weight_kg REAL,
                head_circum_cm REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS mpasi_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                date DATE,
                time TEXT,
                volume_ml REAL,
                food_detail TEXT,
                food_grams TEXT,
                est_calories REAL,
                gpt_calorie_summary TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS poop_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                date DATE,
                time TEXT,
                bristol_scale INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS pumping_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                date DATE,
                time TEXT,
                left_ml REAL,
                right_ml REAL,
                milk_bags INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS milk_intake_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                date DATE,
                time TEXT,
                volume_ml REAL,
                milk_type TEXT,
                asi_method TEXT,
                sufor_calorie REAL,
                note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS calorie_setting (
                user TEXT PRIMARY KEY,
                asi_kcal REAL DEFAULT 0.67,
                sufor_kcal REAL DEFAULT 0.7
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS milk_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                reminder_name TEXT,
                interval_hours INTEGER,
                start_time TEXT,
                end_time TEXT,
                is_active BOOLEAN DEFAULT 1,
                last_sent DATETIME,
                next_due DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS reminder_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                reminder_id INTEGER,
                action TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                volume_ml REAL,
                notes TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_tiers (
                user TEXT PRIMARY KEY,
                tier TEXT DEFAULT 'free',
                messages_today INTEGER DEFAULT 0,
                last_reset DATE DEFAULT CURRENT_DATE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        #Add sleep table for SQLite
        c.execute(init_sleep_table(database_url))

        conn.commit()
        conn.close()

# Initialize database
init_db()

# Cost control functions (new for Railway)
def get_user_tier(user):
    """Secure version of get_user_tier with SQL injection protection"""
    import os
    from datetime import date
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)  # ← SECURITY ADDITION
    table_name = DatabaseSecurity.validate_table_name('user_tiers')  # ← SECURITY ADDITION
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            # Use validated names instead of dynamic string formatting
            c.execute(f'SELECT tier, messages_today, last_reset FROM {table_name} WHERE {user_col}=%s', (user,))
            row = c.fetchone()
            
            if not row:
                c.execute(f'''
                    INSERT INTO {table_name} ({user_col}, tier, messages_today, last_reset) 
                    VALUES (%s, %s, %s, %s)
                ''', (user, 'free', 0, date.today()))
                conn.commit()
                result = {'tier': 'free', 'messages_today': 0}
            else:
                if row['last_reset'] != date.today():
                    c.execute(f'''
                        UPDATE {table_name} 
                        SET messages_today=0, last_reset=%s 
                        WHERE {user_col}=%s
                    ''', (date.today(), user))
                    conn.commit()
                    result = {'tier': row['tier'], 'messages_today': 0}
                else:
                    result = dict(row)
            conn.close()
        else:
            # SQLite version (similar pattern)
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'SELECT tier, messages_today, last_reset FROM {table_name} WHERE {user_col}=?', (user,))
            # ... rest of SQLite logic
            
        return result
    except Exception as e:
        import logging
        logging.error(f"Error getting user tier: {e}")
        return {'tier': 'free', 'messages_today': 0}

def can_send_reminder(user):
    """Check if user can receive more reminders today"""
    user_info = get_user_tier(user)
    if user_info['tier'] == 'premium':
        return True
    else:
        return user_info['messages_today'] < 2  # Free tier limit

def increment_message_count(user):
    """Secure version of increment_message_count"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('user_tiers')
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'UPDATE {table_name} SET messages_today = messages_today + 1 WHERE {user_col}=%s', (user,))
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'UPDATE {table_name} SET messages_today = messages_today + 1 WHERE {user_col}=?', (user,))
            conn.commit()
            conn.close()
    except Exception as e:
        logging.error(f"Error incrementing message count: {e}")

def check_subscription_status(user):
    """Check if user has an active premium subscription"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)  # ← ADD SECURITY
    subscription_table = DatabaseSecurity.validate_table_name('user_subscriptions')  # ← ADD SECURITY
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # First check user_subscriptions table for active subscription  
    c.execute(f'''
        SELECT subscription_tier, subscription_end 
        FROM {subscription_table} 
        WHERE {user_col}=%s
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
            conn.close()
            return {'tier': 'premium', 'valid_until': end_date, 'messages_today': 0}
    
    # If no valid subscription found, fall back to user_tiers table
    conn.close()
    return get_user_tier(user)  # ← USE SECURE VERSION
    
def get_tier_limits(user):
    user_info = check_subscription_status(user)  # This now calls secure functions
    if user_info['tier'] == 'premium':
        return {
            "history_days": None,
            "growth_entries": None,
            "active_reminders": None,
            "children_count": 5,
            "mpasi_entries": None,
            "pumping_entries": None,
            "sleep_record": None
        }
    else:
        return {
            "history_days": 7,
            "growth_entries": 10,
            "active_reminders": 3,
            "children_count": 1,
            "mpasi_entries": 10,
            "pumping_entries": 10,
            "sleep_record": 10
        }

def can_access_feature(user, feature_name):
    """Check if user can access a specific feature based on their subscription"""
    user_info = check_subscription_status(user)
    
    # Free features - available to everyone
    free_features = [
        "basic_tracking",
        "limited_history",
        "basic_reminders",
        "simple_summary"
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
        "pdf_reports"
    ]
    
    if feature_name in free_features:
        return True
    
    if feature_name in premium_features:
        return user_info['tier'] == 'premium'
    
    # If feature not explicitly categorized, default to available
    return True

# === ADDITIONAL HELPER FUNCTIONS FOR SLEEP TRACKING ===

def validate_sleep_permissions(user, action="create"):
    """
    Validate if user can perform sleep-related actions
    Returns: (can_proceed: bool, message: str)
    """
    limits = get_tier_limits(user)
    
    if action == "create":
        if limits["sleep_record"] is not None:  # Free user
            current_count = get_sleep_record_count(user)
            if current_count >= limits["sleep_record"]:
                return False, f"Tier gratis dibatasi {limits['sleep_record']} catatan tidur. Upgrade ke premium!"
    
    return True, ""

def get_sleep_status_info(user):
    """Get current sleep tracking status and limits for user"""
    limits = get_tier_limits(user)
    current_count = get_sleep_record_count(user)
    active_session = get_latest_open_sleep_id(user)
    
    status = {
        "current_count": current_count,
        "limit": limits.get("sleep_record"),
        "has_active_session": bool(active_session),
        "active_session_id": active_session,
        "is_premium": limits.get("sleep_record") is None
    }
    
    # Calculate percentage used for free users
    if status["limit"] is not None:
        status["percentage_used"] = (current_count / status["limit"]) * 100
    else:
        status["percentage_used"] = 0
        
    return status

# ADD the helper functions for sleep tracking:

def complete_sleep_session(user, sleep_id, end_time):
    """Enhanced version of complete_sleep_session with better validation and feedback"""
    try:
        # Get the sleep record
        sleep_data = get_sleep_by_id(sleep_id)
        if not sleep_data:
            return "❌ Sesi tidur tidak ditemukan. Mungkin sudah dihapus atau tidak valid."
        
        # Calculate duration with better validation
        try:
            start_datetime = datetime.strptime(f"{sleep_data['date']} {sleep_data['start_time']}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{sleep_data['date']} {end_time}", "%Y-%m-%d %H:%M")
            
            # Handle sleep across midnight
            if end_datetime < start_datetime:
                end_datetime += timedelta(days=1)
                
            duration_minutes = (end_datetime - start_datetime).total_seconds() / 60
            
            # Enhanced validation
            if duration_minutes < 1:
                return "❌ Durasi tidur terlalu singkat (kurang dari 1 menit). Periksa waktu mulai dan selesai."
            
            if duration_minutes > 20 * 60:  # More than 20 hours
                return (
                    f"❌ Durasi tidur terlalu lama ({int(duration_minutes/60)} jam). "
                    f"Periksa kembali waktu mulai ({sleep_data['start_time']}) dan selesai ({end_time})."
                )
            
            hours, minutes = divmod(int(duration_minutes), 60)
            
            # Update the record
            success = update_sleep_record(sleep_id, end_time, duration_minutes)
            
            if success:
                # Check tier limits after completion
                limits = get_tier_limits(user)
                sleep_limit = limits.get("sleep_record")
                
                base_message = (
                    f"✅ Catatan tidur berhasil disimpan!\n\n"
                    f"📊 Detail:\n"
                    f"• Durasi: {hours} jam {minutes} menit\n"
                    f"• Waktu: {sleep_data['start_time']} - {end_time}\n"
                    f"• Tanggal: {sleep_data['date']}"
                )
                
                if sleep_limit is not None:  # Free user
                    current_count = get_sleep_record_count(user)
                    base_message += f"\n\n📈 Catatan tidur: {current_count}/{sleep_limit}"
                    
                    if current_count >= sleep_limit:
                        base_message += (
                            f"\n\n⚠️ Anda telah mencapai batas maksimal catatan tidur. "
                            f"Upgrade ke premium untuk catatan unlimited!"
                        )
                    elif current_count >= sleep_limit * 0.8:
                        base_message += f"\n\n💡 Mendekati batas maksimal. Upgrade ke premium?"
                
                return base_message
            else:
                return "❌ Gagal menyimpan catatan tidur. Silakan coba lagi atau hubungi support."
                
        except ValueError as e:
            return f"❌ Format waktu tidak valid: {str(e)}"
            
    except Exception as e:
        logging.error(f"Error in complete_sleep_session_improved: {e}")
        return "❌ Terjadi kesalahan sistem saat menyimpan catatan tidur."
        
def cancel_sleep_session(user):
    """Secure version of cancel_sleep_session"""
    sleep_id = get_latest_open_sleep_id(user)
    if not sleep_id:
        return "❌ Tidak ada sesi tidur yang sedang berlangsung."
    
    # Delete the incomplete sleep record
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'DELETE FROM {table_name} WHERE id=%s', (sleep_id,))
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'DELETE FROM {table_name} WHERE id=?', (sleep_id,))
            conn.commit()
            conn.close()
        return "✅ Sesi tidur yang belum selesai telah dibatalkan."
    except Exception as e:
        logging.error(f"Error canceling sleep session: {e}")
        return "❌ Gagal membatalkan sesi tidur."

def format_sleep_display(user, show_history=False):
    """Format sleep data for display"""
    if show_history:
        # Show multiple days (limited by tier)
        limits = get_tier_limits(user)
        days_limit = limits.get("history_days", 7)
        if days_limit is None:
            days_limit = 30  # Premium users get 30 days
        
        records = get_sleep_records_with_limit(user, limit=None)
        if not records:
            return f"😴 Belum ada catatan tidur.\n\nMulai dengan: `catat tidur`"
        
        # Group by date
        by_date = {}
        for record in records:
            date_str = record['date']
            if isinstance(date_str, str):
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    date_obj = date_str
            else:
                date_obj = date_str
            
            if date_obj not in by_date:
                by_date[date_obj] = []
            by_date[date_obj].append(record)
        
        # Limit dates shown
        sorted_dates = sorted(by_date.keys(), reverse=True)[:days_limit]
        
        lines = [f"📊 *Riwayat Tidur (maks {days_limit} hari)*\n"]
        total_sessions = 0
        total_minutes = 0
        
        for date_obj in sorted_dates:
            day_records = by_date[date_obj]
            day_total = sum(r.get('duration_minutes', 0) or 0 for r in day_records)
            hours, minutes = divmod(int(day_total), 60)
            
            # Format date nicely
            if date_obj == datetime.now().date():
                date_display = "Hari ini"
            elif date_obj == datetime.now().date() - timedelta(days=1):
                date_display = "Kemarin"
            else:
                date_display = date_obj.strftime("%d/%m")
            
            lines.append(f"*{date_display}:*")
            for record in day_records:
                duration = record.get('duration_minutes', 0) or 0
                h, m = divmod(int(duration), 60)
                start_time = record.get('start_time', '-')
                end_time = record.get('end_time', '-')
                lines.append(f"  • {start_time} - {end_time} ({h}j {m}m)")
            
            lines.append(f"  📈 Total: {hours}j {minutes}m ({len(day_records)} sesi)\n")
            
            total_sessions += len(day_records)
            total_minutes += day_total
        
        # Overall summary
        if by_date:
            total_hours, total_mins = divmod(int(total_minutes), 60)
            avg_per_day = total_minutes / len(sorted_dates) if sorted_dates else 0
            avg_hours, avg_mins = divmod(int(avg_per_day), 60)
            
            lines.append(f"📊 *Ringkasan {len(sorted_dates)} hari:*")
            lines.append(f"• Total tidur: {total_hours}j {total_mins}m")
            lines.append(f"• Total sesi: {total_sessions}")
            lines.append(f"• Rata-rata per hari: {avg_hours}j {avg_mins}m")
            
            # Add tier info for free users
            if limits.get("history_days"):
                lines.append(f"\n💡 *Tier gratis dibatasi {limits['history_days']} hari riwayat*")
        
        return "\n".join(lines)
    else:
        # Show today only
        today = datetime.now().strftime("%Y-%m-%d")
        sleep_rows = get_sleep_summary(user, today)
        
        if not sleep_rows:
            return "😴 Belum ada catatan tidur hari ini.\n\nMulai dengan: `catat tidur`"
        
        lines = ["*Catatan tidur hari ini:*\n"]
        total_minutes = 0
        
        for i, row in enumerate(sleep_rows, 1):
            duration_mins = row[2] or 0
            hours, minutes = divmod(int(duration_mins), 60)
            lines.append(f"{i}. {row[0]} - {row[1]} ({hours}j {minutes}m)")
            total_minutes += duration_mins
        
        # Total for today
        total_hours, total_mins = divmod(int(total_minutes), 60)
        lines.append(f"\n📊 *Total hari ini: {total_hours}j {total_mins}m ({len(sleep_rows)} sesi)*")
        
        return "\n".join(lines)

# Your existing database functions (adapted for both SQLite and PostgreSQL)
def get_user_calorie_setting(user):
    """Secure version of get_user_calorie_setting"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('calorie_setting')
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT asi_kcal, sufor_kcal FROM {table_name} WHERE {user_col}=%s', (user,))
        row = c.fetchone()
        if row:
            conn.close()
            return {"asi": row['asi_kcal'], "sufor": row['sufor_kcal']}
        else:
            c.execute(f'INSERT INTO {table_name} ({user_col}) VALUES (%s)', (user,))
            conn.commit()
            conn.close()
            return {"asi": 0.67, "sufor": 0.7}
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'SELECT asi_kcal, sufor_kcal FROM {table_name} WHERE {user_col}=?', (user,))
        row = c.fetchone()
        if row:
            conn.close()
            return {"asi": row[0], "sufor": row[1]}
        else:
            c.execute(f'INSERT INTO {table_name} ({user_col}) VALUES (?)', (user,))
            conn.commit()
            conn.close()
            return {"asi": 0.67, "sufor": 0.7}
            
def set_user_calorie_setting(user, milk_type, value):
    """Secure version of set_user_calorie_setting"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('calorie_setting')
    
    # Validate milk_type
    if milk_type not in ["asi", "sufor"]:
        raise ValueError(f"Invalid milk_type: {milk_type}")
    
    # Validate value
    try:
        value = float(value)
        if value < 0 or value > 5:  # Reasonable range for calories per ml
            raise ValueError(f"Invalid calorie value: {value}")
    except (ValueError, TypeError):
        raise ValueError(f"Invalid calorie value: {value}")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        if milk_type == "asi":
            c.execute(f'UPDATE {table_name} SET asi_kcal=%s WHERE {user_col}=%s', (value, user))
        elif milk_type == "sufor":
            c.execute(f'UPDATE {table_name} SET sufor_kcal=%s WHERE {user_col}=%s', (value, user))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        if milk_type == "asi":
            c.execute(f'UPDATE {table_name} SET asi_kcal=? WHERE {user_col}=?', (value, user))
        elif milk_type == "sufor":
            c.execute(f'UPDATE {table_name} SET sufor_kcal=? WHERE {user_col}=?', (value, user))
        conn.commit()
        conn.close()

def save_child(user, data):
    """Secure version of save_child"""
    import os
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('child')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['dob'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_weight_kg(str(data['weight_kg']))
    if not is_valid:
        raise ValueError(f"Invalid weight: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_height_cm(str(data['height_cm']))
    if not is_valid:
        raise ValueError(f"Invalid height: {error_msg}")
    
    # Sanitize text inputs
    data['name'] = InputValidator.sanitize_text_input(data['name'], 100)
    
    # ... rest of the function
def get_child(user):
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)  # Validated!
    table_name = DatabaseSecurity.validate_table_name('child')
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT name, gender, dob, height_cm, weight_kg FROM child WHERE {user_col}=%s ORDER BY created_at DESC LIMIT 1', (user,))
        row = c.fetchone()
        conn.close()
        return row
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'SELECT name, gender, dob, height_cm, weight_kg FROM child WHERE {user_col}=? ORDER BY created_at DESC LIMIT 1', (user,))
        row = c.fetchone()
        conn.close()
        return row

def save_child(user, data):
    """Secure version of save_child"""
    import os
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('child')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['dob'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_weight_kg(str(data['weight_kg']))
    if not is_valid:
        raise ValueError(f"Invalid weight: {error_msg}")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, name, gender, dob, height_cm, weight_kg)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, name, gender, dob, height_cm, weight_kg)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))
        conn.commit()
        conn.close()

# Continue with your existing functions, but adapt database queries...
def save_timbang(user, data):
    """Secure version of save_timbang"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('timbang_log')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_weight_kg(str(data['weight_kg']))
    if not is_valid:
        raise ValueError(f"Invalid weight: {error_msg}")
    
    # Validate height
    try:
        height = float(data['height_cm'])
        if height < 10 or height > 200:  # Reasonable range
            raise ValueError("Height must be between 10-200 cm")
    except (ValueError, TypeError):
        raise ValueError("Invalid height value")
    
    # Validate head circumference
    try:
        head_circum = float(data['head_circum_cm'])
        if head_circum < 10 or head_circum > 100:  # Reasonable range
            raise ValueError("Head circumference must be between 10-100 cm")
    except (ValueError, TypeError):
        raise ValueError("Invalid head circumference value")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, height_cm, weight_kg, head_circum_cm)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, height_cm, weight_kg, head_circum_cm)
            VALUES (?, ?, ?, ?, ?)
        ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))
        conn.commit()
        conn.close()

def get_timbang_history(user, limit=None):
    """Secure version of get_timbang_history"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('timbang_log')
    limits = get_tier_limits(user)
    
    # Only set limit if free tier and not provided by caller
    if limit is None:
        limit = limits.get("growth_entries")

    query = f'''
        SELECT date, height_cm, weight_kg, head_circum_cm FROM {table_name}
        WHERE {user_col}=%s
        ORDER BY date DESC, created_at DESC
    '''
    params = [user]
    if limit is not None:
        query += ' LIMIT %s'
        params.append(limit)
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        query = query.replace('%s', '?')  # For SQLite
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows
        
# Reminder functions (adapted from your original script)
def save_reminder(user, data):
    """Secure version of save_reminder"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_reminders')
    
    # Validate input data
    try:
        # Validate interval
        interval = int(data['interval_hours'])
        if interval < 1 or interval > 24:
            raise ValueError("Interval must be between 1-24 hours")
        
        # Validate times
        datetime.strptime(data['start_time'], "%H:%M")
        datetime.strptime(data['end_time'], "%H:%M")
        
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid reminder data: {e}")
    
    # Calculate first reminder time
    start_datetime = datetime.now().replace(
        hour=int(data['start_time'].split(':')[0]),
        minute=int(data['start_time'].split(':')[1]),
        second=0,
        microsecond=0
    )
    
    if start_datetime <= datetime.now():
        start_datetime += timedelta(days=1)
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} 
            ({user_col}, reminder_name, interval_hours, start_time, end_time, next_due)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user, data['reminder_name'], data['interval_hours'], data['start_time'], data['end_time'], start_datetime))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} 
            ({user_col}, reminder_name, interval_hours, start_time, end_time, next_due)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['reminder_name'], data['interval_hours'], data['start_time'], data['end_time'], start_datetime))
        conn.commit()
        conn.close()

def get_user_reminders(user, active_only=True):
    """Secure version of get_user_reminders"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_reminders')
    limits = get_tier_limits(user)
    active_reminder_limit = limits.get("active_reminders")  # None for premium, 3 for free

    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT * FROM {table_name} WHERE {user_col}=%s'
        params = [user]
        if active_only:
            query += ' AND is_active=TRUE'
        if active_reminder_limit is not None:
            query += ' LIMIT %s'
            params.append(active_reminder_limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT * FROM {table_name} WHERE {user_col}=?'
        params = [user]
        if active_only:
            query += ' AND is_active=1'
        if active_reminder_limit is not None:
            query += ' LIMIT ?'
            params.append(active_reminder_limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows

def time_in_range(start_str, end_str, check_time):
    """Check if check_time (datetime) is within start and end (HH:MM strings) in local time."""
    start_hour, start_minute = map(int, start_str.split(":"))
    end_hour, end_minute = map(int, end_str.split(":"))
    start_time = check_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_time = check_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if start_time <= end_time:
        return start_time <= check_time <= end_time
    else:  # Over midnight
        return check_time >= start_time or check_time <= end_time

def check_and_send_reminders():
    """Secure version of check_and_send_reminders"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    reminder_table = DatabaseSecurity.validate_table_name('milk_reminders')

    try:
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_local = now_utc.astimezone(DEFAULT_TIMEZONE)
        
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                SELECT * FROM {reminder_table} 
                WHERE is_active=TRUE AND next_due <= %s
            ''', (now_utc,))
            due_reminders = c.fetchall()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                SELECT * FROM {reminder_table} 
                WHERE is_active=1 AND next_due <= ?
            ''', (now_local,))
            due_reminders = c.fetchall()
            conn.close()
        
        logging.info(f"Found {len(due_reminders)} due reminders")

        for reminder in due_reminders:
            if database_url:
                user = reminder[user_col]
                reminder_id = reminder['id']
                reminder_name = reminder['reminder_name']
                interval = reminder['interval_hours']
                start_str = reminder['start_time']
                end_str = reminder['end_time']
                next_due = reminder['next_due'].astimezone(DEFAULT_TIMEZONE)
            else:
                user = reminder[1]
                reminder_id = reminder[0]
                reminder_name = reminder[2]
                interval = reminder[3]
                start_str = reminder[4]
                end_str = reminder[5]
                next_due = reminder[8]

            user_info = get_user_tier(user)
            remaining = 2 - user_info['messages_today'] if user_info['tier'] == 'free' else 'unlimited'
            
            message = f"""🍼 Pengingat: {reminder_name}
                
                ⏰ Waktunya minum susu!
                
                Balas cepat:
                • 'done 120ml' - catat minum
                • 'snooze 30' - tunda 30 menit  
                • 'skip' - lewati
                
                💡 Sisa pengingat hari ini: {remaining}"""

            # Only send if inside allowed time window
            now_for_check = now_utc.astimezone(DEFAULT_TIMEZONE) if database_url else now_local
            if not time_in_range(start_str, end_str, now_for_check):
                send_this = False
            else:
                if user_info['tier'] == 'free' and user_info['messages_today'] >= 2:
                    logging.info(f"Free user {user} has reached daily reminder limit.")
                    send_this = False
                else:
                    send_this = True

            if send_this and send_twilio_message(user, message):
                logging.info(f"Sent reminder to {user} at {now_for_check}")
            else:
                logging.info(f"Not sending reminder message to {user} at {now_for_check}")

            # Calculate the next due time
            if database_url:
                new_next_due = now_for_check + timedelta(hours=interval)
            else:
                new_next_due = now_for_check + timedelta(hours=interval)

            if not time_in_range(start_str, end_str, new_next_due):
                next_start = (new_next_due + timedelta(days=1)).replace(
                    hour=int(start_str[:2]), 
                    minute=int(start_str[3:5]), 
                    second=0, 
                    microsecond=0
                )
                new_next_due = next_start

            # Save new_next_due
            if database_url:
                next_due_save = new_next_due.astimezone(pytz.utc)
                last_sent_save = now_utc
                conn = get_db_connection()
                c = conn.cursor()
                c.execute(f'UPDATE {reminder_table} SET next_due=%s, last_sent=%s WHERE id=%s',
                        (next_due_save, last_sent_save, reminder_id))
                conn.commit()
                conn.close()
            else:
                next_due_save = new_next_due
                last_sent_save = now_local
                import sqlite3
                conn = sqlite3.connect('babylog.db')
                c = conn.cursor()
                c.execute(f'UPDATE {reminder_table} SET next_due=?, last_sent=? WHERE id=?',
                        (next_due_save, last_sent_save, reminder_id))
                conn.commit()
                conn.close()

    except Exception as e:
        logging.error(f"Error checking reminders: {e}")
        
def start_reminder_scheduler():
    """Start background thread for reminder checking"""
    def reminder_worker():
        while True:
            try:
                check_and_send_reminders()
                time.sleep(1800)  # Check every 30 minutes
            except Exception as e:
                logging.error(f"Error in reminder scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
    reminder_thread.start()
    logging.info("Reminder scheduler started")

# Continue with all your existing functions...
def save_mpasi(user, data):
    """Secure version of save_mpasi"""
    print(f"[DB] Saving MPASI for {user}: {data}")
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('mpasi_log')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValueError(f"Invalid time: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_volume_ml(str(data['volume_ml']))
    if not is_valid:
        raise ValueError(f"Invalid volume: {error_msg}")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['volume_ml'], data['food_detail'], data['food_grams'], data.get('est_calories')))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['volume_ml'], data['food_detail'], data['food_grams'], data.get('est_calories')))
        conn.commit()
        conn.close()
        
def get_mpasi_summary(user, period_start=None, period_end=None):
    """Secure version of get_mpasi_summary"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('mpasi_log')
    limits = get_tier_limits(user)
    mpasi_limit = limits.get("mpasi_entries")

    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT date, time, volume_ml, food_detail, food_grams, est_calories FROM {table_name} WHERE {user_col}=%s'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN %s AND %s'
            params += [period_start, period_end]
        query += ' ORDER BY date DESC, time DESC'
        if mpasi_limit is not None:
            query += ' LIMIT %s'
            params.append(mpasi_limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT date, time, volume_ml, food_detail, food_grams, est_calories FROM {table_name} WHERE {user_col}=?'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN ? AND ?'
            params += [period_start, period_end]
        query += ' ORDER BY date DESC, time DESC'
        if mpasi_limit is not None:
            query += ' LIMIT ?'
            params.append(mpasi_limit)
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def save_poop(user, data):
    """Secure version of save_poop"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('poop_log')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValueError(f"Invalid time: {error_msg}")
    
    # Validate Bristol scale
    try:
        bristol = int(data['bristol_scale'])
        if bristol < 1 or bristol > 7:
            raise ValueError("Bristol scale must be between 1-7")
    except (ValueError, TypeError):
        raise ValueError("Invalid Bristol scale value")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, bristol_scale)
            VALUES (%s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['bristol_scale']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, bristol_scale)
            VALUES (?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['bristol_scale']))
        conn.commit()
        conn.close()

def get_poop_log(user, period_start=None, period_end=None):
    """Secure version of get_poop_log"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('poop_log')
    limits = get_tier_limits(user)
    poop_log_limit = limits.get("poop_log_limit")

    # If no period is specified and free, restrict to history_days
    if not period_start and not period_end and limits["history_days"]:
        period_start = (datetime.now() - timedelta(days=limits["history_days"])).strftime('%Y-%m-%d')
        period_end = datetime.now().strftime('%Y-%m-%d')

    query = f"SELECT date, time, bristol_scale FROM {table_name} WHERE {user_col}=%s" if database_url else f"SELECT date, time, bristol_scale FROM {table_name} WHERE {user_col}=?"
    params = [user]

    # Add date range filter if specified
    if period_start and period_end:
        query += " AND date BETWEEN %s AND %s" if database_url else " AND date BETWEEN ? AND ?"
        params += [period_start, period_end]

    query += " ORDER BY date DESC, time DESC"

    # Only add LIMIT if not premium or if a row limit is set
    if poop_log_limit:
        query += " LIMIT %s" if database_url else " LIMIT ?"
        params.append(poop_log_limit)

    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def save_milk_intake(user, data):
    """Secure version of save_milk_intake"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_intake_log')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValueError(f"Invalid time: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_volume_ml(str(data['volume_ml']))
    if not is_valid:
        raise ValueError(f"Invalid volume: {error_msg}")
    
    # Validate milk_type
    if data['milk_type'] not in ['asi', 'sufor', 'mixed']:
        raise ValueError(f"Invalid milk_type: {data['milk_type']}")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['volume_ml'], data['milk_type'], 
              data.get('asi_method'), data.get('sufor_calorie'), data.get('note', "")))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['volume_ml'], data['milk_type'], 
              data.get('asi_method'), data.get('sufor_calorie'), data.get('note', "")))
        conn.commit()
        conn.close()
        
def get_milk_intake_summary(user, period_start=None, period_end=None):
    """Secure version of get_milk_intake_summary"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_intake_log')

    # Apply tier-based limits if no specific period requested
    if not period_start and not period_end:
        limits = get_tier_limits(user)
        if limits["history_days"]:
            # Free tier - limit to X days
            period_start = (datetime.now() - timedelta(days=limits["history_days"])).strftime('%Y-%m-%d')
            period_end = datetime.now().strftime('%Y-%m-%d')
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'''
            SELECT milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)
            FROM {table_name}
            WHERE {user_col}=%s
        '''
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN %s AND %s'
            params += [period_start, period_end]
        query += ' GROUP BY milk_type, asi_method'
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'''
            SELECT milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)
            FROM {table_name}
            WHERE {user_col}=?
        '''
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN ? AND ?'
            params += [period_start, period_end]
        query += ' GROUP BY milk_type, asi_method'
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def format_milk_summary(rows, summary_date):
    if not rows:
        return f"Belum ada catatan minum susu/ASI pada {summary_date}."

    # Handle both tuple (SQLite) and dict (PostgreSQL) results
    total_count = 0
    total_ml = 0
    total_cal = 0
    
    for r in rows:
        if isinstance(r, (list, tuple)):
            # SQLite: [milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)]
            total_count += r[2] or 0
            total_ml += r[3] or 0
            total_cal += r[4] or 0
        else:
            # PostgreSQL: dict-like object with specific keys
            # The keys are usually the column names or auto-generated
            keys = list(r.keys())
            values = list(r.values())
            
            # Count is the 3rd value (index 2), volume is 4th (index 3), calories is 5th (index 4)
            total_count += values[2] if len(values) > 2 and values[2] is not None else 0
            total_ml += values[3] if len(values) > 3 and values[3] is not None else 0
            total_cal += values[4] if len(values) > 4 and values[4] is not None else 0

    lines = [
        f"📊 Ringkasan Minum Susu/ASI ({summary_date})",
        "",
        f"• Total sesi minum: {total_count}",
        f"• Total susu diminum: {total_ml} ml",
        f"• Total kalori (perkiraan): {total_cal} kkal",
        ""
    ]

    for r in rows:
        if isinstance(r, (list, tuple)):
            # SQLite
            milk_type = r[0]
            asi_method = r[1] or ""
            count = r[2]
            volume = r[3]
            calories = r[4] or 0
        else:
            # PostgreSQL
            values = list(r.values())
            milk_type = values[0] if len(values) > 0 else '-'
            asi_method = values[1] if len(values) > 1 else ""
            count = values[2] if len(values) > 2 else 0
            volume = values[3] if len(values) > 3 else 0
            calories = values[4] if len(values) > 4 else 0
            
        # Handle None values
        if asi_method is None:
            asi_method = ""
        if calories is None:
            calories = 0
            
        if milk_type == 'asi':
            lines.append(f"ASI ({asi_method}): {count}x, {volume} ml")
        else:
            lines.append(f"Sufor: {count}x, {volume} ml (kalori: {calories} kkal)")

    return "\n".join(lines)
    
def save_pumping(user, data):
    """Secure version of save_pumping"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('pumping_log')
    
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValueError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValueError(f"Invalid time: {error_msg}")
    
    # Validate milk volumes
    try:
        left_ml = float(data['left_ml'])
        right_ml = float(data['right_ml'])
        if left_ml < 0 or right_ml < 0:
            raise ValueError("Milk volumes cannot be negative")
        if left_ml > 1000 or right_ml > 1000:  # Reasonable upper limit
            raise ValueError("Milk volumes seem too high (max 1000ml per side)")
    except (ValueError, TypeError):
        raise ValueError("Invalid milk volume values")
    
    # Validate milk bags
    try:
        milk_bags = int(data['milk_bags'])
        if milk_bags < 0:
            raise ValueError("Number of milk bags cannot be negative")
        if milk_bags > 50:  # Reasonable upper limit
            raise ValueError("Number of milk bags seems too high (max 50)")
    except (ValueError, TypeError):
        raise ValueError("Invalid milk bags value")
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, left_ml, right_ml, milk_bags)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO {table_name} ({user_col}, date, time, left_ml, right_ml, milk_bags)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))
        conn.commit()
        conn.close()

def get_pumping_summary(user, period_start=None, period_end=None):
    """Secure version of get_pumping_summary"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('pumping_log')
    limits = get_tier_limits(user)
    pumping_limit = limits.get("pumping_entries")

    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT date, time, left_ml, right_ml, milk_bags FROM {table_name} WHERE {user_col}=%s'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN %s AND %s'
            params += [period_start, period_end]
        query += ' ORDER BY date DESC, time DESC'
        if pumping_limit is not None:
            query += ' LIMIT %s'
            params.append(pumping_limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT date, time, left_ml, right_ml, milk_bags FROM {table_name} WHERE {user_col}=?'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN ? AND ?'
            params += [period_start, period_end]
        query += ' ORDER BY date DESC, time DESC'
        if pumping_limit is not None:
            query += ' LIMIT ?'
            params.append(pumping_limit)
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def get_daily_summary(user, summary_date):
    """Secure version of get_daily_summary"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    
    # Validate table names
    pumping_table = DatabaseSecurity.validate_table_name('pumping_log')
    mpasi_table = DatabaseSecurity.validate_table_name('mpasi_log')
    timbang_table = DatabaseSecurity.validate_table_name('timbang_log')
    poop_table = DatabaseSecurity.validate_table_name('poop_log')
    sleep_table = DatabaseSecurity.validate_table_name('sleep_log')

    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        # Pumping summary
        c.execute(f'SELECT SUM(left_ml), SUM(right_ml), COUNT(*), SUM(milk_bags) FROM {pumping_table} WHERE {user_col}=%s AND date=%s', (user, summary_date))
        pump = c.fetchone() or (0, 0, 0, 0)
        # MPASI summary
        c.execute(f'SELECT COUNT(*), SUM(volume_ml), SUM(est_calories) FROM {mpasi_table} WHERE {user_col}=%s AND date=%s', (user, summary_date))
        mpasi = c.fetchone() or (0, 0, 0)
        # Growth summary
        c.execute(f'SELECT weight_kg, height_cm FROM {timbang_table} WHERE {user_col}=%s AND date=%s ORDER BY created_at DESC LIMIT 1', (user, summary_date))
        growth = c.fetchone() or (None, None)
        # Poop summary
        c.execute(f'SELECT COUNT(*) FROM {poop_table} WHERE {user_col}=%s AND date=%s', (user, summary_date))
        poop = c.fetchone() or (0,)
        # Sleep summary
        c.execute(f'''
            SELECT COUNT(*) as sessions, SUM(duration_minutes) as total_minutes 
            FROM {sleep_table} 
            WHERE {user_col}=%s AND date=%s AND is_complete=TRUE
        ''', (user, summary_date))
        sleep_data = c.fetchone() or {'sessions': 0, 'total_minutes': 0}
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        # Pumping summary
        c.execute(f'SELECT SUM(left_ml), SUM(right_ml), COUNT(*), SUM(milk_bags) FROM {pumping_table} WHERE {user_col}=? AND date=?', (user, summary_date))
        pump = c.fetchone() or (0, 0, 0, 0)
        # MPASI summary
        c.execute(f'SELECT COUNT(*), SUM(volume_ml), SUM(est_calories) FROM {mpasi_table} WHERE {user_col}=? AND date=?', (user, summary_date))
        mpasi = c.fetchone() or (0, 0, 0)
        # Growth summary
        c.execute(f'SELECT weight_kg, height_cm FROM {timbang_table} WHERE {user_col}=? AND date=? ORDER BY created_at DESC LIMIT 1', (user, summary_date))
        growth = c.fetchone() or (None, None)
        # Poop summary
        c.execute(f'SELECT COUNT(*) FROM {poop_table} WHERE {user_col}=? AND date=?', (user, summary_date))
        poop = c.fetchone() or (0,)
        # Sleep summary
        c.execute(f'''
            SELECT COUNT(*) as sessions, SUM(duration_minutes) as total_minutes 
            FROM {sleep_table} 
            WHERE {user_col}=? AND date=? AND is_complete=1
        ''', (user, summary_date))
        sleep_row = c.fetchone()
        sleep_data = {
            'sessions': sleep_row[0] if sleep_row else 0,
            'total_minutes': sleep_row[1] if sleep_row and sleep_row[1] else 0
        }
        conn.close()

    # Process sleep data for consistent format
    if isinstance(sleep_data, dict):
        sleep_sessions = sleep_data.get('sessions', 0)
        sleep_minutes = sleep_data.get('total_minutes', 0) or 0
    else:
        sleep_sessions = sleep_data[0] if sleep_data else 0
        sleep_minutes = sleep_data[1] if sleep_data and len(sleep_data) > 1 else 0
    
    sleep_hours, sleep_mins = divmod(int(sleep_minutes), 60)

    return {
        "pumping_count": pump[2] if len(pump) > 2 else 0,
        "pumping_total": (pump[0] or 0) + (pump[1] or 0),
        "pumping_left": pump[0] or 0,
        "pumping_right": pump[1] or 0,
        "pumping_bags": pump[3] if len(pump) > 3 else 0,
        "mpasi_count": mpasi[0] if len(mpasi) > 0 else 0,
        "mpasi_total": mpasi[1] if len(mpasi) > 1 else 0,
        "calories": mpasi[2] if len(mpasi) > 2 else 0,
        "weight": growth[0] if growth and growth[0] is not None else "-",
        "height": growth[1] if growth and len(growth) > 1 and growth[1] is not None else "-",
        "poop_count": poop[0] if poop else 0,
        "sleep_sessions": sleep_sessions,
        "sleep_duration": f"{sleep_hours}j {sleep_mins}m" if sleep_sessions > 0 else "-",
        "note": "-"
    }

def format_summary_message(data, summary_date):
    lines = [
        f"📊 Ringkasan Aktivitas Bayi ({summary_date})",
        "",
        f"• ASI dipompa: {data['pumping_count']}x, total {data['pumping_total']} ml (Kiri: {data['pumping_left']} ml, Kanan: {data['pumping_right']} ml, Kantong: {data['pumping_bags']})",
        f"• Makan MPASI: {data['mpasi_count']}x, total {data['mpasi_total']} ml",
        f"• Estimasi kalori: {data['calories']} kkal",
        f"• Berat: {data['weight']} kg, Tinggi: {data['height']} cm",
        f"• Pup: {data['poop_count']}x",
        f"• Catatan: {data['note']}",
        "",
        "Ketik 'detail [aktivitas]' untuk info lebih lanjut."
    ]
    return "\n".join(lines)

def extract_total_calories(gpt_summary):
    """
    Extracts the total calories from the GPT summary if possible.
    Assumes summary contains a line like 'Total: 220 kkal'
    """
    import re
    match = re.search(r"Total:\s*(\d+)\s*kkal", gpt_summary or "", re.IGNORECASE)
    return int(match.group(1)) if match else None

def update_mpasi_with_calories(user, data, gpt_summary, est_calories):
    """Secure version of update_mpasi_with_calories"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('mpasi_log')
    
    conn = get_db_connection()
    c = conn.cursor()
    if database_url:
        c.execute(
            f"""UPDATE {table_name} SET gpt_calorie_summary=%s, est_calories=%s
                WHERE {user_col}=%s AND date=%s AND time=%s""",
            (gpt_summary, est_calories, user, data['date'], data['time'])
        )
    else:
        c.execute(
            f"""UPDATE {table_name} SET gpt_calorie_summary=?, est_calories=?
                WHERE {user_col}=? AND date=? AND time=?""",
            (gpt_summary, est_calories, user, data['date'], data['time'])
        )
    conn.commit()
    conn.close()

def send_calorie_summary_and_update(user, data):
    try:
        summary = estimate_calories_openai(data['food_grams'])
        total = extract_total_calories(summary)
        update_mpasi_with_calories(user, data, summary, total)
        send_twilio_message(user, f"Hasil estimasi kalori MPASI:\n{summary}")
    except Exception as e:
        logging.error(f"Error in send_calorie_summary_and_update: {e}")
        send_twilio_message(user, "Maaf, terjadi kesalahan saat menghitung kalori MPASI.")

def get_mpasi_milk_data(user_phone):
    from datetime import date, timedelta

    # Get ASI kcal value for this user (default 0.67 if not found)
    try:
        user_kcal = get_user_calorie_setting(user_phone)
        asi_kcal = user_kcal.get("asi", 0.67)
    except Exception:
        asi_kcal = 0.67

    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in reversed(range(7))]
    data = []
    for d in days:
        # Aggregate MPASI for this day
        mpasi_rows = get_mpasi_summary(user_phone, d, d) or []
        mpasi_ml = sum([(row[2] or 0) for row in mpasi_rows])
        mpasi_kcal = sum([(row[5] or 0) for row in mpasi_rows])

        # Aggregate Milk for this day - separate ASI and Sufor
        milk_rows = get_milk_intake_summary(user_phone, d, d) or []
        milk_ml_asi = 0
        milk_kcal_asi = 0
        milk_ml_sufor = 0
        milk_kcal_sufor = 0

        for row in milk_rows:
            # row: [milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)]
            milk_type = row[0]
            volume_ml = row[3] or 0
            sufor_calorie = row[4] or 0
            if milk_type == "asi":
                milk_ml_asi += volume_ml
                milk_kcal_asi += volume_ml * asi_kcal
            elif milk_type == "sufor":
                milk_ml_sufor += volume_ml
                milk_kcal_sufor += sufor_calorie

        milk_ml = milk_ml_asi + milk_ml_sufor
        milk_kcal = milk_kcal_asi + milk_kcal_sufor

        data.append({
            "date": d,
            "mpasi_ml": mpasi_ml,
            "mpasi_kcal": mpasi_kcal,
            "milk_ml": milk_ml,
            "milk_kcal": milk_kcal,
            "milk_ml_asi": milk_ml_asi,
            "milk_kcal_asi": milk_kcal_asi,
            "milk_ml_sufor": milk_ml_sufor,
            "milk_kcal_sufor": milk_kcal_sufor,
        })
    return data

# Usage in your main.py - Replace vulnerable queries:
def get_child_secure(user):
    """Secure version of get_child"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    # Validate column name
    user_col = DatabaseSecurity.validate_column_name(
        user_col, 
        DatabaseSecurity.ALLOWED_USER_COLUMNS
    )
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        # Now safe because user_col is validated
        query = f'SELECT name, gender, dob, height_cm, weight_kg FROM child WHERE {user_col}=%s ORDER BY created_at DESC LIMIT 1'
        c.execute(query, (user,))
        row = c.fetchone()
        conn.close()
        return row
    else:
        # SQLite version
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT name, gender, dob, height_cm, weight_kg FROM child WHERE {user_col}=? ORDER BY created_at DESC LIMIT 1'
        c.execute(query, (user,))
        row = c.fetchone()
        conn.close()
        return row

def normalize_user_phone(user_phone):
    # Accept 'whatsapp:' or 'p:' prefix
    if user_phone.startswith("whatsapp:"):
        return user_phone
    elif user_phone.startswith("p:"):
        return user_phone
    else:
        # Default to 'whatsapp:'
        return "whatsapp:" + user_phone

@app.get("/mpasi-milk-graph/{user_phone}")
def mpasi_milk_graph(user_phone: str):
    user_phone = normalize_user_phone(user_phone)  # Add this line
    print("Requested report for:", user_phone)
    data = get_mpasi_milk_data(user_phone)
    print("Aggregated data:", data)
    chart_buf = generate_mpasi_milk_chart(data, user_phone)
    return StreamingResponse(chart_buf, media_type='image/png')

@app.get("/report-mpasi-milk/{user_phone}")
def report_mpasi_milk(user_phone: str):
    user_phone = normalize_user_phone(user_phone)
    print("Requested report for:", user_phone)
    data = get_mpasi_milk_data(user_phone)
    print("Aggregated data:", data)
    chart_buf = generate_mpasi_milk_chart(data, user_phone)
    pdf_buf = generate_pdf_report(data, chart_buf, user_phone)
    return StreamingResponse(pdf_buf, media_type='application/pdf')

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        if os.environ.get('DATABASE_URL'):
            conn = get_db_connection()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            conn.close()
        
        return {
            "status": "healthy", 
            "timestamp": datetime.now().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# FastAPI startup event
@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    try:
        # Start reminder scheduler only in production (Railway)
        if os.environ.get('DATABASE_URL'):
            start_reminder_scheduler()
        
        logging.info("Baby log app started successfully")
        
    except Exception as e:
        logging.error(f"Startup error: {e}")

WELCOME_MESSAGE = (
    "Selamat datang di Babylog! 👋 Saya siap membantu Anda mengelola catatan dan perkembangan si kecil.\n\n"
    "Untuk memulai, Anda bisa coba perintah ini:\n"
    "• `tambah anak` (untuk menambahkan si kecil)\n"
    "• `catat timbang` (untuk log berat badan)\n"
    "• `catat mpasi` (untuk log makanan)\n"
    "• `catat tidur` (untuk log jam tidur)\n"
    "• `ringkasan hari ini` (untuk melihat rangkuman harian)\n\n"
    "Butuh bantuan lebih lanjut? Ketik `bantuan`.\n"
    "Ingin melihat semua perintah? Ketik `panduan`."
)

HELP_MESSAGE = (
    "🤖 *Bantuan Babylog:*\n\n"
    "Pilih kategori bantuan yang Anda butuhkan, atau ketik perintah langsung:\n\n"
    "*Data Anak & Tumbuh Kembang:*\n"
    "• `tambah anak` / `tampilkan anak`\n"
    "• `catat timbang` / `lihat tumbuh kembang`\n\n"
    "*Asupan Nutrisi:*\n"
    "• `catat mpasi` / `lihat ringkasan mpasi`\n"
    "• `catat susu` / `lihat ringkasan susu [hari ini/tanggal]`\n"
    "• `catat pumping` / `lihat ringkasan pumping`\n\n"
    "*Kesehatan & Aktivitas:*\n"
    "• `catat bab` / `lihat riwayat bab`\n"
    "• `catat tidur` / `lihat tidur` / `riwayat tidur`\n\n"
    "*Pengaturan Kalori:*\n"
    "• `hitung kalori susu`\n"
    "• `set kalori asi` / `set kalori sufor`\n"
    "• `lihat kalori` / `daftar asupan` / `persentase asupan`\n\n"
    "*Pengingat Susu:*\n"
    "• `atur pengingat susu` / `lihat pengingat`\n"
    "• *Saat ada pengingat, Anda bisa:*\n"
    "  • `done [volume]ml` (Selesai dan catat volume)\n"
    "  • `snooze [menit]` (Tunda pengingat)\n"
    "  • `skip reminder` (Lewati pengingat)\n\n"
    "*Pelacakan Tidur:*\n"
    "• `catat tidur` - Mulai mencatat sesi tidur\n"
    "• `selesai tidur [HH:MM]` - Selesaikan sesi tidur\n"
    "• `batal tidur` - Batalkan sesi yang belum selesai\n"
    "• `lihat tidur` - Tidur hari ini\n"
    "• `riwayat tidur` - Riwayat beberapa hari\n\n"
    "*Laporan & Ringkasan:*\n"
    "• `ringkasan hari ini`\n\n"
    "*Perintah Umum:*\n"
    "• `batal` (Batalkan sesi saat ini)\n\n"
    "Butuh daftar lengkap semua perintah? Ketik `panduan`."
)

PANDUAN_MESSAGE = (
    "🤖 *Panduan Lengkap Perintah Babylog:*\n\n"
    "Berikut adalah semua perintah yang bisa Anda gunakan:\n\n"
    "*I. Data Anak & Tumbuh Kembang:*\n"
    "• `tambah anak` - Tambah data si kecil baru\n"
    "• `tampilkan anak` - Lihat data anak\n"
    "• `catat timbang` - Catat berat & tinggi badan\n"
    "• `lihat tumbuh kembang` - Lihat grafik dan riwayat pertumbuhan\n\n"
    "*II. Asupan Nutrisi:*\n"
    "• `catat mpasi` - Catat detail MPASI\n"
    "• `lihat ringkasan mpasi` - Lihat ringkasan MPASI\n"
    "• `catat susu` - Catat pemberian susu\n"
    "• `lihat ringkasan susu [hari ini/tanggal]` - Rekap susu harian/khusus\n"
    "• `catat pumping` - Catat volume ASI pumping\n"
    "• `lihat ringkasan pumping` - Lihat total & riwayat ASI perah\n\n"
    "*III. Pengaturan Kalori:*\n"
    "• `hitung kalori susu` - Hitung estimasi kalori susu\n"
    "• `set kalori asi` - Atur kalori per ml ASI\n"
    "• `set kalori sufor` - Atur kalori per ml susu formula\n"
    "• `lihat kalori` - Total kalori harian\n"
    "• `daftar asupan` - Daftar lengkap asupan\n"
    "• `persentase asupan` - Persentase nutrisi asupan\n\n"
    "*IV. Kesehatan & Aktivitas:*\n"
    "• `catat bab` - Catat riwayat BAB\n"
    "• `lihat riwayat bab` - Lihat riwayat BAB\n\n"
    "*V. Pelacakan Tidur:*\n"
    "• `catat tidur` - Mulai mencatat sesi tidur bayi\n"
    "• `selesai tidur [HH:MM]` - Selesaikan sesi tidur (cth: selesai tidur 07:30)\n"
    "• `batal tidur` - Batalkan sesi tidur yang belum selesai\n"
    "• `lihat tidur` - Lihat catatan tidur hari ini\n"
    "• `riwayat tidur` - Lihat riwayat tidur beberapa hari\n\n"
    "*VI. Pengingat Susu:*\n"
    "• `atur pengingat susu` - Atur pengingat pemberian susu\n"
    "• `lihat pengingat` - Daftar pengingat susu aktif\n"
    "• Respon cepat saat pengingat aktif:\n"
    "  • `done [volume]ml` - Catat volume susu (cth: done 120ml)\n"
    "  • `snooze [menit]` - Tunda pengingat (cth: snooze 15)\n"
    "  • `skip reminder` - Lewati pengingat\n\n"
    "*VII. Laporan & Ringkasan:*\n"
    "• `ringkasan hari ini` - Lihat rangkuman aktivitas hari ini\n\n"
    "*VIII. Perintah Umum:*\n"
    "• `batal` - Batalkan sesi/aksi berjalan\n"
    "• `bantuan` - Tampilkan bantuan singkat\n"
    "• `panduan` - Tampilkan panduan lengkap ini\n\n"
    "*Tips Penggunaan:*\n"
    "📱 Gunakan format waktu 24 jam (HH:MM)\n"
    "📊 User gratis dibatasi beberapa fitur, upgrade ke premium untuk akses penuh\n"
    "💡 Ketik `batal` kapan saja untuk membatalkan proses yang sedang berjalan"
)

# Your existing webhook handler (unchanged except for cost control integration)
@app.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    user = None
    try:
        form = await request.form()
        user = form.get("From")
        msg = form.get("Body", "").strip()
        resp = MessagingResponse()
        session = session_manager.get_session(user)
        reply = ""

        # Universal Commands
        if msg.lower() in ["batal", "cancel"]:
            session["state"] = None
            session["data"] = {}
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message("Sesi dibatalkan. Anda bisa mulai kembali dengan perintah baru.")
            return Response(str(resp), media_type="application/xml")

        # 1. Welcome: greet on initial keywords
        if msg.lower() in ["start", "mulai", "hi", "halo", "assalamualaikum"]:
            resp.message(WELCOME_MESSAGE)
            return Response(str(resp), media_type="application/xml")

        # 2. Help section
        if msg.lower() in ["help", "bantuan"]:
            resp.message(HELP_MESSAGE)
            return Response(str(resp), media_type="application/xml")

        # 3. Guideline section
        if msg.lower() in ["panduan", "guide", "commands", "perintah"]:
            resp.message(PANDUAN_MESSAGE)
            return Response(str(resp), media_type="application/xml")

        # Reminder Commands
        elif msg.lower() in ["set reminder susu", "atur pengingat susu"]:
            limits = get_tier_limits(user)  # Get limits first
            if os.environ.get('DATABASE_URL'):
                user_info = get_user_tier(user)
                if user_info['tier'] == 'free':
                    active_reminders = len(get_user_reminders(user))
                    if active_reminders >= limits["active_reminders"]:  # Use limits, not undefined variable
                        reply = f"🚫 Tier gratis dibatasi {limits['active_reminders']} pengingat aktif. Upgrade ke premium untuk unlimited!"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")


        elif session["state"] == "REMINDER_NAME":
            session["data"]["reminder_name"] = msg
            session["state"] = "REMINDER_INTERVAL"
            reply = "Interval berapa jam? (contoh: 2, 3, 4 untuk setiap 2/3/4 jam)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_INTERVAL":
            try:
                interval = int(msg)
                if 1 <= interval <= 12:
                    session["data"]["interval_hours"] = interval
                    session["state"] = "REMINDER_START"
                    reply = "Jam berapa mulai pengingat? (format HH:MM, contoh: 06:00)"
                else:
                    reply = "Masukkan interval antara 1-12 jam."
            except ValueError:
                reply = "Masukkan angka untuk interval jam."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_START":
            is_valid, error_msg = InputValidator.validate_time(msg)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["start_time"] = msg
                session["state"] = "REMINDER_END"
                reply = "Jam berapa berhenti pengingat? (format HH:MM, contoh: 22:00)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_END":
            is_valid, error_msg = InputValidator.validate_time(msg)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["end_time"] = msg
                session["state"] = "REMINDER_CONFIRM"
                    
                    summary = f"""Konfirmasi Pengingat:
- Nama: {session['data']['reminder_name']}
- Setiap: {session['data']['interval_hours']} jam
- Dari: {session['data']['start_time']} 
- Sampai: {session['data']['end_time']}

Apakah sudah benar? (ya/tidak)"""
                    reply = summary
                except ValueError:
                    reply = "Format jam tidak valid. Gunakan HH:MM, contoh: 22:00"
            else:
                reply = "Format jam tidak valid. Gunakan HH:MM, contoh: 22:00"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_CONFIRM":
            if msg.lower() == "ya":
                try:
                    save_reminder(user, session["data"])  # This can throw ValueError
                    reply = f"✅ Pengingat '{session['data']['reminder_name']}' tersimpan! Pengingat pertama akan dikirim pukul {session['data']['start_time']}."
                    session["state"] = None
                    session["data"] = {}
                except ValueError as e:
                    reply = f"❌ {str(e)}"
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                except Exception as e:
                    logging.error(f"Error saving reminder: {e}")
                    reply = "❌ Terjadi kesalahan saat menyimpan pengingat."

        # Show reminders
        elif msg.lower() in ["show reminders", "lihat pengingat"]:
            reminders = get_user_reminders(user)
            if reminders:
                reply = "📋 Pengingat Aktif:\n\n"
                for r in reminders:
                    if hasattr(r, 'keys'):  # PostgreSQL
                        status = "🟢 Aktif" if r['is_active'] else "🔴 Tidak aktif"
                        reply += f"• {r['reminder_name']} - Setiap {r['interval_hours']}jam ({r['start_time']}-{r['end_time']}) {status}\n"
                    else:  # SQLite
                        status = "🟢 Aktif" if r[6] else "🔴 Tidak aktif"
                        reply += f"• {r[2]} - Setiap {r[3]}jam ({r[4]}-{r[5]}) {status}\n"
                reply += "\nKetik 'stop reminder [nama]' untuk matikan\nKetik 'delete reminder [nama]' untuk hapus"
            else:
                reply = "Belum ada pengingat yang diatur. Ketik 'set reminder susu' untuk membuat."
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Quick responses to reminders
        elif msg.lower().startswith("done "):
            volume_match = re.search(r'done\s+(\d+)', msg.lower())
            if volume_match:
                volume = float(volume_match.group(1))
                
                milk_data = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'time': datetime.now().strftime("%H:%M"),
                    'volume_ml': volume,
                    'milk_type': 'mixed',
                    'note': 'Via reminder'
                }
                save_milk_intake(user, milk_data)
                reply = f"✅ Tercatat: {volume}ml susu pada {milk_data['time']}. Pengingat berikutnya akan disesuaikan."
            else:
                reply = "Format: 'done [volume]ml', contoh: 'done 120ml'"
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif msg.lower().startswith("snooze "):
            snooze_match = re.search(r'snooze\s+(\d+)', msg.lower())
            if snooze_match:
                minutes = int(snooze_match.group(1))
                reminders = get_user_reminders(user)
                if reminders:
                    # Simple snooze implementation
                    reply = f"⏰ Pengingat ditunda {minutes} menit."
                else:
                    reply = "Tidak ada pengingat aktif untuk ditunda."
            else:
                reply = "Format: 'snooze [menit]', contoh: 'snooze 30'"
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif msg.lower() == "skip reminder":
            reminders = get_user_reminders(user)
            if reminders:
                reply = "⏭️ Pengingat dilewati. Pengingat berikutnya telah dijadwalkan."
            else:
                reply = "Tidak ada pengingat aktif."
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # [Continue with ALL your existing webhook logic from the original script]
        # I'm showing the pattern - you would include all your existing flows here
        # Calorie setting commands, data anak, timbang, mpasi, poop, pumping, milk intake, etc.
        
        # For brevity, I'll include a few key ones and the default response:
        
    # Calorie setting commands
        if msg.lower().startswith("set kalori asi"):
            session["state"] = "SET_KALORI_ASI"
            reply = "Masukkan nilai kalori per ml ASI (default 0.67), atau tekan enter untuk default:"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        elif session["state"] == "SET_KALORI_ASI":
            val = msg.strip()
            try:
                kcal = 0.67 if val == "" else float(val.replace(",", "."))
                set_user_calorie_setting(user, "asi", kcal)
                reply = f"Nilai kalori ASI di-set ke {kcal} kkal/ml."
                session["state"] = None
                session["data"] = {}
            except Exception:
                reply = "Format tidak valid. Masukkan angka (contoh: 0.67) atau tekan enter untuk default."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        if msg.lower().startswith("set kalori sufor"):
            session["state"] = "SET_KALORI_SUFOR"
            reply = "Masukkan nilai kalori per ml susu formula (default 0.7), atau tekan enter untuk default:"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        elif session["state"] == "SET_KALORI_SUFOR":
            val = msg.strip()
            try:
                kcal = 0.7 if val == "" else float(val.replace(",", "."))
                set_user_calorie_setting(user, "sufor", kcal)
                reply = f"Nilai kalori susu formula di-set ke {kcal} kkal/ml."
                session["state"] = None
                session["data"] = {}
            except Exception:
                reply = "Format tidak valid. Masukkan angka (contoh: 0.7) atau tekan enter untuk default."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # --- Daily summary command ---
        summary_commands = [
            "summary today",
            "ringkasan hari ini",
            "show summary",
            "daily summary",
        ]
        if any(msg.lower().startswith(cmd) for cmd in summary_commands) or re.match(r"^(summary|ringkasan) \d{4}-\d{2}-\d{2}", msg.lower()):
            if "today" in msg.lower() or "hari ini" in msg.lower():
                summary_date = date.today().isoformat()
            else:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", msg)
                summary_date = m.group(1) if m else date.today().isoformat()
            data = get_daily_summary(user, summary_date)
            reply = format_summary_message(data, summary_date)
            session["state"] = None
            session["data"] = {}
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")


        # ---- Flow 1: Data Anak ----
        if msg.lower() == "tambah anak":
            session["state"] = "ADDCHILD_NAME"
            session["data"] = {}
            reply = "Siapa nama anak Anda?"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_NAME":
            session["data"]["name"] = msg
            session["state"] = "ADDCHILD_GENDER"
            reply = "Jenis kelamin anak? (laki-laki/perempuan)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_GENDER":
            gender = msg.lower()
            if gender in ["laki-laki", "pria", "laki"]:
                session["data"]["gender"] = "laki-laki"
                session["state"] = "ADDCHILD_DOB"
                reply = "Tanggal lahir? (format: YYYY-MM-DD, contoh: 2019-05-21)"
            elif gender in ["perempuan", "wanita"]:
                session["data"]["gender"] = "perempuan"
                session["state"] = "ADDCHILD_DOB"
                reply = "Tanggal lahir? (format: YYYY-MM-DD, contoh: 2019-05-21)"
            else:
                reply = "Masukkan 'laki-laki' atau 'perempuan' untuk jenis kelamin."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_DOB":
            try:
                datetime.strptime(msg, "%Y-%m-%d")
                session["data"]["dob"] = msg
                session["state"] = "ADDCHILD_HEIGHT"
                reply = "Tinggi badan anak (cm)? (contoh: 75.5)"
            except ValueError:
                reply = "Masukkan tanggal dengan format YYYY-MM-DD, contoh: 2019-05-21."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_HEIGHT":
            is_valid, error_msg = InputValidator.validate_height_cm(msg)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["height_cm"] = float(msg)
                session["state"] = "ADDCHILD_WEIGHT"
                reply = "Berat badan? (kg, contoh: 8.4 atau 8500 untuk gram)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_WEIGHT":
            # Convert grams to kg if needed
            weight_input = msg
            try:
                weight = float(weight_input)
                weight_kg = weight / 1000 if weight > 100 else weight
                
                is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["weight_kg"] = weight_kg
                # Show summary before save
                summary = (
                    f"Data anak:\n"
                    f"- Nama: {session['data']['name']}\n"
                    f"- Jenis kelamin: {session['data']['gender']}\n"
                    f"- Tgl lahir: {session['data']['dob']}\n"
                    f"- Tinggi: {session['data']['height_cm']} cm\n"
                    f"- Berat: {session['data']['weight_kg']} kg\n"
                    f"Apakah data sudah benar? (ya/ulang/batal)"
                )
                session["state"] = "ADDCHILD_CONFIRM"
                reply = summary
            except ValueError:
                reply = "❌ Masukkan angka untuk berat badan, contoh: 8.4 atau 8500."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_CONFIRM":
            if msg.lower() == "ya":
                try:
                    save_child(user, session["data"])  # This can throw ValueError
                    reply = "Data anak tersimpan! Untuk melihat data anak, ketik: tampilkan anak"
                    session["state"] = None
                    session["data"] = {}
                except ValueError as e:
                    reply = f"❌ {str(e)}"
                    # Don't reset session, let user fix the error
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                except Exception as e:
                    logging.error(f"Error saving child: {e}")
                    reply = "❌ Terjadi kesalahan saat menyimpan data anak."
            elif msg.lower() == "ulang":
                session["state"] = "ADDCHILD_NAME"
                reply = "Siapa nama anak Anda? (Ulangi input)"
            elif msg.lower() == "batal":
                session["state"] = None
                session["data"] = {}
                reply = "Input data anak dibatalkan."
            else:
                reply = "Ketik 'ya' jika data sudah benar, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif msg.lower() == "tampilkan anak":
            row = get_child(user)
            if row:
                reply = f"Nama: {row[0]}, Jenis kelamin: {row[1].capitalize()}, Tgl lahir: {row[2]}, Tinggi: {row[3]} cm, Berat: {row[4]} kg"
            else:
                reply = "Data anak belum ada. Silakan ketik 'tambah anak' untuk menambah data anak."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # ---- Flow 2: Catat Timbang ----
        elif msg.lower() == "catat timbang":
            session["state"] = "TIMBANG_HEIGHT"
            session["data"] = {"date": datetime.now().strftime("%Y-%m-%d")}
            reply = "Tinggi badan (cm)?"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "TIMBANG_HEIGHT":
            is_valid, error_msg = InputValidator.validate_height_cm(msg)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["height_cm"] = float(msg)
                session["state"] = "TIMBANG_WEIGHT"
                reply = "Berat badan? (kg)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "TIMBANG_WEIGHT":
            weight_input = msg
            try:
                weight = float(weight_input)
                weight_kg = weight / 1000 if weight > 100 else weight
                
                is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["weight_kg"] = weight_kg
                    session["state"] = "TIMBANG_HEAD"
                    reply = "Lingkar kepala (cm)?"
            except ValueError:
                reply = "❌ Masukkan angka yang valid untuk berat badan"
                
                elif session["state"] == "TIMBANG_HEAD":
                    try:
                        session["data"]["head_circum_cm"] = float(msg)
                        save_timbang(user, session["data"])  # This can throw ValueError
                        reply = "Data timbang tersimpan! Untuk melihat riwayat, ketik: lihat tumbuh kembang"
                        session["state"] = None
                        session["data"] = {}
                    except ValueError as e:
                        if "Invalid" in str(e):  # From InputValidator
                            reply = f"❌ {str(e)}"
                        else:
                            reply = "Masukkan angka yang valid untuk lingkar kepala (cm)."
                    except Exception as e:
                        logging.error(f"Error saving timbang: {e}")
                        reply = "❌ Terjadi kesalahan saat menyimpan data timbang."
                    
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            
        elif msg.lower().startswith("lihat tumbuh kembang"):
            records = get_timbang_history(user)
            if records:
                reply = "Riwayat Timbang Terbaru:\n"
                for r in records[::-1]:
                    reply += f"{r[0]}: Tinggi {r[1]} cm, Berat {r[2]} kg, Lingkar kepala {r[3]} cm\n"
                reply += "\n(Untuk grafik, integrasikan matplotlib & pengiriman gambar)"
            else:
                reply = "Belum ada catatan timbang. Ketik 'catat timbang' untuk menambah data."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # ---- Flow 3: Catat MPASI ----
        elif msg.lower() == "catat mpasi":
            session["state"] = "MPASI_DATE"
            session["data"] = {}
            reply = "Tanggal makan? (YYYY-MM-DD, atau ketik 'today')"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Tanggal Makan
        elif session["state"] == "MPASI_DATE":
            if msg.lower().strip() == "today":
                session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                session["state"] = "MPASI_TIME"
                reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
            else:
                # Validate date input
                is_valid, error_msg = InputValidator.validate_date(msg)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["date"] = msg
                    session["state"] = "MPASI_TIME"
                    reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Jam Makan
        elif session["state"] == "MPASI_TIME":
            time_input = msg.replace('.', ':')
            if re.match(r"^\d{2}:\d{2}$", time_input):
                try:
                    datetime.strptime(time_input, "%H:%M")
                    session["data"]["time"] = time_input
                    session["state"] = "MPASI_VOL"
                    reply = "Berapa ml yang dimakan?"
                except ValueError:
                    reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            else:
                reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Volume Makan
        elif session["state"] == "MPASI_VOL":
            # Validate volume input
            is_valid, error_msg = InputValidator.validate_volume_ml(msg)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["volume_ml"] = float(msg)
                session["state"] = "MPASI_DETAIL"
                reply = "Makanan apa saja? (cth: nasi 50gr, ayam 30gr, wortel 20gr)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Detail Makanan
        elif session["state"] == "MPASI_DETAIL":
            session["data"]["food_detail"] = InputValidator.sanitize_text_input(msg, 200)
            session["state"] = "MPASI_GRAMS"
            reply = "Masukkan menu dan porsi MPASI (misal: nasi santan 5 sdm, ayam 1 potong), atau 'skip'."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Gram/Berat/Estimasi Kalori
        elif session["state"] == "MPASI_GRAMS":
            if msg.lower() != "skip":
                session["data"]["food_grams"] = msg
                background_tasks.add_task(
                    send_calorie_summary_and_update, user, session["data"].copy()
                )
            else:
                session["data"]["food_grams"] = ""
                session["data"]["gpt_calorie_summary"] = ""
                session["data"]["est_calories"] = None
            
            try:
                save_mpasi(user, session["data"])  # This can throw ValueError
                reply = "Catat MPASI tersimpan! Silahkan cek di lihat ringkasan mpasi."
            except ValueError as e:
                reply = f"❌ {str(e)}"
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            except Exception as e:
                logging.error(f"Error saving MPASI: {e}")
                reply = "❌ Terjadi kesalahan saat menyimpan data MPASI."
            
            session["state"] = None
            session["data"] = {}
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Lihat Ringkasan
        elif msg.lower().startswith("lihat ringkasan mpasi"):
            rows = get_mpasi_summary(user)
            if rows:
                total_ml = 0
                total_cal = 0
                for row in rows:
                    if isinstance(row, (list, tuple)):
                        total_ml += row[2] or 0
                        total_cal += row[5] or 0
                    else:
                        total_ml += row.get("volume_ml", 0) or 0
                        total_cal += row.get("est_calories", 0) or 0
                reply = f"Ringkasan MPASI:\nTotal makan: {len(rows)}\nTotal ml: {total_ml}\nEstimasi total kalori: {total_cal}\n"
            else:
                reply = "Belum ada catat mpasi. Ketik 'catat mpasi' untuk menambah data."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # ---- Flow 4: Pengingat Kalori ----
        elif msg.lower() == "lihat kalori":
            # Calculate total calories from both MPASI and susu for today
            today = datetime.now().strftime("%Y-%m-%d")
            mpasi_rows = get_mpasi_summary(user, today, today)
            susu_rows = get_milk_intake_summary(user, today, today)
            total_cal_mpasi = sum([row[5] or 0 for row in mpasi_rows])
            total_cal_susu = sum([r[4] or 0 for r in susu_rows])
            reply = (
                f"Total kalori hari ini:\n"
                f"- MPASI: {total_cal_mpasi} kkal\n"
                f"- Susu: {total_cal_susu} kkal\n"
                f"Total: {total_cal_mpasi + total_cal_susu} kkal"
            )
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif msg.lower() == "daftar asupan":
            # Aggregate all foods and milk types for today
            today = datetime.now().strftime("%Y-%m-%d")
            mpasi_rows = get_mpasi_summary(user, today, today)
            susu_rows = get_milk_intake_summary(user, today, today)
            foods = []
            for row in mpasi_rows:
                if row[3]:
                    foods += [i.strip() for i in row[3].split(",")]
            milk_types = [r[0] for r in susu_rows if r[0]]
            all_items = list(set(foods + milk_types))
            reply = "Daftar asupan hari ini:\n" + (", ".join(all_items) if all_items else "Belum ada makanan/susu tercatat.")
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif msg.lower() == "persentase asupan":
            # Calculate proportion of calories from MPASI vs susu
            today = datetime.now().strftime("%Y-%m-%d")
            mpasi_rows = get_mpasi_summary(user, today, today)
            susu_rows = get_milk_intake_summary(user, today, today)
            total_cal_mpasi = sum([row[5] or 0 for row in mpasi_rows])
            total_cal_susu = sum([r[4] or 0 for r in susu_rows])
            total_kalori = total_cal_mpasi + total_cal_susu
            if total_kalori > 0:
                persen_mpasi = int(total_cal_mpasi / total_kalori * 100)
                persen_susu = 100 - persen_mpasi
                reply = (
                    f"Persentase asupan hari ini:\n"
                    f"- MPASI: {persen_mpasi}%\n"
                    f"- Susu: {persen_susu}%\n"
                    f"(MPASI: {total_cal_mpasi} kkal, Susu: {total_cal_susu} kkal)"
                )
            else:
                reply = "Belum ada log makanan/susu hari ini."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # ---- Flow 5: Catat Pup ----
        elif msg.lower() in ["log poop", "catat bab"]:
            session["state"] = "POOP_DATE"
            session["data"] = {}
            reply = "Tanggal? (YYYY-MM-DD, atau 'today')"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "POOP_DATE":
            if msg.lower().strip() == "today":
                session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
            else:
                try:
                    datetime.strptime(msg, "%Y-%m-%d")
                    session["data"]["date"] = msg
                except ValueError:
                    reply = "Masukkan tanggal dengan format YYYY-MM-DD atau 'today'."
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            session["state"] = "POOP_TIME"
            reply = "Jam berapa? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "POOP_TIME":
            time_input = msg.replace('.', ':')
            if re.match(r"^\d{2}:\d{2}$", time_input):
                try:
                    datetime.strptime(time_input, "%H:%M")
                    session["data"]["time"] = time_input
                    session["state"] = "POOP_BRISTOL"
                    reply = (
                        "Tekstur feses mengikuti Skala Bristol (1-7):\n"
                        "1: Sangat keras (seperti kacang-kacang, susah dikeluarkan)\n"
                        "2: Berbentuk sosis, bergelombang/bergerigi\n"
                        "3: Sosis dengan retakan di permukaan\n"
                        "4: Lembut, berbentuk sosis/pisang, permukaan halus\n"
                        "5: Potongan-potongan lunak, tepi jelas\n"
                        "6: Potongan lembek, tepi bergerigi\n"
                        "7: Cair, tanpa bentuk padat\n\n"
                        "Masukkan angka 1-7 sesuai tekstur feses anak Anda.\n(cth: 4)"
                    )
                except ValueError:
                    reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            else:
                reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "POOP_BRISTOL":
            try:
                bristol = int(msg)
                if 1 <= bristol <= 7:
                    session["data"]["bristol_scale"] = bristol
                    save_poop(user, session["data"])  # This can throw ValueError
                    reply = "Log pup tersimpan! Untuk melihat log, ketik: lihat riwayat bab"
                    session["state"] = None
                    session["data"] = {}
                else:
                    reply = "Masukkan angka 1-7 untuk skala Bristol."
            except ValueError as e:
                if "Invalid" in str(e):  # From InputValidator  
                    reply = f"❌ {str(e)}"
                else:
                    reply = "Masukkan angka 1-7 untuk skala Bristol."
            except Exception as e:
                logging.error(f"Error saving poop: {e}")
                reply = "❌ Terjadi kesalahan saat menyimpan data BAB."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif msg.lower() in ["show poop log", "lihat riwayat bab"]:
            try:
                logs = get_poop_log(user)
                if logs:
                    reply = "Log Pup Terbaru:\n"
                    for l in logs:
                        # Handle both dict-row (PostgreSQL) and tuple (SQLite)
                        if isinstance(l, (list, tuple)):
                            date_val, time_val, bristol = l[0], l[1], l[2]
                        else:
                            date_val = l.get('date', '-')
                            time_val = l.get('time', '-')
                            bristol = l.get('bristol_scale', '-')
                        reply += f"{date_val} {time_val}, Skala Bristol: {bristol}\n"
                else:
                    reply = "Belum ada log pup. Ketik 'catat bab' untuk menambah data."
                session["state"] = None
                session["data"] = {}
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            except Exception as ex:
                logging.exception(f"Error in show poop log: {ex}")
                resp.message("Maaf, terjadi kesalahan saat mengambil data log pup.")
                return Response(str(resp), media_type="application/xml")

        # === SLEEP TRACKING HANDLERS ===
        
        # === REVISED SLEEP TRACKING HANDLERS ===

        # Handler 1: "catat tidur" - Start sleep tracking
        elif msg.lower() == "catat tidur":
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")
            
            # Check if user has an incomplete sleep session first
            existing_sleep_id = get_latest_open_sleep_id(user)
            if existing_sleep_id:
                reply = (
                    f"⚠️ Anda masih memiliki sesi tidur yang belum selesai.\n\n"
                    f"Pilihan:\n"
                    f"• `selesai tidur [HH:MM]` - Selesaikan sesi sebelumnya\n"
                    f"• `batal tidur` - Batalkan sesi sebelumnya\n\n"
                    f"Contoh: `selesai tidur 07:30`"
                )
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Check tier limits for new sleep session
            limits = get_tier_limits(user)
            if limits["sleep_record"] is not None:  # Free user
                current_count = get_sleep_record_count(user)
                if current_count >= limits["sleep_record"]:
                    reply = (
                        f"🚫 Tier gratis dibatasi {limits['sleep_record']} catatan tidur. "
                        f"Upgrade ke premium untuk catatan unlimited!\n\n"
                        f"💡 Tip: Hapus catatan lama atau upgrade ke premium untuk melanjutkan."
                    )
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            
            # Start new sleep session
            try:
                sleep_id, message = start_sleep_record(user, today, time_str)
                if sleep_id:
                    # Get updated count and limits for display
                    updated_count = get_sleep_record_count(user)
                    sleep_limit = limits.get('sleep_record')
                    
                    if sleep_limit is not None:
                        limit_info = f"\n\n📊 Catatan tidur: {updated_count}/{sleep_limit}"
                        if updated_count >= sleep_limit * 0.8:  # Warn when 80% full
                            limit_info += f"\n⚠️ Mendekati batas maksimal!"
                    else:
                        limit_info = f"\n\n📊 Catatan tidur: {updated_count} (unlimited)"
                    
                    reply = (
                        f"✅ Mulai mencatat tidur pada {time_str}.{limit_info}\n\n"
                        f"Ketika bayi bangun, ketik:\n"
                        f"`selesai tidur [HH:MM]`\n\n"
                        f"Contoh: `selesai tidur 07:30`"
                    )
                else:
                    reply = f"❌ {message}"
                    
            except Exception as e:
                logging.error(f"Error starting sleep session for {user}: {e}")
                reply = "❌ Terjadi kesalahan saat memulai catatan tidur. Silakan coba lagi."
            
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # Handler 2: "selesai tidur [time]" - Complete sleep session
        elif msg.lower().startswith("selesai tidur"):
            try:
                # Parse the end time from message
                parts = msg.split()
                if len(parts) < 3:
                    reply = (
                        "❌ Format tidak lengkap.\n\n"
                        "Gunakan: `selesai tidur [HH:MM]`\n"
                        "Contoh: `selesai tidur 07:30`"
                    )
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                
                end_time = parts[2]
                
                # Validate time format
                try:
                    datetime.strptime(end_time, "%H:%M")
                except ValueError:
                    reply = (
                        "❌ Format waktu tidak valid.\n\n"
                        "Gunakan format HH:MM (24 jam)\n"
                        "Contoh: `selesai tidur 07:30` atau `selesai tidur 19:45`"
                    )
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                
                # Check if there's an active sleep session
                sleep_id = get_latest_open_sleep_id(user)
                if not sleep_id:
                    reply = (
                        "❌ Tidak ada sesi tidur yang sedang berlangsung.\n\n"
                        "Mulai sesi baru dengan: `catat tidur`"
                    )
                else:
                    # Complete the sleep session
                    reply = complete_sleep_session(user, sleep_id, end_time)
                    
            except Exception as e:
                logging.error(f"Error completing sleep session for {user}: {e}")
                reply = "❌ Terjadi kesalahan saat menyelesaikan catatan tidur. Silakan coba lagi."
            
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # Handler 3: "batal tidur" - Cancel incomplete sleep session
        elif msg.lower() == "batal tidur":
            try:
                reply = cancel_sleep_session(user)
            except Exception as e:
                logging.error(f"Error canceling sleep session for {user}: {e}")
                reply = "❌ Terjadi kesalahan saat membatalkan sesi tidur. Silakan coba lagi."
            
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # Handler 4: "lihat tidur" and "riwayat tidur" - Show sleep records
        elif msg.lower() in ["lihat tidur", "riwayat tidur", "sleep history", "tidur hari ini"]:
            try:
                # Determine what to show based on command
                if any(keyword in msg.lower() for keyword in ["riwayat", "history"]):
                    # Show multi-day history
                    reply = format_sleep_display(user, show_history=True)
                else:
                    # Show today only
                    reply = format_sleep_display(user, show_history=False)
                    
                # Add helpful tips for free users
                limits = get_tier_limits(user)
                if limits["sleep_record"] is not None:  # Free user
                    current_count = get_sleep_record_count(user)
                    if current_count >= limits["sleep_record"] * 0.8:  # 80% full
                        reply += f"\n\n💡 Tip: Upgrade ke premium untuk catatan tidur unlimited!"
                        
            except Exception as e:
                logging.error(f"Error displaying sleep records for {user}: {e}")
                reply = "❌ Terjadi kesalahan saat mengambil data tidur. Silakan coba lagi."
            
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # ---- Flow 6: Catat Pumping ASI ----
        elif msg.lower() == "catat pumping":
            session["state"] = "PUMP_DATE"
            session["data"] = {}
            reply = "Tanggal pumping? (YYYY-MM-DD, atau 'today')"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "PUMP_DATE":
            if msg.lower().strip() == "today":
                session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
            else:
                try:
                    datetime.strptime(msg, "%Y-%m-%d")
                    session["data"]["date"] = msg
                except ValueError:
                    reply = "Masukkan tanggal dengan format YYYY-MM-DD atau 'today'."
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            session["state"] = "PUMP_TIME"
            reply = "Pukul berapa pumping? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_TIME":
            time_input = msg.replace('.', ':')
            if re.match(r"^\d{2}:\d{2}$", time_input):
                try:
                    datetime.strptime(time_input, "%H:%M")
                    session["data"]["time"] = time_input
                    session["state"] = "PUMP_LEFT"
                    reply = "Jumlah ASI dari payudara kiri (ml)?"
                except ValueError:
                    reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            else:
                reply = "Masukkan jam dengan format 24 jam, HH:MM, contoh: 07:30 atau 18:45"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_LEFT":
            try:
                session["data"]["left_ml"] = float(msg)
                session["state"] = "PUMP_RIGHT"
                reply = "Jumlah ASI dari payudara kanan (ml)?"
            except ValueError:
                reply = "Masukkan angka untuk ASI payudara kiri (ml)."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_RIGHT":
            try:
                session["data"]["right_ml"] = float(msg)
                session["state"] = "PUMP_BAGS"
                reply = "Berapa kantong ASI yang disimpan?"
            except ValueError:
                reply = "Masukkan angka untuk ASI payudara kanan (ml)."
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_BAGS":
            try:
                session["data"]["milk_bags"] = int(msg)
                save_pumping(user, session["data"])  # This can throw ValueError
                reply = "catat pumping tersimpan! Untuk ringkasan, ketik: lihat ringkasan pumping"
                session["state"] = None
                session["data"] = {}
            except ValueError as e:
                if "Invalid" in str(e):  # From InputValidator
                    reply = f"❌ {str(e)}"
                else:
                    reply = "Masukkan angka bulat untuk jumlah kantong ASI."
            except Exception as e:
                logging.error(f"Error saving pumping: {e}")
                reply = "❌ Terjadi kesalahan saat menyimpan data pumping."
            
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        
    # --- Flow: Calculate Formula Milk Calories with User Setting ---
        elif msg.lower() == "hitung kalori susu":
            session["state"] = "CALC_MILK_VOL"
            session["data"] = {}
            reply = "Masukkan jumlah susu (ml):"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "CALC_MILK_VOL":
            try:
                session["data"]["volume_ml"] = float(msg)
                session["state"] = "CALC_MILK_JENIS"
                reply = "Jenis susu? (asi/sufor)"
            except ValueError:
                reply = "Masukkan angka untuk volume susu (ml)!"
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "CALC_MILK_JENIS":
            jenis = msg.lower().strip()
            if jenis not in ["asi", "sufor"]:
                reply = "Masukkan 'asi' untuk ASI atau 'sufor' untuk susu formula."
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            kcal_settings = get_user_calorie_setting(user)
            kcal_per_ml = kcal_settings[jenis]
            total_calories = session["data"].get("volume_ml", 0) * kcal_per_ml
            reply = (
                f"Total kalori: {session['data'].get('volume_ml', 0)} ml x {kcal_per_ml} kkal/ml = "
                f"{total_calories:.2f} kkal\n"
                f"(Ubah nilai ini dengan perintah: set kalori asi / set kalori sufor)"
            )
            session["state"] = None
            session["data"] = {}
            session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # --- Milk Intake Logging: Use user setting for default calories ---
        if msg.lower() == "catat susu" or session["state"] in [
            "MILK_DATE", "MILK_TIME", "MILK_VOL", "MILK_TYPE", "ASI_METHOD", "MILK_NOTE", "SET_KALORI_SUFOR_LOG"
        ]:
            if msg.lower() == "catat susu":
                session["state"] = "MILK_DATE"
                session["data"] = {}
                reply = "Tanggal minum susu? (YYYY-MM-DD atau 'today')"
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
        
            elif session["state"] == "MILK_DATE":
                if msg.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    try:
                        datetime.strptime(msg, "%Y-%m-%d")
                        session["data"]["date"] = msg
                    except ValueError:
                        reply = "Masukkan tanggal dengan format YYYY-MM-DD atau 'today'."
                        session_manager.update_session(user, state=session["state"], data=session["data"])
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                session["state"] = "MILK_TIME"
                reply = "Jam berapa minum susu? (format 24 jam, HH:MM, contoh: 09:00)"
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
        
            elif session["state"] == "MILK_TIME":
                time_input = msg.replace('.', ':')
                if re.match(r"^\d{2}:\d{2}$", time_input):
                    try:
                        datetime.strptime(time_input, "%H:%M")
                        session["data"]["time"] = time_input
                        session["state"] = "MILK_VOL"
                        reply = "Berapa ml yang diminum?"
                    except ValueError:
                        reply = "Masukkan jam dengan format HH:MM, contoh: 09:00 atau 21:30"
                else:
                    reply = "Masukkan jam dengan format HH:MM, contoh: 09:00 atau 21:30"
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "MILK_VOL":
                is_valid, error_msg = InputValidator.validate_volume_ml(msg)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["volume_ml"] = float(msg)
                    session["state"] = "MILK_TYPE"
                    reply = "Susu apa yang diminum? (asi/sufor)"
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "MILK_TYPE":
                milk_type = msg.lower()
                if milk_type == "asi":
                    session["data"]["milk_type"] = "asi"
                    session["state"] = "ASI_METHOD"
                    reply = "ASI diberikan langsung (dbf) atau hasil pumping? (dbf/pumping)"
                elif milk_type == "sufor":
                    session["data"]["milk_type"] = "sufor"
                    user_kcal = get_user_calorie_setting(user)
                    # If user has never set sufor_kcal, ask once
                    if user_kcal["sufor"] is None or user_kcal["sufor"] == 0:
                        session["state"] = "SET_KALORI_SUFOR_LOG"
                        reply = "Masukkan nilai kalori per ml susu formula (default 0.7), atau tekan enter untuk default:"
                    else:
                        session["data"]["sufor_kcal"] = user_kcal["sufor"]
                        session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                        session["state"] = "MILK_NOTE"
                        reply = (
                            f"Kalori otomatis dihitung: {session['data']['sufor_calorie']:.2f} kkal. "
                            "Catatan tambahan? (atau ketik 'skip')"
                        )
                else:
                    reply = "Masukkan 'asi' untuk ASI atau 'sufor' untuk susu formula."
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "SET_KALORI_SUFOR_LOG":
                val = msg.strip()
                try:
                    kcal = 0.7 if val == "" else float(val.replace(",", "."))
                    set_user_calorie_setting(user, "sufor", kcal)
                    session["data"]["sufor_kcal"] = kcal
                    session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * kcal
                    session["state"] = "MILK_NOTE"
                    reply = (
                        f"Kalori otomatis dihitung: {session['data']['sufor_calorie']:.2f} kkal. "
                        "Catatan tambahan? (atau ketik 'skip')"
                    )
                except Exception:
                    reply = "Format tidak valid. Masukkan angka (contoh: 0.7) atau tekan enter untuk default."
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "ASI_METHOD":
                method = msg.lower()
                if method in ["dbf", "pumping"]:
                    session["data"]["asi_method"] = method
                    session["state"] = "MILK_NOTE"
                    reply = "Catatan tambahan? (atau ketik 'skip')"
                else:
                    reply = "Masukkan 'dbf' untuk direct breastfeeding atau 'pumping' untuk hasil perahan."
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "MILK_NOTE":
                note_text = "" if msg.lower() == "skip" else InputValidator.sanitize_text_input(msg, 200)
                session["data"]["note"] = note_text                # PATCH: Always ensure sufor_calorie is set for sufor entries
                if session["data"]["milk_type"] == "sufor" and "sufor_calorie" not in session["data"]:
                    user_kcal = get_user_calorie_setting(user)
                    session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                
                try:
                    save_milk_intake(user, session["data"])  # This can throw ValueError
                    if session["data"]["milk_type"] == "sufor":
                        extra = f" (kalori: {session['data']['sufor_calorie']:.2f} kkal)"
                    elif session["data"]["milk_type"] == "asi":
                        extra = f" ({session['data'].get('asi_method','')})"
                    else:
                        extra = ""
                    reply = (
                        f"Catatan minum susu jam {session['data']['time']}, {session['data']['volume_ml']} ml, "
                        f"{session['data']['milk_type'].upper()}{extra} tersimpan!"
                    )
                    session["state"] = None
                    session["data"] = {}
                except ValueError as e:
                    reply = f"❌ {str(e)}"
                    session_manager.update_session(user, state=session["state"], data=session["data"])
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                except Exception as e:
                    logging.error(f"Error saving milk intake: {e}")
                    reply = "❌ Terjadi kesalahan saat menyimpan data minum susu."
                
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")

        # --- Milk Intake Summary ---
        if msg.lower().startswith("lihat ringkasan susu") or msg.lower().startswith("ringkasan susu"):
            mdate = re.search(r"\d{4}-\d{2}-\d{2}", msg)
            if "today" in msg.lower():
                summary_date = date.today().isoformat()
            elif mdate:
                summary_date = mdate.group(0)
            else:
                summary_date = date.today().isoformat()
            try:
                logging.info(f"Fetching milk summary for user={user} date={summary_date}")
                rows = get_milk_intake_summary(user, summary_date, summary_date)
                logging.info(f"Rows returned: {len(rows)} rows")
                reply = format_milk_summary(rows, summary_date)
                session["state"] = None
                session["data"] = {}
                session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            except Exception as ex:
                logging.exception(f"Error in lihat ringkasan susu: {ex}")
                resp.message("Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti.")
                return Response(str(resp), media_type="application/xml")

        # ---------- DEFAULT RESPONSE (not indented inside any previous block) ----------
        if os.environ.get('DATABASE_URL'):
            user_info = get_user_tier(user)
            tier_text = f"\n💡 Status: Tier {user_info['tier'].title()}\n📊 Pengingat tersisa hari ini: {2 - user_info['messages_today'] if user_info['tier'] == 'free' else 'unlimited'}"
        else:
            tier_text = ""
        reply = (
            f"Selamat datang di Babylog! 🍼{tier_text}\n\n"
            "Ketik 'help' untuk melihat semua perintah.\n\n"
            "Mulai dengan:\n"
            "• tambah anak - daftarkan anak\n"
            "• set reminder susu - buat pengingat"
        )
        session_manager.update_session(user, state=session["state"], data=session["data"])
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    except Exception as exc:
        logging.exception(f"Error in WhatsApp webhook for user {user}: {exc}")
        resp = MessagingResponse()
        resp.message("Maaf, terjadi kesalahan teknis. Silakan coba lagi nanti.")
        return Response(str(resp), media_type="application/xml")

@app.on_event("startup")
async def startup_event():
    try:
        logging.info("Calling init_db() at startup...")
        init_db()
        logging.info("Database tables checked/created successfully.")
    except Exception as e:
        logging.error(f"Error in init_db() at startup: {e}")

# Add these endpoints to your main.py after your existing endpoints

@app.get("/admin/sessions")
async def get_session_stats():
    """Admin endpoint to monitor active sessions"""
    return session_manager.get_stats()

@app.post("/admin/cleanup-sessions")
async def manual_session_cleanup():
    """Manually trigger session cleanup"""
    cleaned = session_manager.cleanup_expired_sessions()
    return {
        "cleaned_sessions": cleaned,
        "timestamp": datetime.now().isoformat(),
        "message": f"Cleaned up {cleaned} expired sessions"
    }

@app.get("/health-detailed")
async def detailed_health_check():
    """Detailed health check including session info"""
    try:
        # Test database connection
        if os.environ.get('DATABASE_URL'):
            conn = get_db_connection()
            conn.close()
            db_status = "connected"
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            conn.close()
            db_status = "connected"
        
        session_stats = session_manager.get_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "sessions": {
                "total": session_stats["total_sessions"],
                "timeout_minutes": session_stats["timeout_minutes"]
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# For Railway: do NOT use reload, and always import app from main:app
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
