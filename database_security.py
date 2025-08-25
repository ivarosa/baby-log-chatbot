import re
from typing import List, Tuple, Any

class DatabaseSecurity:
    """Secure database operations"""
    
    # Whitelist of allowed column names
    ALLOWED_USER_COLUMNS = ['user', 'user_phone']
    ALLOWED_TABLE_NAMES = [
        'child', 'timbang_log', 'mpasi_log', 'poop_log',
        'pumping_log', 'milk_intake_log', 'calorie_setting',
        'milk_reminders', 'reminder_logs', 'user_tiers',
        'user_subscriptions', 'sleep_log'
    ]
    
    @staticmethod
    def validate_column_name(column_name: str, allowed_list: List[str]) -> str:
        """Validate column name against whitelist"""
        if column_name not in allowed_list:
            raise ValueError(f"Invalid column name: {column_name}")
        return column_name
    
    @staticmethod
    def validate_table_name(table_name: str) -> str:
        """Validate table name against whitelist"""
        if table_name not in DatabaseSecurity.ALLOWED_TABLE_NAMES:
            raise ValueError(f"Invalid table name: {table_name}")
        return table_name
    
    @staticmethod
    def safe_query(query_template: str, params: Tuple[Any, ...], 
                   column_name: str = None, table_name: str = None) -> Tuple[str, Tuple]:
        """
        Safely construct queries with validated column/table names
        
        Example:
            query, params = DatabaseSecurity.safe_query(
                "SELECT * FROM {} WHERE {}=%s",
                (user_value,),
                column_name='user_phone',
                table_name='child'
            )
        """
        if table_name:
            table_name = DatabaseSecurity.validate_table_name(table_name)
            query_template = query_template.replace('{}', table_name, 1)
        
        if column_name:
            column_name = DatabaseSecurity.validate_column_name(
                column_name, 
                DatabaseSecurity.ALLOWED_USER_COLUMNS
            )
            query_template = query_template.replace('{}', column_name, 1)
        
        return query_template, params

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
