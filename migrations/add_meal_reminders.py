# migrations/add_meal_reminders.py
"""
Migration to add meal reminders feature
Run this once to create the meal_reminders table
"""
import os
import sqlite3
from database_pool import DatabasePool

db_pool = DatabasePool()

def migrate_up():
    """Create meal_reminders table"""
    database_url = os.environ.get('DATABASE_URL')
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        
        if database_url:
            # PostgreSQL
            c.execute('''
                CREATE TABLE IF NOT EXISTS meal_reminders (
                    id SERIAL PRIMARY KEY,
                    user_phone TEXT NOT NULL,
                    reminder_name TEXT NOT NULL,
                    meal_type TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_sent TIMESTAMP,
                    next_due TIMESTAMP,
                    days_of_week TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for performance
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_meal_reminders_user 
                ON meal_reminders(user_phone)
            ''')
            
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_meal_reminders_next_due 
                ON meal_reminders(next_due) 
                WHERE is_active = TRUE
            ''')
        else:
            # SQLite
            c.execute('''
                CREATE TABLE IF NOT EXISTS meal_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    reminder_name TEXT NOT NULL,
                    meal_type TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_sent TIMESTAMP,
                    next_due TIMESTAMP,
                    days_of_week TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_meal_reminders_user 
                ON meal_reminders(user)
            ''')
            
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_meal_reminders_next_due 
                ON meal_reminders(next_due)
            ''')
        
        print("✅ meal_reminders table created successfully")

def migrate_down():
    """Rollback: Drop meal_reminders table"""
    database_url = os.environ.get('DATABASE_URL')
    table_name = 'meal_reminders'
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        c.execute(f'DROP TABLE IF EXISTS {table_name}')
        print("✅ meal_reminders table dropped")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
