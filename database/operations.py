# database/operations.py
"""
Centralized database operations module
Extracted from main.py for better organization
"""
import os
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from database_pool import DatabasePool
from database_security import DatabaseSecurity
from error_handler import ErrorHandler, ValidationError, DatabaseError
from validators import InputValidator

# Initialize the singleton pool
db_pool = DatabasePool()

@ErrorHandler.handle_database_error
def get_user_calorie_setting(user: str) -> Dict[str, float]:
    """Get user calorie setting using connection pool"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('calorie_setting')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'SELECT asi_kcal, sufor_kcal FROM {table_name} WHERE {user_col}=%s', (user,))
        else:
            c.execute(f'SELECT asi_kcal, sufor_kcal FROM {table_name} WHERE {user_col}=?', (user,))
        
        row = c.fetchone()
        if row:
            if isinstance(row, dict):  # PostgreSQL
                return {"asi": row['asi_kcal'], "sufor": row['sufor_kcal']}
            else:  # SQLite
                return {"asi": row[0], "sufor": row[1]}
        else:
            # Insert default values
            if database_url:
                c.execute(f'INSERT INTO {table_name} ({user_col}) VALUES (%s)', (user,))
            else:
                c.execute(f'INSERT INTO {table_name} ({user_col}) VALUES (?)', (user,))
            return {"asi": 0.67, "sufor": 0.7}

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def set_user_calorie_setting(user: str, milk_type: str, value: float) -> None:
    """Set user calorie setting with validation"""
    # Validate milk_type
    if milk_type not in ["asi", "sufor"]:
        raise ValidationError(f"Invalid milk_type: {milk_type}")
    
    # Validate value
    try:
        value = float(value)
        if value < 0 or value > 5:  # Reasonable range for calories per ml
            raise ValidationError(f"Invalid calorie value: {value}")
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid calorie value: {value}")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('calorie_setting')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if milk_type == "asi":
            if database_url:
                c.execute(f'UPDATE {table_name} SET asi_kcal=%s WHERE {user_col}=%s', (value, user))
            else:
                c.execute(f'UPDATE {table_name} SET asi_kcal=? WHERE {user_col}=?', (value, user))
        elif milk_type == "sufor":
            if database_url:
                c.execute(f'UPDATE {table_name} SET sufor_kcal=%s WHERE {user_col}=%s', (value, user))
            else:
                c.execute(f'UPDATE {table_name} SET sufor_kcal=? WHERE {user_col}=?', (value, user))

@ErrorHandler.handle_database_error
def get_child(user: str) -> Optional[Tuple]:
    """Get child data using connection pool"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('child')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'SELECT name, gender, dob, height_cm, weight_kg FROM {table_name} WHERE {user_col}=%s ORDER BY created_at DESC LIMIT 1', (user,))
        else:
            c.execute(f'SELECT name, gender, dob, height_cm, weight_kg FROM {table_name} WHERE {user_col}=? ORDER BY created_at DESC LIMIT 1', (user,))
        return c.fetchone()

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_child(user: str, data: Dict[str, Any]) -> None:
    """Save child data with validation"""
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['dob'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_weight_kg(str(data['weight_kg']))
    if not is_valid:
        raise ValidationError(f"Invalid weight: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_height_cm(str(data['height_cm']))
    if not is_valid:
        raise ValidationError(f"Invalid height: {error_msg}")
    
    # Sanitize text inputs
    data['name'] = InputValidator.sanitize_text_input(data['name'], 100)
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('child')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, name, gender, dob, height_cm, weight_kg)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, name, gender, dob, height_cm, weight_kg)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user, data['name'], data['gender'], data['dob'], data['height_cm'], data['weight_kg']))

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_timbang(user: str, data: Dict[str, Any]) -> None:
    """Save timbang data with validation"""
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_weight_kg(str(data['weight_kg']))
    if not is_valid:
        raise ValidationError(f"Invalid weight: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_height_cm(str(data['height_cm']))
    if not is_valid:
        raise ValidationError(f"Invalid height: {error_msg}")
    
    # Validate head circumference
    try:
        head_circum = float(data['head_circum_cm'])
        if head_circum < 10 or head_circum > 100:
            raise ValidationError("Head circumference must be between 10-100 cm")
    except (ValueError, TypeError):
        raise ValidationError("Invalid head circumference value")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('timbang_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, height_cm, weight_kg, head_circum_cm)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, height_cm, weight_kg, head_circum_cm)
                VALUES (?, ?, ?, ?, ?)
            ''', (user, data['date'], data['height_cm'], data['weight_kg'], data['head_circum_cm']))

@ErrorHandler.handle_database_error
def get_timbang_history(user: str, limit: Optional[int] = None) -> List[Tuple]:
    """Get timbang history with optional limit"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('timbang_log')
    
    # Apply tier limits if no specific limit provided
    if limit is None:
        from tier_management import get_tier_limits
        limits = get_tier_limits(user)
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
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(query, tuple(params))
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        return c.fetchall()

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_mpasi(user: str, data: Dict[str, Any]) -> None:
    """Save MPASI data with validation"""
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValidationError(f"Invalid time: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_volume_ml(str(data['volume_ml']))
    if not is_valid:
        raise ValidationError(f"Invalid volume: {error_msg}")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('mpasi_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (user, data['date'], data['time'], data['volume_ml'], data['food_detail'], data['food_grams'], data.get('est_calories')))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, volume_ml, food_detail, food_grams, est_calories)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user, data['date'], data['time'], data['volume_ml'], data['food_detail'], data['food_grams'], data.get('est_calories')))

@ErrorHandler.handle_database_error
def get_mpasi_summary(user: str, period_start: Optional[str] = None, period_end: Optional[str] = None) -> List[Tuple]:
    """Get MPASI summary with optional date range"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('mpasi_log')
    
    # Apply tier limits
    from tier_management import get_tier_limits
    limits = get_tier_limits(user)
    mpasi_limit = limits.get("mpasi_entries")

    with db_pool.get_connection() as conn:
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
        
        if database_url:
            c.execute(query, params)
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        
        return c.fetchall()

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_milk_intake(user: str, data: Dict[str, Any]) -> None:
    """Save milk intake with validation"""
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValidationError(f"Invalid time: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_volume_ml(str(data['volume_ml']))
    if not is_valid:
        raise ValidationError(f"Invalid volume: {error_msg}")
    
    # Validate milk_type
    if data['milk_type'] not in ['asi', 'sufor', 'mixed']:
        raise ValidationError(f"Invalid milk_type: {data['milk_type']}")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_intake_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (user, data['date'], data['time'], data['volume_ml'], data['milk_type'], 
                  data.get('asi_method'), data.get('sufor_calorie'), data.get('note', "")))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, volume_ml, milk_type, asi_method, sufor_calorie, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user, data['date'], data['time'], data['volume_ml'], data['milk_type'], 
                  data.get('asi_method'), data.get('sufor_calorie'), data.get('note', "")))

@ErrorHandler.handle_database_error
def get_milk_intake_summary(user: str, period_start: Optional[str] = None, period_end: Optional[str] = None) -> List[Tuple]:
    """Get milk intake summary with optional date range"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('milk_intake_log')

    # Apply tier-based limits if no specific period requested
    if not period_start and not period_end:
        from tier_management import get_tier_limits
        limits = get_tier_limits(user)
        if limits["history_days"]:
            period_start = (datetime.now() - timedelta(days=limits["history_days"])).strftime('%Y-%m-%d')
            period_end = datetime.now().strftime('%Y-%m-%d')
    
    with db_pool.get_connection() as conn:
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
        
        if database_url:
            c.execute(query, params)
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        
        return c.fetchall()

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_pumping(user: str, data: Dict[str, Any]) -> None:
    """Save pumping data with validation"""
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValidationError(f"Invalid time: {error_msg}")
    
    # Validate milk volumes
    try:
        left_ml = float(data['left_ml'])
        right_ml = float(data['right_ml'])
        if left_ml < 0 or right_ml < 0:
            raise ValidationError("Milk volumes cannot be negative")
        if left_ml > 1000 or right_ml > 1000:
            raise ValidationError("Milk volumes seem too high (max 1000ml per side)")
    except (ValueError, TypeError):
        raise ValidationError("Invalid milk volume values")
    
    # Validate milk bags
    try:
        milk_bags = int(data['milk_bags'])
        if milk_bags < 0:
            raise ValidationError("Number of milk bags cannot be negative")
        if milk_bags > 50:
            raise ValidationError("Number of milk bags seems too high (max 50)")
    except (ValueError, TypeError):
        raise ValidationError("Invalid milk bags value")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('pumping_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, left_ml, right_ml, milk_bags)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, left_ml, right_ml, milk_bags)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user, data['date'], data['time'], data['left_ml'], data['right_ml'], data['milk_bags']))

@ErrorHandler.handle_database_error
def get_pumping_summary(user: str, period_start: Optional[str] = None, period_end: Optional[str] = None) -> List[Tuple]:
    """Get pumping summary with optional date range"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('pumping_log')
    
    from tier_management import get_tier_limits
    limits = get_tier_limits(user)
    pumping_limit = limits.get("pumping_entries")

    with db_pool.get_connection() as conn:
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
        
        if database_url:
            c.execute(query, params)
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        
        return c.fetchall()

@ErrorHandler.handle_database_error
@ErrorHandler.handle_validation_error
def save_poop(user: str, data: Dict[str, Any]) -> None:
    """Save poop data with validation"""
    # Validate input data
    is_valid, error_msg = InputValidator.validate_date(data['date'])
    if not is_valid:
        raise ValidationError(f"Invalid date: {error_msg}")
    
    is_valid, error_msg = InputValidator.validate_time(data['time'])
    if not is_valid:
        raise ValidationError(f"Invalid time: {error_msg}")
    
    # Validate Bristol scale
    try:
        bristol = int(data['bristol_scale'])
        if bristol < 1 or bristol > 7:
            raise ValidationError("Bristol scale must be between 1-7")
    except (ValueError, TypeError):
        raise ValidationError("Invalid Bristol scale value")
    
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('poop_log')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, bristol_scale)
                VALUES (%s, %s, %s, %s)
            ''', (user, data['date'], data['time'], data['bristol_scale']))
        else:
            c.execute(f'''
                INSERT INTO {table_name} ({user_col}, date, time, bristol_scale)
                VALUES (?, ?, ?, ?)
            ''', (user, data['date'], data['time'], data['bristol_scale']))

def get_poop_log(user: str, period_start: Optional[str] = None, period_end: Optional[str] = None) -> List[Tuple]:
    """Get poop log with optional date range"""
    database_url = os.environ.get('DATABASE_URL')
    user_col = DatabaseSecurity.get_user_column(database_url)
    table_name = DatabaseSecurity.validate_table_name('poop_log')
    
    from tier_management import get_tier_limits
    limits = get_tier_limits(user)

    # If no period is specified and free, restrict to history_days
    if not period_start and not period_end and limits["history_days"]:
        period_start = (datetime.now() - timedelta(days=limits["history_days"])).strftime('%Y-%m-%d')
        period_end = datetime.now().strftime('%Y-%m-%d')

    query = f"SELECT date, time, bristol_scale FROM {table_name} WHERE {user_col}=%s"
    params = [user]

    # Add date range filter if specified
    if period_start and period_end:
        query += " AND date BETWEEN %s AND %s"
        params += [period_start, period_end]

    query += " ORDER BY date DESC, time DESC"

    with db_pool.get_connection() as conn:
        c = conn.cursor()
        if database_url:
            c.execute(query, tuple(params))
        else:
            sqlite_query = query.replace('%s', '?')
            c.execute(sqlite_query, tuple(params))
        return c.fetchall()
