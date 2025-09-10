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
        if table_name:
            table_name = DatabaseSecurity.validate_table_name(table_name)
            query_template = query_template.replace('{}', table_name, 1)
        
        if column_name:
            column_name = DatabaseSecurity.validate_column_name(
                column_name, DatabaseSecurity.ALLOWED_USER_COLUMNS
            )
            query_template = query_template.replace('{}', column_name, 1)
        
        return query_template, params
