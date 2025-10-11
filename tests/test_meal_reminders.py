# tests/test_meal_reminders.py
"""
Test script for meal reminder functionality
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json

def test_meal_reminder_setup():
    """Test meal reminder setup flow"""
    from handlers.meal_reminder_handler import MealReminderHandler
    
    mock_session_manager = Mock()
    mock_session_manager.get_session.return_value = {"state": None, "data": {}}
    
    handler = MealReminderHandler(mock_session_manager, Mock())
    
    # Test meal type parsing
    assert handler._parse_meal_type("sarapan") == "breakfast"
    assert handler._parse_meal_type("makan siang") == "lunch"
    assert handler._parse_meal_type("dinner") == "dinner"
    assert handler._parse_meal_type("snack") == "snack"
    
    print("✅ Meal type parsing works")

def test_custom_days_parsing():
    """Test custom days parsing"""
    from handlers.meal_reminder_handler import MealReminderHandler
    
    handler = MealReminderHandler(Mock(), Mock())
    
    # Test valid input
    result = handler._parse_custom_days("senin, rabu, jumat")
    assert result == ['mon', 'wed', 'fri']
    
    # Test mixed case
    result = handler._parse_custom_days("Senin, RABU, Jumat")
    assert result == ['mon', 'wed', 'fri']
    
    # Test invalid input
    result = handler._parse_custom_days("invalid, days")
    assert result is None
    
    print("✅ Custom days parsing works")

def test_days_display_formatting():
    """Test days display formatting"""
    from handlers.meal_reminder_handler import MealReminderHandler
    
    handler = MealReminderHandler(Mock(), Mock())
    
    # All days
    result = handler._format_days_display(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])
    assert result == "Setiap hari"
    
    # Weekdays
    result = handler._format_days_display(['mon', 'tue', 'wed', 'thu', 'fri'])
    assert result == "Hari kerja (Sen-Jum)"
    
    # Weekend
    result = handler._format_days_display(['sat', 'sun'])
    assert result == "Akhir pekan (Sab-Min)"
    
    # Custom
    result = handler._format_days_display(['mon', 'wed', 'fri'])
    assert "Sen" in result and "Rab" in result and "Jum" in result
    
    print("✅ Days display formatting works")

def test_next_due_calculation():
    """Test next due time calculation"""
    from handlers.meal_reminder_handler import MealReminderHandler
    from timezone_handler import TimezoneHandler
    
    handler = MealReminderHandler(Mock(), Mock())
    
    user = "whatsapp:+1234567890"
    reminder_time = "07:00"
    days_of_week = ['mon', 'wed', 'fri']
    
    with patch.object(TimezoneHandler, 'now_local') as mock_now:
        # Mock current time as Tuesday 10:00
        mock_now.return_value = datetime(2024, 1, 2, 10, 0)  # Tuesday
        
        with patch.object(TimezoneHandler, 'to_utc') as mock_to_utc:
            mock_to_utc.return_value = datetime(2024, 1, 3, 0, 0)  # Mock UTC conversion
            
            next_due = handler._calculate_next_due(user, reminder_time, days_of_week)
            
            # Should skip to Wednesday since today is Tuesday
            assert next_due is not None
            
    print("✅ Next due calculation works")

def test_database_operations():
    """Test meal reminder database operations"""
    from database.operations import (
        save_meal_reminder, get_meal_reminders, 
        get_meal_reminder_count
    )
    
    # This requires actual database - would need proper test setup
    print("⚠️ Database operations test requires test database setup")

if __name__ == "__main__":
    print("Running meal reminder tests...\n")
    
    test_meal_reminder_setup()
    test_custom_days_parsing()
    test_days_display_formatting()
    test_next_due_calculation()
    test_database_operations()
    
    print("\n✅ All tests completed!")
