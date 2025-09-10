# sleep_tracking.py
"""
Sleep tracking module for baby log application
Handles sleep session management and tracking
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from database_pool import DatabasePool
from database_security import DatabaseSecurity
from error_handler import ErrorHandler, ValidationError, DatabaseError

# Initialize the singleton pool
db_pool = DatabasePool()

@ErrorHandler.handle_database_error
def start_sleep_record(user: str, date: str, start_time: str) -> Tuple[Optional[int], str]:
    """Start a new sleep record"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    # Check if user already has an incomplete sleep session
    existing_id = get_latest_open_sleep_id(user)
    if existing_id:
        return None, "You already have an incomplete sleep session. Complete it first."
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, start_time, is_complete)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (user, date, start_time, False))
            result = c.fetchone()
            sleep_id = result[0] if result else None
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, start_time, is_complete)
                VALUES (?, ?, ?, ?)
            ''', (user, date, start_time, 0))
            sleep_id = c.lastrowid
        
        return sleep_id, "Sleep session started successfully"

@ErrorHandler.handle_database_error
def get_latest_open_sleep_id(user: str) -> Optional[int]:
    """Get the ID of the latest incomplete sleep session"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                SELECT id FROM {table_name} 
                WHERE {user_col}=%s AND is_complete=FALSE 
                ORDER BY created_at DESC LIMIT 1
            ''', (user,))
        else:
            c.execute(f'''
                SELECT id FROM {table_name} 
                WHERE {user_col}=? AND is_complete=0 
                ORDER BY created_at DESC LIMIT 1
            ''', (user,))
        
        result = c.fetchone()
        return result[0] if result else None

@ErrorHandler.handle_database_error
def get_sleep_by_id(sleep_id: int) -> Optional[Dict[str, Any]]:
    """Get sleep record by ID"""
    database_url = os.environ.get('DATABASE_URL')
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                SELECT date, start_time, end_time, duration_minutes, is_complete
                FROM {table_name} WHERE id=%s
            ''', (sleep_id,))
        else:
            c.execute(f'''
                SELECT date, start_time, end_time, duration_minutes, is_complete
                FROM {table_name} WHERE id=?
            ''', (sleep_id,))
        
        result = c.fetchone()
        if result:
            if isinstance(result, dict):  # PostgreSQL
                return result
            else:  # SQLite
                return {
                    'date': result[0],
                    'start_time': result[1],
                    'end_time': result[2],
                    'duration_minutes': result[3],
                    'is_complete': result[4]
                }
        return None

@ErrorHandler.handle_database_error
def update_sleep_record(sleep_id: int, end_time: str, duration_minutes: float) -> bool:
    """Update sleep record with end time and duration"""
    database_url = os.environ.get('DATABASE_URL')
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                UPDATE {table_name} 
                SET end_time=%s, duration_minutes=%s, is_complete=%s
                WHERE id=%s
            ''', (end_time, duration_minutes, True, sleep_id))
        else:
            c.execute(f'''
                UPDATE {table_name} 
                SET end_time=?, duration_minutes=?, is_complete=?
                WHERE id=?
            ''', (end_time, duration_minutes, 1, sleep_id))
        
        return c.rowcount > 0

@ErrorHandler.handle_database_error
def get_sleep_summary(user: str, date: str) -> List[Tuple]:
    """Get sleep summary for a specific date"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                SELECT start_time, end_time, duration_minutes
                FROM {table_name} 
                WHERE {user_col}=%s AND date=%s AND is_complete=TRUE
                ORDER BY start_time
            ''', (user, date))
        else:
            c.execute(f'''
                SELECT start_time, end_time, duration_minutes
                FROM {table_name} 
                WHERE {user_col}=? AND date=? AND is_complete=1
                ORDER BY start_time
            ''', (user, date))
        
        return c.fetchall()

@ErrorHandler.handle_database_error
def get_sleep_record_count(user: str) -> int:
    """Get total number of sleep records for user"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'SELECT COUNT(*) FROM {table_name} WHERE {user_col}=%s', (user,))
        else:
            c.execute(f'SELECT COUNT(*) FROM {table_name} WHERE {user_col}=?', (user,))
        
        result = c.fetchone()
        return result[0] if result else 0

