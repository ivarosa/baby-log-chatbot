# tests/test_reminder_handler.py
import pytest
import tempfile
import os
import logging
from unittest.mock import MagicMock, patch, Mock
import sys

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.reminder_handler import ReminderHandler


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing"""
    mock = Mock()
    mock.get_session.return_value = {"state": None, "data": {}}
    return mock


@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    return logging.getLogger('test')


@pytest.fixture
def reminder_handler(mock_session_manager, mock_logger):
    """Create ReminderHandler instance for testing"""
    return ReminderHandler(mock_session_manager, mock_logger)


def test_handle_show_reminders_with_complete_tuples(reminder_handler):
    """Test handle_show_reminders with complete tuple data"""
    # Mock the get_user_reminders to return tuples as expected
    with patch('handlers.reminder_handler.get_user_reminders') as mock_get_reminders:
        # Return tuple matching actual query: reminder_name, interval_hours, start_time, end_time, is_active, next_due
        mock_get_reminders.return_value = [
            ('Test Reminder', 3, '08:00', '20:00', 1, '2024-01-15 08:00:00')
        ]
        
        # Test the function
        response = reminder_handler.handle_show_reminders('whatsapp:+1234567890')
        
        # Verify response contains expected content
        assert response.status_code == 200
        response_body = response.body.decode('utf-8')
        assert 'Test Reminder' in response_body
        assert '🟢 Aktif' in response_body
        assert 'Setiap 3 jam' in response_body


def test_handle_show_reminders_with_incomplete_tuples(reminder_handler):
    """Test handle_show_reminders gracefully handles incomplete tuples"""
    # Mock the get_user_reminders to return incomplete tuples
    with patch('handlers.reminder_handler.get_user_reminders') as mock_get_reminders:
        # Return incomplete tuple (only 3 fields instead of 6)
        mock_get_reminders.return_value = [
            ('Test Reminder', 3, '08:00'),  # Missing end_time, is_active, next_due
            ('Complete Reminder', 2, '06:00', '22:00', 1, '2024-01-15 06:00:00')  # Complete tuple
        ]
        
        # Test the function
        response = reminder_handler.handle_show_reminders('whatsapp:+1234567890')
        
        # Verify response is successful
        assert response.status_code == 200
        response_body = response.body.decode('utf-8')
        
        # The incomplete tuple should be skipped, only complete one should appear
        assert 'Complete Reminder' in response_body
        assert 'Test Reminder' not in response_body  # Should be skipped due to incomplete data
        assert '🟢 Aktif' in response_body
        assert 'Setiap 2 jam' in response_body


def test_handle_show_reminders_empty_list(reminder_handler):
    """Test handle_show_reminders with no reminders"""
    # Mock the get_user_reminders to return empty list
    with patch('handlers.reminder_handler.get_user_reminders') as mock_get_reminders:
        mock_get_reminders.return_value = []
        
        # Test the function
        response = reminder_handler.handle_show_reminders('whatsapp:+1234567890')
        
        # Verify response contains "no reminders" message
        assert response.status_code == 200
        response_body = response.body.decode('utf-8')
        assert 'Belum ada pengingat yang diatur' in response_body
        assert 'set reminder susu' in response_body


def test_handle_show_reminders_with_edge_case_tuple_lengths(reminder_handler):
    """Test handle_show_reminders with various tuple lengths"""
    # Mock the get_user_reminders to return tuples of different lengths
    with patch('handlers.reminder_handler.get_user_reminders') as mock_get_reminders:
        mock_get_reminders.return_value = [
            (),  # Empty tuple
            ('Only name',),  # 1 field
            ('Name', 2),  # 2 fields  
            ('Name', 3, '08:00', '20:00'),  # 4 fields
            ('Name', 4, '08:00', '20:00', 1),  # 5 fields
            ('Valid Reminder', 3, '08:00', '20:00', 1, '2024-01-15 08:00:00'),  # 6 fields - valid
            ('Extra Field Reminder', 2, '06:00', '22:00', 1, '2024-01-15 06:00:00', 'extra', 'more_extra')  # 8 fields
        ]
        
        # Test the function
        response = reminder_handler.handle_show_reminders('whatsapp:+1234567890')
        
        # Verify response is successful
        assert response.status_code == 200
        response_body = response.body.decode('utf-8')
        
        # Only the valid reminder should appear
        assert 'Valid Reminder' in response_body
        assert 'Extra Field Reminder' in response_body  # This should work too since it has >= 6 fields
        assert 'Setiap 3 jam' in response_body
        
        # Edge cases should be skipped gracefully
        assert 'Only name' not in response_body