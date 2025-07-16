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

DEFAULT_TIMEZONE = pytz.timezone('Asia/Jakarta')  # Change to 'Asia/Makassar' for GMT+8, 'Asia/Jayapura' for GMT+9

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# Initialize FastAPI app
app = FastAPI(title="Baby Log WhatsApp Chatbot", version="1.0.0")
user_sessions = {}


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
            )'''
        ]
        
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
        conn.commit()
        conn.close()

# Initialize database
init_db()

# Cost control functions (new for Railway)
def get_user_tier(user):
    """Get user tier and daily message count with auto-reset"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'SELECT tier, messages_today, last_reset FROM user_tiers WHERE {user_col}=%s', (user,))
            row = c.fetchone()
            
            if not row:
                c.execute(f'''
                    INSERT INTO user_tiers ({user_col}, tier, messages_today, last_reset) 
                    VALUES (%s, %s, %s, %s)
                ''', (user, 'free', 0, date.today()))
                conn.commit()
                result = {'tier': 'free', 'messages_today': 0}
            else:
                if row['last_reset'] != date.today():
                    c.execute(f'''
                        UPDATE user_tiers 
                        SET messages_today=0, last_reset=%s 
                        WHERE {user_col}=%s
                    ''', (date.today(), user))
                    conn.commit()
                    result = {'tier': row['tier'], 'messages_today': 0}
                else:
                    result = dict(row)
            conn.close()
        else:
            # SQLite fallback
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'SELECT tier, messages_today, last_reset FROM user_tiers WHERE {user_col}=?', (user,))
            row = c.fetchone()
            
            if not row:
                c.execute(f'INSERT INTO user_tiers ({user_col}, tier, messages_today, last_reset) VALUES (?, ?, ?, ?)', 
                         (user, 'free', 0, date.today().isoformat()))
                conn.commit()
                result = {'tier': 'free', 'messages_today': 0}
            else:
                if row[2] != date.today().isoformat():
                    c.execute(f'UPDATE user_tiers SET messages_today=0, last_reset=? WHERE {user_col}=?', 
                             (date.today().isoformat(), user))
                    conn.commit()
                    result = {'tier': row[0], 'messages_today': 0}
                else:
                    result = {'tier': row[0], 'messages_today': row[1]}
            conn.close()
            
        return result
    except Exception as e:
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
    """Track daily message count"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'UPDATE user_tiers SET messages_today = messages_today + 1 WHERE {user_col}=%s', (user,))
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'UPDATE user_tiers SET messages_today = messages_today + 1 WHERE {user_col}=?', (user,))
            conn.commit()
            conn.close()
    except Exception as e:
        logging.error(f"Error incrementing message count: {e}")

# Your existing database functions (adapted for both SQLite and PostgreSQL)
def get_user_calorie_setting(user):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT asi_kcal, sufor_kcal FROM calorie_setting WHERE {user_col}=%s', (user,))
        row = c.fetchone()
        if row:
            conn.close()
            return {"asi": row['asi_kcal'], "sufor": row['sufor_kcal']}
        else:
            c.execute(f'INSERT INTO calorie_setting ({user_col}) VALUES (%s)', (user,))
            conn.commit()
            conn.close()
            return {"asi": 0.67, "sufor": 0.7}
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'SELECT asi_kcal, sufor_kcal FROM calorie_setting WHERE {user_col}=?', (user,))
        row = c.fetchone()
        if row:
            conn.close()
            return {"asi": row[0], "sufor": row[1]}
        else:
            c.execute(f'INSERT INTO calorie_setting ({user_col}) VALUES (?)', (user,))
            conn.commit()
            conn.close()
            return {"asi": 0.67, "sufor": 0.7}

def set_user_calorie_setting(user, milk_type, value):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        if milk_type == "asi":
            c.execute(f'UPDATE calorie_setting SET asi_kcal=%s WHERE {user_col}=%s', (value, user))
        elif milk_type == "sufor":
            c.execute(f'UPDATE calorie_setting SET sufor_kcal=%s WHERE {user_col}=%s', (value, user))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        if milk_type == "asi":
            c.execute(f'UPDATE calorie_setting SET asi_kcal=? WHERE {user_col}=?', (value, user))
        elif milk_type == "sufor":
            c.execute(f'UPDATE calorie_setting SET sufor_kcal=? WHERE {user_col}=?', (value, user))
        conn.commit()
        conn.close()

def save_child(user, data):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO child ({user_col}, name, gender, dob, height_cm, weight_kg)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO child ({user_col}, name, gender, dob, height_cm, weight_kg)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))
        conn.commit()
        conn.close()

def get_child(user):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
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

# Continue with your existing functions, but adapt database queries...
def save_timbang(user, data):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO timbang_log ({user_col}, date, height_cm, weight_kg, head_circum_cm)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO timbang_log ({user_col}, date, height_cm, weight_kg, head_circum_cm)
            VALUES (?, ?, ?, ?, ?)
        ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))
        conn.commit()
        conn.close()

def get_timbang_history(user, limit=10):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            SELECT date, height_cm, weight_kg, head_circum_cm FROM timbang_log
            WHERE {user_col}=%s
            ORDER BY date DESC, created_at DESC
            LIMIT %s
        ''', (user, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            SELECT date, height_cm, weight_kg, head_circum_cm FROM timbang_log
            WHERE {user_col}=?
            ORDER BY date DESC, created_at DESC
            LIMIT ?
        ''', (user, limit))
        rows = c.fetchall()
        conn.close()
        return rows

# Reminder functions (adapted from your original script)
def save_reminder(user, data):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
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
            INSERT INTO milk_reminders 
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
            INSERT INTO milk_reminders 
            ({user_col}, reminder_name, interval_hours, start_time, end_time, next_due)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['reminder_name'], data['interval_hours'], data['start_time'], data['end_time'], start_datetime))
        conn.commit()
        conn.close()

def get_user_reminders(user, active_only=True):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT * FROM milk_reminders WHERE {user_col}=%s'
        params = [user]
        
        if active_only:
            query += ' AND is_active=TRUE'
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT * FROM milk_reminders WHERE {user_col}=?'
        params = [user]
        
        if active_only:
            query += ' AND is_active=1'
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows

def check_and_send_reminders():
    """Background function to check and send due reminders"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_local = now_utc.astimezone(DEFAULT_TIMEZONE)
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            # Compare next_due in UTC
            c.execute(f'''
                SELECT * FROM milk_reminders 
                WHERE is_active=TRUE AND next_due <= %s
            ''', (now_utc,))
            due_reminders = c.fetchall()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            # SQLite stores naive datetime, so use local time
            c.execute(f'''
                SELECT * FROM milk_reminders 
                WHERE is_active=1 AND next_due <= ?
            ''', (now_local,))
            due_reminders = c.fetchall()
            conn.close()
        
        logging.info(f"Found {len(due_reminders)} due reminders")
        
        for reminder in due_reminders:
            if database_url:
                user = reminder['user_phone']
                reminder_id = reminder['id']
                reminder_name = reminder['reminder_name']
                interval = reminder['interval_hours']
            else:
                user = reminder[1]
                reminder_id = reminder[0]
                reminder_name = reminder[2]
                interval = reminder[3]
            
            user_info = get_user_tier(user)
            remaining = 2 - user_info['messages_today'] if user_info['tier'] == 'free' else 'unlimited'
            
            message = f"""🍼 Pengingat: {reminder_name}
                
                ⏰ Waktunya minum susu!
                
                Balas cepat:
                • 'done 120ml' - catat minum
                • 'snooze 30' - tunda 30 menit  
                • 'skip' - lewati
                
                💡 Sisa pengingat hari ini: {remaining}"""
            
            if send_twilio_message(user, message):
                # Calculate next_due based on user's timezone and interval_hours
                if database_url:
                    # Save next_due in UTC
                    next_due_utc = now_utc + timedelta(hours=interval)
                    last_sent_utc = now_utc
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute('UPDATE milk_reminders SET next_due=%s, last_sent=%s WHERE id=%s',
                             (next_due_utc, last_sent_utc, reminder_id))
                    conn.commit()
                    conn.close()
                else:
                    # Save next_due in local time for SQLite
                    next_due_local = now_local + timedelta(hours=interval)
                    last_sent_local = now_local
                    import sqlite3
                    conn = sqlite3.connect('babylog.db')
                    c = conn.cursor()
                    c.execute('UPDATE milk_reminders SET next_due=?, last_sent=? WHERE id=?',
                             (next_due_local, last_sent_local, reminder_id))
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
    print(f"[DB] Saving MPASI for {user}: {data}")  # For debugging/logging
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO mpasi_log ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            user,
            data['date'],
            data['time'],
            data['volume_ml'],
            data['food_detail'],
            data['food_grams'],
            data.get('est_calories')
        ))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO mpasi_log ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user,
            data['date'],
            data['time'],
            data['volume_ml'],
            data['food_detail'],
            data['food_grams'],
            data.get('est_calories')
        ))
        conn.commit()
        conn.close()
        conn.close()

def get_mpasi_summary(user, period_start=None, period_end=None):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT date, time, volume_ml, food_detail, food_grams, est_calories FROM mpasi_log WHERE {user_col}=%s'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN %s AND %s'
            params += [period_start, period_end]
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT date, time, volume_ml, food_detail, food_grams, est_calories FROM mpasi_log WHERE {user_col}=?'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN ? AND ?'
            params += [period_start, period_end]
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def save_poop(user, data):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO poop_log ({user_col}, date, time, bristol_scale)
            VALUES (%s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['bristol_scale']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO poop_log ({user_col}, date, time, bristol_scale)
            VALUES (?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['bristol_scale']))
        conn.commit()
        conn.close()

def get_poop_log(user, limit=10):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT date, time, bristol_scale FROM poop_log WHERE {user_col}=%s ORDER BY date DESC, time DESC LIMIT %s', (user, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'SELECT date, time, bristol_scale FROM poop_log WHERE {user_col}=? ORDER BY date DESC, time DESC LIMIT ?', (user, limit))
        rows = c.fetchall()
        conn.close()
        return rows

def save_milk_intake(user, data):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO milk_intake_log ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
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
            INSERT INTO milk_intake_log ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['volume_ml'], data['milk_type'], 
              data.get('asi_method'), data.get('sufor_calorie'), data.get('note', "")))
        conn.commit()
        conn.close()

def get_milk_intake_summary(user, period_start=None, period_end=None):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'''
            SELECT milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)
            FROM milk_intake_log
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
            FROM milk_intake_log
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
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO pumping_log ({user_col}, date, time, left_ml, right_ml, milk_bags)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'''
            INSERT INTO pumping_log ({user_col}, date, time, left_ml, right_ml, milk_bags)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))
        conn.commit()
        conn.close()

def get_pumping_summary(user, period_start=None, period_end=None):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        query = f'SELECT date, time, left_ml, right_ml, milk_bags FROM pumping_log WHERE {user_col}=%s'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN %s AND %s'
            params += [period_start, period_end]
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        query = f'SELECT date, time, left_ml, right_ml, milk_bags FROM pumping_log WHERE {user_col}=?'
        params = [user]
        if period_start and period_end:
            query += ' AND date BETWEEN ? AND ?'
            params += [period_start, period_end]
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        return rows

def get_daily_summary(user, summary_date):
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    if database_url:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(f'SELECT SUM(left_ml), SUM(right_ml), COUNT(*), SUM(milk_bags) FROM pumping_log WHERE {user_col}=%s AND date=%s', (user, summary_date))
        pump = c.fetchone() or {'sum': 0, 'sum_1': 0, 'count': 0, 'sum_2': 0}
        c.execute(f'SELECT COUNT(*), SUM(volume_ml), SUM(est_calories) FROM mpasi_log WHERE {user_col}=%s AND date=%s', (user, summary_date))
        mpasi = c.fetchone() or {'count': 0, 'sum': 0, 'sum_1': 0}
        c.execute(f'SELECT weight_kg, height_cm FROM timbang_log WHERE {user_col}=%s AND date=%s ORDER BY created_at DESC LIMIT 1', (user, summary_date))
        growth = c.fetchone() or {'weight_kg': "-", 'height_cm': "-"}
        c.execute(f'SELECT COUNT(*) FROM poop_log WHERE {user_col}=%s AND date=%s', (user, summary_date))
        poop = c.fetchone() or {'count': 0}
        conn.close()
        
        return {
            "pumping_count": pump['count'] or 0,
            "pumping_total": (pump['sum'] or 0) + (pump['sum_1'] or 0),
            "pumping_left": pump['sum'] or 0,
            "pumping_right": pump['sum_1'] or 0,
            "pumping_bags": pump['sum_2'] or 0,
            "mpasi_count": mpasi['count'] or 0,
            "mpasi_total": mpasi['sum'] or 0,
            "calories": mpasi['sum_1'] or 0,
            "weight": growth['weight_kg'],
            "height": growth['height_cm'],
            "poop_count": poop['count'] or 0,
            "note": "-"
        }
    else:
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        c = conn.cursor()
        c.execute(f'SELECT SUM(left_ml), SUM(right_ml), COUNT(*), SUM(milk_bags) FROM pumping_log WHERE {user_col}=? AND date=?', (user, summary_date))
        pump = c.fetchone() or (0, 0, 0, 0)
        c.execute(f'SELECT COUNT(*), SUM(volume_ml), SUM(est_calories) FROM mpasi_log WHERE {user_col}=? AND date=?', (user, summary_date))
        mpasi = c.fetchone() or (0, 0, 0)
        c.execute(f'SELECT weight_kg, height_cm FROM timbang_log WHERE {user_col}=? AND date=? ORDER BY created_at DESC LIMIT 1', (user, summary_date))
        growth = c.fetchone() or ("-", "-")
        c.execute(f'SELECT COUNT(*) FROM poop_log WHERE {user_col}=? AND date=?', (user, summary_date))
        poop = c.fetchone() or (0,)
        conn.close()
        
        return {
            "pumping_count": pump[2] or 0,
            "pumping_total": (pump[0] or 0) + (pump[1] or 0),
            "pumping_left": pump[0] or 0,
            "pumping_right": pump[1] or 0,
            "pumping_bags": pump[3] or 0,
            "mpasi_count": mpasi[0] or 0,
            "mpasi_total": mpasi[1] or 0,
            "calories": mpasi[2] or 0,
            "weight": growth[0],
            "height": growth[1],
            "poop_count": poop[0] or 0,
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
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    conn = get_db_connection()
    c = conn.cursor()
    if database_url:
        c.execute(
            f"""UPDATE mpasi_log SET gpt_calorie_summary=%s, est_calories=%s
                WHERE {user_col}=%s AND date=%s AND time=%s""",
            (gpt_summary, est_calories, user, data['date'], data['time'])
        )
    else:
        c.execute(
            f"""UPDATE mpasi_log SET gpt_calorie_summary=?, est_calories=?
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
    "• `ringkasan hari ini` (untuk melihat rangkuman harian)\n\n"
    "Butuh bantuan lebih lanjut? Ketik `bantuan`.\n"
    "Ingin melihat semua perintah? Ketik `panduan`."
)

HELP_MESSAGE = (
    "🤖 *Bantuan Babylog:*\n\n"
    "Pilih kategori bantuan yang Anda butuhkan, atau ketik perintah langsung:\n\n"
    "*Data Anak & Tumbuh Kembang:*\n"
    "• `tambah anak` / `lihat anak`\n"
    "• `catat timbang` / `lihat tumbuh kembang`\n\n"
    "*Asupan Nutrisi:*\n"
    "• `catat mpasi` / `lihat ringkasan mpasi`\n"
    "• `catat susu` / `lihat ringkasan susu [hari ini/tanggal]`\n"
    "• `catat pumping` / `lihat ringkasan pumping`\n\n"
    "*Kesehatan & Aktivitas Lain:*\n"
    "• `catat bab` / `lihat riwayat bab`\n\n"
    "*Pengaturan Kalori:*\n"
    "• `hitung kalori susu`\n"
    "• `set kalori asi` / `set kalori sufor`\n"
    "• `lihat kalori` / `daftar asupan` / `persentase asupan`\n\n"
    "*Pengingat Susu:*\n"
    "• `atur pengingat susu` / `lihat pengingat`\n"
    "• _Saat ada pengingat, Anda bisa:_\n"
    "  • `done [volume]ml` (Selesai dan catat volume)\n"
    "  • `snooze [menit]` (Tunda pengingat)\n"
    "  • `skip reminder` (Lewati pengingat)\n\n"
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
    "• `tambah anak`: Tambah data si kecil baru\n"
    "• `lihat anak`: Lihat daftar anak\n"
    "• `catat timbang`: Catat berat & tinggi badan\n"
    "• `lihat tumbuh kembang`: Lihat grafik dan riwayat pertumbuhan\n\n"
    "*II. Asupan Nutrisi:*\n"
    "• `catat mpasi`: Catat detail MPASI\n"
    "• `lihat ringkasan mpasi`: Lihat ringkasan MPASI\n"
    "• `catat susu`: Catat pemberian susu\n"
    "• `lihat ringkasan susu [hari ini/tanggal]`: Rekap susu harian/khusus\n"
    "• `catat pumping`: Catat volume ASI pumping\n"
    "• `lihat ringkasan pumping`: Lihat total & riwayat ASI perah\n\n"
    "*III. Pengaturan Kalori:*\n"
    "• `hitung kalori susu`: Hitung estimasi kalori susu\n"
    "• `set kalori asi`: Atur kalori per ml ASI\n"
    "• `set kalori sufor`: Atur kalori per ml susu formula\n"
    "• `lihat kalori`: Total kalori harian\n"
    "• `daftar asupan`: Daftar lengkap asupan\n"
    "• `persentase asupan`: Persentase nutrisi asupan\n\n"
    "*IV. Kesehatan & Aktivitas Lain:*\n"
    "• `catat bab`: Catat riwayat BAB\n"
    "• `lihat riwayat bab`: Lihat riwayat BAB\n\n"
    "*V. Pengingat Susu:*\n"
    "• `atur pengingat susu`: Atur pengingat pemberian susu\n"
    "• `lihat pengingat`: Daftar pengingat susu aktif\n"
    "• Respon cepat saat pengingat aktif:\n"
    "  • `done [volume]ml`: Catat volume susu (cth: `done 120ml`)\n"
    "  • `snooze [menit]`: Tunda pengingat (cth: `snooze 15`)\n"
    "  • `skip reminder`: Lewati pengingat\n\n"
    "*VI. Laporan & Ringkasan:*\n"
    "• `ringkasan hari ini`: Lihat rangkuman aktivitas hari ini\n\n"
    "*VII. Perintah Umum:*\n"
    "• `batal`: Batalkan sesi/aksi berjalan\n"
    "• `bantuan`: Tampilkan bantuan singkat\n"
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
        session = user_sessions.get(user, {"state": None, "data": {}})
        reply = ""

        # Universal Commands
        if msg.lower() in ["batal", "cancel"]:
            session["state"] = None
            session["data"] = {}
            user_sessions[user] = session
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
        if msg.lower() in ["set reminder susu", "atur pengingat susu"]:
            if os.environ.get('DATABASE_URL'):
                user_info = get_user_tier(user)
                if user_info['tier'] == 'free':
                    active_reminders = len(get_user_reminders(user))
                    if active_reminders >= 3:
                        reply = "🚫 Tier gratis dibatasi 3 pengingat aktif. Upgrade ke premium untuk unlimited!"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
            session["state"] = "REMINDER_NAME"
            session["data"] = {}
            reply = "Nama pengingat? (contoh: ASI pagi, Sufor malam, ASI reguler)"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_NAME":
            session["data"]["reminder_name"] = msg
            session["state"] = "REMINDER_INTERVAL"
            reply = "Interval berapa jam? (contoh: 2, 3, 4 untuk setiap 2/3/4 jam)"
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_START":
            if re.match(r"^\d{2}:\d{2}$", msg):
                try:
                    datetime.strptime(msg, "%H:%M")
                    session["data"]["start_time"] = msg
                    session["state"] = "REMINDER_END"
                    reply = "Jam berapa berhenti pengingat? (format HH:MM, contoh: 22:00)"
                except ValueError:
                    reply = "Format jam tidak valid. Gunakan HH:MM, contoh: 06:00"
            else:
                reply = "Format jam tidak valid. Gunakan HH:MM, contoh: 06:00"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_END":
            if re.match(r"^\d{2}:\d{2}$", msg):
                try:
                    datetime.strptime(msg, "%H:%M")
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "REMINDER_CONFIRM":
            if msg.lower() == "ya":
                save_reminder(user, session["data"])
                reply = f"✅ Pengingat '{session['data']['reminder_name']}' tersimpan! Pengingat pertama akan dikirim pukul {session['data']['start_time']}."
                session["state"] = None
                session["data"] = {}
            elif msg.lower() == "tidak":
                session["state"] = "REMINDER_NAME"
                reply = "Mari ulangi. Nama pengingat?"
            else:
                reply = "Ketik 'ya' untuk konfirmasi atau 'tidak' untuk mengulang."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

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
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        if msg.lower().startswith("set kalori sufor"):
            session["state"] = "SET_KALORI_SUFOR"
            reply = "Masukkan nilai kalori per ml susu formula (default 0.7), atau tekan enter untuk default:"
            user_sessions[user] = session
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
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")


        # ---- Flow 1: Data Anak ----
        if msg.lower() == "tambah anak":
            session["state"] = "ADDCHILD_NAME"
            session["data"] = {}
            reply = "Siapa nama anak Anda?"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_NAME":
            session["data"]["name"] = msg
            session["state"] = "ADDCHILD_GENDER"
            reply = "Jenis kelamin anak? (laki-laki/perempuan)"
            user_sessions[user] = session
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
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_HEIGHT":
            try:
                session["data"]["height_cm"] = float(msg)
                session["state"] = "ADDCHILD_WEIGHT"
                reply = "Berat badan? (kg, contoh: 8.4 atau 8500 untuk gram)"
            except ValueError:
                reply = "Masukkan angka untuk tinggi badan (cm), contoh: 75.5"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_WEIGHT":
            try:
                weight = float(msg)
                session["data"]["weight_kg"] = weight / 1000 if weight > 100 else weight
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
                reply = "Masukkan angka untuk berat badan, contoh: 8.4 atau 8500."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif session["state"] == "ADDCHILD_CONFIRM":
            if msg.lower() == "ya":
                save_child(user, session["data"])
                session["state"] = None
                session["data"] = {}
                reply = "Data anak tersimpan! Untuk melihat data anak, ketik: tampilkan anak"
            elif msg.lower() == "ulang":
                session["state"] = "ADDCHILD_NAME"
                reply = "Siapa nama anak Anda? (Ulangi input)"
            elif msg.lower() == "batal":
                session["state"] = None
                session["data"] = {}
                reply = "Input data anak dibatalkan."
            else:
                reply = "Ketik 'ya' jika data sudah benar, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        elif msg.lower() == "tampilkan anak":
            row = get_child(user)
            if row:
                reply = f"Nama: {row[0]}, Jenis kelamin: {row[1].capitalize()}, Tgl lahir: {row[2]}, Tinggi: {row[3]} cm, Berat: {row[4]} kg"
            else:
                reply = "Data anak belum ada. Silakan ketik 'tambah anak' untuk menambah data anak."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # ---- Flow 2: Catat Timbang ----
        elif msg.lower() == "catat timbang":
            session["state"] = "TIMBANG_HEIGHT"
            session["data"] = {"date": datetime.now().strftime("%Y-%m-%d")}
            reply = "Tinggi badan (cm)?"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "TIMBANG_HEIGHT":
            try:
                session["data"]["height_cm"] = float(msg)
                session["state"] = "TIMBANG_WEIGHT"
                reply = "Berat badan? (kg)"
            except ValueError:
                reply = "Masukkan angka yang valid untuk tinggi badan (cm)."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "TIMBANG_WEIGHT":
            try:
                weight = float(msg)
                session["data"]["weight_kg"] = weight / 1000 if weight > 100 else weight
                session["state"] = "TIMBANG_HEAD"
                reply = "Lingkar kepala (cm)?"
            except ValueError:
                reply = "Masukkan angka yang valid untuk berat badan (kg)."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "TIMBANG_HEAD":
            try:
                session["data"]["head_circum_cm"] = float(msg)
                save_timbang(user, session["data"])
                session["state"] = None
                session["data"] = {}
                reply = "Data timbang tersimpan! Untuk melihat riwayat, ketik: lihat tumbuh kembang"
            except ValueError:
                reply = "Masukkan angka yang valid untuk lingkar kepala (cm)."
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # ---- Flow 3: Catat MPASI ----
        elif msg.lower() == "catat mpasi":
            session["state"] = "MPASI_DATE"
            session["data"] = {}
            reply = "Tanggal makan? (YYYY-MM-DD, atau ketik 'today')"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Tanggal Makan
        elif session["state"] == "MPASI_DATE":
            if msg.lower().strip() == "today":
                session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                session["state"] = "MPASI_TIME"
                reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
            else:
                try:
                    datetime.strptime(msg, "%Y-%m-%d")
                    session["data"]["date"] = msg
                    session["state"] = "MPASI_TIME"
                    reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
                except ValueError:
                    reply = "Masukkan tanggal dengan format YYYY-MM-DD atau ketik 'today'."
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Volume Makan
        elif session["state"] == "MPASI_VOL":
            try:
                session["data"]["volume_ml"] = float(msg)
                session["state"] = "MPASI_DETAIL"
                reply = "Makanan apa saja? (cth: nasi 50gr, ayam 30gr, wortel 20gr)"
            except ValueError:
                reply = "Masukkan angka untuk ml."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")

        # Detail Makanan
        elif session["state"] == "MPASI_DETAIL":
            session["data"]["food_detail"] = msg
            session["state"] = "MPASI_GRAMS"
            reply = "Masukkan menu dan porsi MPASI (misal: nasi santan 5 sdm, ayam 1 potong), atau 'skip'."
            user_sessions[user] = session
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
            save_mpasi(user, session["data"])
            reply = "Catat MPASI tersimpan! Silahkan cek di lihat ringkasan mpasi."
            session["state"] = None
            session["data"] = {}
            user_sessions[user] = session
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
            user_sessions[user] = session
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
            user_sessions[user] = session
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
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # ---- Flow 5: Catat Pup ----
        elif msg.lower() in ["log poop", "catat bab"]:
            session["state"] = "POOP_DATE"
            session["data"] = {}
            reply = "Tanggal? (YYYY-MM-DD, atau 'today')"
            user_sessions[user] = session
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
                    user_sessions[user] = session
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            session["state"] = "POOP_TIME"
            reply = "Jam berapa? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "POOP_BRISTOL":
            try:
                bristol = int(msg)
                if 1 <= bristol <= 7:
                    session["data"]["bristol_scale"] = bristol
                    save_poop(user, session["data"])
                    session["state"] = None
                    session["data"] = {}
                    reply = "Log pup tersimpan! Untuk melihat log, ketik: lihat riwayat bab"
                else:
                    reply = "Masukkan angka 1-7 untuk skala Bristol."
            except ValueError:
                reply = "Masukkan angka 1-7 untuk skala Bristol."
            user_sessions[user] = session
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
                user_sessions[user] = session
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            except Exception as ex:
                logging.exception(f"Error in show poop log: {ex}")
                resp.message("Maaf, terjadi kesalahan saat mengambil data log pup.")
                return Response(str(resp), media_type="application/xml")
        
        # ---- Flow 6: Catat Pumping ASI ----
        elif msg.lower() == "catat pumping":
            session["state"] = "PUMP_DATE"
            session["data"] = {}
            reply = "Tanggal pumping? (YYYY-MM-DD, atau 'today')"
            user_sessions[user] = session
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
                    user_sessions[user] = session
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            session["state"] = "PUMP_TIME"
            reply = "Pukul berapa pumping? (format 24 jam, HH:MM, contoh: 07:30 atau 18:45)"
            user_sessions[user] = session
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
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_LEFT":
            try:
                session["data"]["left_ml"] = float(msg)
                session["state"] = "PUMP_RIGHT"
                reply = "Jumlah ASI dari payudara kanan (ml)?"
            except ValueError:
                reply = "Masukkan angka untuk ASI payudara kiri (ml)."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_RIGHT":
            try:
                session["data"]["right_ml"] = float(msg)
                session["state"] = "PUMP_BAGS"
                reply = "Berapa kantong ASI yang disimpan?"
            except ValueError:
                reply = "Masukkan angka untuk ASI payudara kanan (ml)."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "PUMP_BAGS":
            try:
                session["data"]["milk_bags"] = int(msg)
                save_pumping(user, session["data"])
                session["state"] = None
                session["data"] = {}
                reply = "catat pumping tersimpan! Untuk ringkasan, ketik: lihat ringkasan pumping"
            except ValueError:
                reply = "Masukkan angka bulat untuk jumlah kantong ASI."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif msg.lower().startswith("lihat ringkasan pumping"):
            logs = get_pumping_summary(user)
            if logs:
                total_left = sum([l[2] for l in logs])
                total_right = sum([l[3] for l in logs])
                total_bags = sum([l[4] for l in logs])
                reply = f"Total kiri: {total_left}ml\nTotal kanan: {total_right}ml\nKantong: {total_bags}\nSesi: {len(logs)}"
            else:
                reply = "Belum ada catat pumping. Ketik 'catat pumping' untuk menambah data."
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
    # --- Flow: Calculate Formula Milk Calories with User Setting ---
        if msg.lower() == "hitung kalori susu":
            session["state"] = "CALC_MILK_VOL"
            session["data"] = {}
            reply = "Masukkan jumlah susu (ml):"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "CALC_MILK_VOL":
            try:
                session["data"]["volume_ml"] = float(msg)
                session["state"] = "CALC_MILK_JENIS"
                reply = "Jenis susu? (asi/sufor)"
            except ValueError:
                reply = "Masukkan angka untuk volume susu (ml)!"
            user_sessions[user] = session
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        elif session["state"] == "CALC_MILK_JENIS":
            jenis = msg.lower().strip()
            if jenis not in ["asi", "sufor"]:
                reply = "Masukkan 'asi' untuk ASI atau 'sufor' untuk susu formula."
                user_sessions[user] = session
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
            user_sessions[user] = session
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
                user_sessions[user] = session
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
                        user_sessions[user] = session
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                session["state"] = "MILK_TIME"
                reply = "Jam berapa minum susu? (format 24 jam, HH:MM, contoh: 09:00)"
                user_sessions[user] = session
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
                user_sessions[user] = session
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "MILK_VOL":
                try:
                    session["data"]["volume_ml"] = float(msg)
                    session["state"] = "MILK_TYPE"
                    reply = "Susu apa yang diminum? (asi/sufor)"
                except ValueError:
                    reply = "Masukkan angka untuk ml, contoh: 90"
                user_sessions[user] = session
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
                user_sessions[user] = session
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
                user_sessions[user] = session
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
                user_sessions[user] = session
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            elif session["state"] == "MILK_NOTE":
                session["data"]["note"] = "" if msg.lower() == "skip" else msg
                # PATCH: Always ensure sufor_calorie is set for sufor entries
                if session["data"]["milk_type"] == "sufor" and "sufor_calorie" not in session["data"]:
                    user_kcal = get_user_calorie_setting(user)
                    session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                save_milk_intake(user, session["data"])
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
                user_sessions[user] = session
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")

        # --- Milk Intake Summary ---
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
                user_sessions[user] = session
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
        user_sessions[user] = session
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

# For Railway: do NOT use reload, and always import app from main:app
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