@ErrorHandler.handle_database_error
def get_sleep_records_with_limit(user: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get sleep records with optional limit"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    # Apply tier limits if no specific limit provided
    if limit is None:
        from tier_management import get_tier_limits
        limits = get_tier_limits(user)
        limit = limits.get("sleep_record")
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        query = f'''
            SELECT date, start_time, end_time, duration_minutes, is_complete
            FROM {table_name} 
            WHERE {user_col}=%s
            ORDER BY date DESC, start_time DESC
        '''
        params = [user]
        
        if limit is not None:
            query += ' LIMIT %s'
            params.append(limit)
        
        if database_url:
            c.execute(query, params)
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        
        results = c.fetchall()
        
        # Convert to list of dicts
        records = []
        for result in results:
            if isinstance(result, dict):  # PostgreSQL
                records.append(result)
            else:  # SQLite
                records.append({
                    'date': result[0],
                    'start_time': result[1],
                    'end_time': result[2],
                    'duration_minutes': result[3],
                    'is_complete': result[4]
                })
        
        return records

@ErrorHandler.handle_database_error
def delete_oldest_sleep_record(user: str) -> bool:
    """Delete oldest sleep record (for free tier management)"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                DELETE FROM {table_name} 
                WHERE id = (
                    SELECT id FROM {table_name} 
                    WHERE {user_col}=%s 
                    ORDER BY created_at ASC 
                    LIMIT 1
                )
            ''', (user,))
        else:
            c.execute(f'''
                DELETE FROM {table_name} 
                WHERE id = (
                    SELECT id FROM {table_name} 
                    WHERE {user_col}=? 
                    ORDER BY created_at ASC 
                    LIMIT 1
                )
            ''', (user,))
        
        return c.rowcount > 0

@ErrorHandler.handle_database_error
def get_sleep_statistics(user: str, days: int = 7) -> Dict[str, Any]:
    """Get sleep statistics for the last N days"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_minutes,
                    AVG(duration_minutes) as avg_duration,
                    MIN(duration_minutes) as min_duration,
                    MAX(duration_minutes) as max_duration
                FROM {table_name} 
                WHERE {user_col}=%s AND date BETWEEN %s AND %s AND is_complete=TRUE
            ''', (user, start_date, end_date))
        else:
            c.execute(f'''
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_minutes,
                    AVG(duration_minutes) as avg_duration,
                    MIN(duration_minutes) as min_duration,
                    MAX(duration_minutes) as max_duration
                FROM {table_name} 
                WHERE {user_col}=? AND date BETWEEN ? AND ? AND is_complete=1
            ''', (user, start_date, end_date))
        
        result = c.fetchone()
        
        if result:
            if isinstance(result, dict):  # PostgreSQL
                stats = result
            else:  # SQLite
                stats = {
                    'total_sessions': result[0] or 0,
                    'total_minutes': result[1] or 0,
                    'avg_duration': result[2] or 0,
                    'min_duration': result[3] or 0,
                    'max_duration': result[4] or 0
                }
            
            # Add calculated fields
            stats['total_hours'] = stats['total_minutes'] / 60
            stats['avg_hours_per_day'] = stats['total_hours'] / days
            stats['avg_sessions_per_day'] = stats['total_sessions'] / days
            
            return stats
        
        return {
            'total_sessions': 0,
            'total_minutes': 0,
            'total_hours': 0,
            'avg_duration': 0,
            'min_duration': 0,
            'max_duration': 0,
            'avg_hours_per_day': 0,
            'avg_sessions_per_day': 0
        }

@ErrorHandler.handle_database_error
def get_daily_sleep_totals(user: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get daily sleep totals for the last N days"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                SELECT 
                    date,
                    COUNT(*) as sessions,
                    SUM(duration_minutes) as total_minutes
                FROM {table_name} 
                WHERE {user_col}=%s AND date BETWEEN %s AND %s AND is_complete=TRUE
                GROUP BY date
                ORDER BY date DESC
            ''', (user, start_date, end_date))
        else:
            c.execute(f'''
                SELECT 
                    date,
                    COUNT(*) as sessions,
                    SUM(duration_minutes) as total_minutes
                FROM {table_name} 
                WHERE {user_col}=? AND date BETWEEN ? AND ? AND is_complete=1
                GROUP BY date
                ORDER BY date DESC
            ''', (user, start_date, end_date))
        
        results = c.fetchall()
        
        daily_totals = []
        for result in results:
            if isinstance(result, dict):  # PostgreSQL
                daily_data = result
            else:  # SQLite
                daily_data = {
                    'date': result[0],
                    'sessions': result[1],
                    'total_minutes': result[2] or 0
                }
            
            daily_data['total_hours'] = daily_data['total_minutes'] / 60
            daily_totals.append(daily_data)
        
        return daily_totals

@ErrorHandler.handle_database_error
def cleanup_incomplete_sleep_sessions(hours_old: int = 24) -> int:
    """Clean up incomplete sleep sessions older than specified hours"""
    database_url = os.environ.get('DATABASE_URL')
    table_name = DatabaseSecurity.validate_table_name('sleep_log')
    
    cutoff_time = datetime.now() - timedelta(hours=hours_old)
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                DELETE FROM {table_name} 
                WHERE is_complete=FALSE AND created_at < %s
            ''', (cutoff_time,))
        else:
            c.execute(f'''
                DELETE FROM {table_name} 
                WHERE is_complete=0 AND created_at < ?
            ''', (cutoff_time,))
        
        deleted_count = c.rowcount
        logging.info(f"Cleaned up {deleted_count} incomplete sleep sessions")
        return deleted_count
