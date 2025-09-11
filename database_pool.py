import os
import sqlite3
from contextlib import contextmanager
import logging
import threading
import time
from queue import Queue, Empty

class DatabasePool:
    """Database connection pooling for both PostgreSQL and SQLite"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabasePool, cls).__new__(cls)
                    cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        self.database_url = os.environ.get('DATABASE_URL')
        
        if self.database_url:
            # PostgreSQL connection pool using psycopg2
            try:
                import psycopg2
                import psycopg2.extras
                from urllib.parse import urlparse
                
                # Parse the DATABASE_URL
                parsed = urlparse(self.database_url)
                
                self.connection_params = {
                    'host': parsed.hostname,
                    'port': parsed.port or 5432,
                    'database': parsed.path.lstrip('/'),
                    'user': parsed.username,
                    'password': parsed.password,
                    'sslmode': 'require'  # For production PostgreSQL
                }
                
                # Test connection
                test_conn = psycopg2.connect(**self.connection_params)
                test_conn.close()
                
                # Create a simple connection pool using Queue
                self._pool = Queue(maxsize=10)  # Max 10 connections
                self._pool_size = 0
                self._max_pool_size = 10
                self._min_pool_size = 2
                self._pool_lock = threading.Lock()
                
                # Pre-create minimum connections
                for _ in range(self._min_pool_size):
                    try:
                        conn = psycopg2.connect(**self.connection_params)
                        conn.set_session(autocommit=False)
                        self._pool.put(conn)
                        self._pool_size += 1
                    except Exception as e:
                        logging.error(f"Failed to create initial connection: {e}")
                
                logging.info(f"PostgreSQL connection pool initialized with {self._pool_size} connections")
                
            except ImportError as e:
                logging.error(f"PostgreSQL dependencies not available: {e}")
                logging.info("Falling back to SQLite")
                self._fallback_to_sqlite()
            except Exception as e:
                logging.error(f"PostgreSQL connection failed: {e}")
                logging.info("Falling back to SQLite")
                self._fallback_to_sqlite()
        else:
            # SQLite doesn't need pooling, but we'll manage connections
            self._pool = None
            logging.info("Using SQLite (no pooling)")
    
    def _fallback_to_sqlite(self):
        """Fallback to SQLite when PostgreSQL is not available"""
        self.database_url = None
        self._pool = None
        logging.info("Fallback to SQLite database")
    
    def _create_connection(self):
        """Create a new database connection"""
        if self.database_url:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(**self.connection_params)
            conn.set_session(autocommit=False)
            # Use RealDictCursor for dict-like row access
            return conn
        else:
            conn = sqlite3.connect('babylog.db')
            conn.row_factory = sqlite3.Row
            return conn
    
    def _get_connection_from_pool(self):
        """Get a connection from the PostgreSQL pool"""
        try:
            # Try to get an existing connection (non-blocking)
            conn = self._pool.get_nowait()
            
            # Test if connection is still alive
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return conn
            except Exception:
                # Connection is dead, create a new one
                try:
                    conn.close()
                except:
                    pass
                
        except Empty:
            # No connections available, create new one if under limit
            with self._pool_lock:
                if self._pool_size < self._max_pool_size:
                    try:
                        conn = self._create_connection()
                        self._pool_size += 1
                        return conn
                    except Exception as e:
                        logging.error(f"Failed to create new connection: {e}")
                        raise
        
        # Wait for a connection to become available
        try:
            conn = self._pool.get(timeout=30)  # 30 second timeout
            # Test connection
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return conn
            except Exception:
                try:
                    conn.close()
                except:
                    pass
                # Recursive call to get another connection
                return self._get_connection_from_pool()
        except Empty:
            raise Exception("Connection pool timeout - no connections available")
    
    def _return_connection_to_pool(self, conn):
        """Return a connection to the PostgreSQL pool"""
        try:
            # Test if connection is still good
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            
            # Connection is good, return to pool
            try:
                self._pool.put_nowait(conn)
            except:
                # Pool is full, close this connection
                try:
                    conn.close()
                except:
                    pass
                with self._pool_lock:
                    self._pool_size -= 1
        except Exception:
            # Connection is bad, close it
            try:
                conn.close()
            except:
                pass
            with self._pool_lock:
                self._pool_size -= 1
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from pool"""
        if self.database_url:
            # PostgreSQL connection from pool
            conn = self._get_connection_from_pool()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                try:
                    conn.rollback()
                except:
                    pass
                raise e
            finally:
                # Return connection to pool
                self._return_connection_to_pool(conn)
        else:
            # SQLite connection (no pooling)
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
            # Close all connections in the queue
            closed_count = 0
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                    closed_count += 1
                except Empty:
                    break
                except Exception as e:
                    logging.error(f"Error closing connection: {e}")
            
            with self._pool_lock:
                self._pool_size = 0
            
            logging.info(f"Connection pool closed - {closed_count} connections closed")
    
    def get_stats(self):
        """Get pool statistics"""
        if self._pool:
            return {
                "pool_size": self._pool_size,
                "available_connections": self._pool.qsize(),
                "max_pool_size": self._max_pool_size,
                "min_pool_size": self._min_pool_size,
                "database_type": "postgresql"
            }
        else:
            return {
                "database_type": "sqlite",
                "pool_size": "N/A",
                "available_connections": "N/A"
            }
