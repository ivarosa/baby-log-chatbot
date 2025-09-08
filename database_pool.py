import os
import psycopg
from psycopg import pool
import sqlite3
from contextlib import contextmanager
import logging

class DatabasePool:
    """Database connection pooling"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # PostgreSQL connection pool
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            self._pool = psycopg.pool.ConnectionPool(
                database_url,
                min_size=2,
                max_size=10,
                timeout=30,
                kwargs={'row_factory': psycopg.rows.dict_row}
            )
            logging.info("PostgreSQL connection pool initialized")
        else:
            # SQLite doesn't need pooling, but we'll manage connections
            self._pool = None
            logging.info("Using SQLite (no pooling)")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from pool"""
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Get connection from pool
            conn = self._pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                # Return connection to pool
                self._pool.putconn(conn)
        else:
            # SQLite connection
            conn = sqlite3.connect('babylog.db')
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    def close_all(self):
        """Close all connections in pool"""
        if self._pool:
            self._pool.close()
            logging.info("Connection pool closed")
