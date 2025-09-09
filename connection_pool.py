import os
import logging
from typing import Optional
from contextlib import contextmanager
import threading
import time
from queue import Queue, Empty
import psycopg
from psycopg import pool
from psycopg.rows import dict_row
import sqlite3

class ConnectionPool:
    """Advanced database connection pooling with health checks"""
    
    def __init__(self, 
                 min_connections: int = 2,
                 max_connections: int = 10,
                 connection_timeout: int = 30,
                 idle_timeout: int = 300,
                 health_check_interval: int = 60):
        
        self.database_url = os.environ.get('DATABASE_URL')
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.health_check_interval = health_check_interval
        
        self._pool = None
        self._sqlite_pool = Queue(maxsize=max_connections)
        self._lock = threading.RLock()
        self._stats = {
            'connections_created': 0,
            'connections_reused': 0,
            'connections_closed': 0,
            'errors': 0,
            'health_checks': 0
        }
        
        self._initialize_pool()
        self._start_health_check()
    
    def _initialize_pool(self):
        """Initialize connection pool based on database type"""
        if self.database_url:
            # PostgreSQL pool
            if self.database_url.startswith('postgres://'):
                self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)
            
            try:
                self._pool = psycopg.pool.ConnectionPool(
                    self.database_url,
                    min_size=self.min_connections,
                    max_size=self.max_connections,
                    timeout=self.connection_timeout,
                    kwargs={
                        'row_factory': dict_row,
                        'autocommit': False,
                        'prepare_threshold': None
                    }
                )
                logging.info(f"PostgreSQL pool initialized: min={self.min_connections}, max={self.max_connections}")
            except Exception as e:
                logging.error(f"Failed to initialize PostgreSQL pool: {e}")
                raise
        else:
            # SQLite - pre-create connections
            for _ in range(self.min_connections):
                conn = self._create_sqlite_connection()
                self._sqlite_pool.put(conn)
            logging.info(f"SQLite pool initialized with {self.min_connections} connections")
    
    def _create_sqlite_connection(self):
        """Create a new SQLite connection"""
        conn = sqlite3.connect('babylog.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        self._stats['connections_created'] += 1
        return conn
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        start_time = time.time()
        
        try:
            if self.database_url:
                # PostgreSQL
                conn = self._pool.getconn()
                self._stats['connections_reused'] += 1
                
                # Test connection
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                
                yield conn
                conn.commit()
                
            else:
                # SQLite
                try:
                    conn = self._sqlite_pool.get(timeout=self.connection_timeout)
                    self._stats['connections_reused'] += 1
                    
                    # Test connection
                    conn.execute("SELECT 1")
                    
                    yield conn
                    conn.commit()
                    
                except Empty:
                    # Create new connection if pool is exhausted
                    if self._sqlite_pool.qsize() < self.max_connections:
                        conn = self._create_sqlite_connection()
                        yield conn
                        conn.commit()
                    else:
                        raise DatabaseError("Connection pool exhausted")
        
        except Exception as e:
            if conn:
                conn.rollback()
            self._stats['errors'] += 1
            logging.error(f"Connection error: {e}")
            raise
        
        finally:
            # Return connection to pool
            if conn:
                if self.database_url:
                    self._pool.putconn(conn)
                else:
                    self._sqlite_pool.put(conn)
            
            # Log slow connections
            elapsed = time.time() - start_time
            if elapsed > 1:
                logging.warning(f"Slow database operation: {elapsed:.2f}s")
    
    def _health_check_worker(self):
        """Background thread for connection health checks"""
        while True:
            try:
                time.sleep(self.health_check_interval)
                self._perform_health_check()
            except Exception as e:
                logging.error(f"Health check failed: {e}")
    
    def _perform_health_check(self):
        """Perform health check on connections"""
        self._stats['health_checks'] += 1
        
        if self.database_url:
            # PostgreSQL health check
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                logging.debug("PostgreSQL health check passed")
            except Exception as e:
                logging.error(f"PostgreSQL health check failed: {e}")
                # Attempt to recreate pool
                self._initialize_pool()
        else:
            # SQLite health check
            temp_conns = []
            while not self._sqlite_pool.empty():
                try:
                    conn = self._sqlite_pool.get_nowait()
                    conn.execute("SELECT 1")
                    temp_conns.append(conn)
                except Exception as e:
                    logging.warning(f"Removing bad SQLite connection: {e}")
                    self._stats['connections_closed'] += 1
            
            # Return good connections to pool
            for conn in temp_conns:
                self._sqlite_pool.put(conn)
    
    def _start_health_check(self):
        """Start health check thread"""
        thread = threading.Thread(target=self._health_check_worker, daemon=True)
        thread.start()
        logging.info("Connection pool health check started")
    
    def get_stats(self) -> dict:
        """Get pool statistics"""
        stats = self._stats.copy()
        
        if self.database_url:
            # Add PostgreSQL specific stats
            pool_info = self._pool.get_stats()
            stats.update({
                'pool_size': pool_info['pool_size'],
                'pool_available': pool_info['pool_available'],
                'requests_queued': pool_info['requests_queued']
            })
        else:
            # SQLite stats
            stats['pool_size'] = self._sqlite_pool.qsize()
        
        return stats
    
    def close(self):
        """Close all connections"""
        if self.database_url and self._pool:
            self._pool.close()
            logging.info("PostgreSQL pool closed")
        else:
            while not self._sqlite_pool.empty():
                try:
                    conn = self._sqlite_pool.get_nowait()
                    conn.close()
                    self._stats['connections_closed'] += 1
                except Empty:
                    break
            logging.info("SQLite connections closed")
