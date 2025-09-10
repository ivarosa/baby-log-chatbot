# tests/conftest.py
import pytest
import sqlite3
import os
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from session_manager import SessionManager
from database_pool import DatabasePool

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    
    # Set environment to use test database
    os.environ['DATABASE_URL'] = ''  # Force SQLite
    
    # Create tables
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create test tables (simplified)
    cursor.execute('''
        CREATE TABLE child (
            id INTEGER PRIMARY KEY,
            user TEXT,
            name TEXT,
            gender TEXT,
            dob DATE,
            height_cm REAL,
            weight_kg REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE mpasi_log (
            id INTEGER PRIMARY KEY,
            user TEXT,
            date DATE,
            time TEXT,
            volume_ml REAL,
            food_detail TEXT,
            est_calories REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE milk_intake_log (
            id INTEGER PRIMARY KEY,
            user TEXT,
            date DATE,
            time TEXT,
            volume_ml REAL,
            milk_type TEXT,
            asi_method TEXT,
            sufor_calorie REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE sleep_log (
            id INTEGER PRIMARY KEY,
            user TEXT,
            date DATE,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            is_complete BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Patch the database connection
    with patch('sqlite3.connect') as mock_connect:
        mock_connect.return_value = sqlite3.connect(path)
        yield path
    
    # Cleanup
    os.unlink(path)

@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing"""
    manager = SessionManager(timeout_minutes=30)
    return manager

@pytest.fixture
def test_user():
    """Standard test user"""
    return "whatsapp:+6281234567890"

@pytest.fixture
def mock_twilio():
    """Mock Twilio client"""
    with patch('send_twilio_message.send_twilio_message') as mock:
        mock.return_value = "message_sid_123"
        yield mock

@pytest.fixture
def app_client(temp_db, mock_session_manager):
    """Test client for FastAPI app"""
    from main import app
    
    # Patch dependencies
    with patch('main.session_manager', mock_session_manager):
        with TestClient(app) as client:
            yield client

@pytest.fixture
def sample_child_data():
    """Sample child data for testing"""
    return {
        'name': 'Test Baby',
        'gender': 'laki-laki',
        'dob': '2023-01-15',
        'height_cm': 75.5,
        'weight_kg': 8.5
    }

@pytest.fixture
def sample_mpasi_data():
    """Sample MPASI data for testing"""
    return {
        'date': '2024-01-15',
        'time': '12:30',
        'volume_ml': 100,
        'food_detail': 'nasi tim, ayam, wortel',
        'food_grams': 'nasi 50g, ayam 30g, wortel 20g',
        'est_calories': 150
    }

@pytest.fixture
def sample_sleep_data():
    """Sample sleep data for testing"""
    return {
        'date': '2024-01-15',
        'start_time': '20:00',
        'end_time': '06:00',
        'duration_minutes': 600
    }
