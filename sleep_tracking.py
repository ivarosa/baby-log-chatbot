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

def get_sleep_record_count(user):
    """Get the total number of completed sleep records for a user"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                SELECT COUNT(*) as count FROM sleep_log 
                WHERE {user_col}=%s AND is_complete=TRUE
            ''', (user,))
            result = c.fetchone()
            conn.close()
            return result['count']
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                SELECT COUNT(*) FROM sleep_log 
                WHERE {user_col}=? AND is_complete=1
            ''', (user,))
            result = c.fetchone()
            conn.close()
            return result[0]
    except Exception as e:
        logging.error(f"Error getting sleep record count: {e}")
        return 0

def can_create_sleep_record(user):
    """Check if user can create a new sleep record based on their tier"""
    try:
        limits = get_tier_limits(user)
        sleep_limit = limits.get('sleep_record')
        
        # Premium users have unlimited records
        if sleep_limit is None:
            return True, "Unlimited records for premium users"
        
        # Check current count for free users
        current_count = get_sleep_record_count(user)
        if current_count >= sleep_limit:
            return False, f"Sleep record limit reached ({current_count}/{sleep_limit}). Upgrade to premium for unlimited records."
        
        return True, f"Can create record ({current_count + 1}/{sleep_limit})"
        
    except Exception as e:
        logging.error(f"Error checking sleep record limits: {e}")
        return False, "Error checking limits"

def start_sleep_record(user, date, start_time):
    """Start a new sleep session with tier limit checking"""
    # Check if user can create new record
    can_create, message = can_create_sleep_record(user)
    if not can_create:
        return None, message
    
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
        
        return sleep_id, "Sleep session started successfully"
    except Exception as e:
        logging.error(f"Error starting sleep record: {e}")
        return None, f"Error starting sleep record: {e}"

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

def get_sleep_records_with_limit(user, limit=None):
    """Get sleep records for user with optional limit for display purposes"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        # Get user's tier limits
        limits = get_tier_limits(user)
        display_limit = limits.get('sleep_record') if limits.get('sleep_record') is not None else limit
        
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            query = f'''
                SELECT * FROM sleep_log 
                WHERE {user_col}=%s AND is_complete=TRUE
                ORDER BY date DESC, start_time DESC
            '''
            params = [user]
            
            if display_limit:
                query += ' LIMIT %s'
                params.append(display_limit)
                
            c.execute(query, params)
            results = c.fetchall()
            conn.close()
            return results
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            query = f'''
                SELECT * FROM sleep_log 
                WHERE {user_col}=? AND is_complete=1
                ORDER BY date DESC, start_time DESC
            '''
            params = [user]
            
            if display_limit:
                query += ' LIMIT ?'
                params.append(display_limit)
                
            c.execute(query, params)
            results = c.fetchall()
            conn.close()
            
            # Convert to dict format for consistency
            if results:
                return [{
                    'id': r[0],
                    'user': r[1],
                    'date': r[2],
                    'start_time': r[3],
                    'end_time': r[4],
                    'duration_minutes': r[5],
                    'is_complete': r[6],
                    'created_at': r[7]
                } for r in results]
            return []
    except Exception as e:
        logging.error(f"Error getting sleep records: {e}")
        return []

def delete_oldest_sleep_record(user):
    """Delete the oldest sleep record for a user (helper function for cleanup)"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    try:
        if database_url:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(f'''
                DELETE FROM sleep_log 
                WHERE id = (
                    SELECT id FROM sleep_log 
                    WHERE {user_col}=%s AND is_complete=TRUE
                    ORDER BY created_at ASC 
                    LIMIT 1
                )
            ''', (user,))
            conn.commit()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect('babylog.db')
            c = conn.cursor()
            c.execute(f'''
                DELETE FROM sleep_log 
                WHERE id = (
                    SELECT id FROM sleep_log 
                    WHERE {user_col}=? AND is_complete=1
                    ORDER BY created_at ASC 
                    LIMIT 1
                )
            ''', (user,))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        logging.error(f"Error deleting oldest sleep record: {e}")
        return False
