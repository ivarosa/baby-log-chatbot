from datetime import datetime, timedelta
import logging

def init_sleep_table(database_url):
    """Create sleep_log table if it doesn't exist"""
    if database_url:
        query = '''CREATE TABLE IF NOT EXISTS sleep_log (
            id SERIAL PRIMARY KEY,
            user_phone TEXT,
            date DATE,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            is_complete BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    else:
        query = '''CREATE TABLE IF NOT EXISTS sleep_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            date DATE,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            is_complete BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )'''
    
    # Execute this in your init_db function
    return query

def start_sleep_record(user, date, start_time):
    """Start a new sleep session"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                INSERT INTO sleep_log ({user_col}, date, start_time, is_complete)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (user, date, start_time, False))
            sleep_id = c.fetchone()['id']
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                INSERT INTO sleep_log ({user_col}, date, start_time, is_complete)
                VALUES (?, ?, ?, ?)
            ''', (user, date, start_time, 0))
            sleep_id = c.lastrowid
            conn.commit()
            conn.close()
        
        return sleep_id
    except Exception as e:
        logging.error(f"Error starting sleep record: {e}")
        return None

def get_latest_open_sleep_id(user):
    """Get the most recent incomplete sleep session"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                SELECT id FROM sleep_log 
                WHERE {user_col}=%s AND is_complete=FALSE
                ORDER BY created_at DESC LIMIT 1
            ''', (user,))
            result = c.fetchone()
            conn.close()
            return result['id'] if result else None
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                SELECT id FROM sleep_log 
                WHERE {user_col}=? AND is_complete=0
                ORDER BY created_at DESC LIMIT 1
            ''', (user,))
            result = c.fetchone()
            conn.close()
            return result[0] if result else None
    except Exception as e:
        logging.error(f"Error getting latest sleep session: {e}")
        return None

def get_sleep_by_id(sleep_id):
    """Get sleep record by ID"""
    database_url = os.environ.get('DATABASE_URL')
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM sleep_log WHERE id=%s', (sleep_id,))
            result = c.fetchone()
            conn.close()
            return result
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute('SELECT * FROM sleep_log WHERE id=?', (sleep_id,))
            result = c.fetchone()
            conn.close()
            if result:
                # Convert tuple to dict for consistency
                return {
                    'id': result[0],
                    'user': result[1],
                    'date': result[2],
                    'start_time': result[3],
                    'end_time': result[4],
                    'duration_minutes': result[5],
                    'is_complete': result[6]
                }
            return None
    except Exception as e:
        logging.error(f"Error getting sleep by ID: {e}")
        return None

def update_sleep_record(sleep_id, end_time, duration_minutes):
    """Complete a sleep session"""
    database_url = os.environ.get('DATABASE_URL')
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''
                UPDATE sleep_log 
                SET end_time=%s, duration_minutes=%s, is_complete=TRUE
                WHERE id=%s
            ''', (end_time, duration_minutes, sleep_id))
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute('''
                UPDATE sleep_log 
                SET end_time=?, duration_minutes=?, is_complete=1
                WHERE id=?
            ''', (end_time, duration_minutes, sleep_id))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        logging.error(f"Error updating sleep record: {e}")
        return False

def get_sleep_summary(user, date):
    """Get all sleep sessions for a specific date"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                SELECT start_time, end_time, duration_minutes 
                FROM sleep_log 
                WHERE {user_col}=%s AND date=%s AND is_complete=TRUE
                ORDER BY start_time
            ''', (user, date))
            results = c.fetchall()
            conn.close()
            return [(r['start_time'], r['end_time'], r['duration_minutes']) for r in results]
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                SELECT start_time, end_time, duration_minutes 
                FROM sleep_log 
                WHERE {user_col}=? AND date=? AND is_complete=1
                ORDER BY start_time
            ''', (user, date))
            results = c.fetchall()
            conn.close()
            return results
    except Exception as e:
        logging.error(f"Error getting sleep summary: {e}")
        return []
