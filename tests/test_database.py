# tests/test_database.py
import pytest
from unittest.mock import patch, MagicMock
import sqlite3

class TestDatabaseOperations:
    
    def test_save_child(self, temp_db, test_user, sample_child_data):
        """Test saving child data"""
        from main import save_child
        
        with patch('main.db_pool.get_connection') as mock_pool:
            # Setup mock connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool.return_value.__enter__.return_value = mock_conn
            
            # Test save
            save_child(test_user, sample_child_data)
            
            # Verify database call
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert "INSERT INTO child" in call_args[0]
            assert test_user in call_args[1]
    
    def test_save_mpasi(self, temp_db, test_user, sample_mpasi_data):
        """Test saving MPASI data"""
        from main import save_mpasi
        
        with patch('main.db_pool.get_connection') as mock_pool:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool.return_value.__enter__.return_value = mock_conn
            
            save_mpasi(test_user, sample_mpasi_data)
            
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert "INSERT INTO mpasi_log" in call_args[0]
    
    def test_get_child(self, temp_db, test_user):
        """Test retrieving child data"""
        from main import get_child
        
        # Mock return data
        mock_child_data = ("Test Baby", "laki-laki", "2023-01-15", 75.5, 8.5)
        
        with patch('main.db_pool.get_connection') as mock_pool:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = mock_child_data
            mock_conn.cursor.return_value = mock_cursor
            mock_pool.return_value.__enter__.return_value = mock_conn
            
            result = get_child(test_user)
            
            assert result == mock_child_data
            mock_cursor.execute.assert_called_once()
    
    def test_database_error_handling(self, temp_db, test_user, sample_child_data):
        """Test database error handling"""
        from main import save_child
        from error_handler import DatabaseError
        
        with patch('main.db_pool.get_connection') as mock_pool:
            # Simulate database error
            mock_pool.side_effect = Exception("Database connection failed")
            
            with pytest.raises(DatabaseError):
                save_child(test_user, sample_child_data)
    
    def test_get_tier_limits_free_user(self, temp_db, test_user):
        """Test tier limits for free user"""
        from main import get_tier_limits
        
        with patch('main.check_subscription_status') as mock_check:
            mock_check.return_value = {'tier': 'free', 'messages_today': 1}
            
            limits = get_tier_limits(test_user)
            
            assert limits['history_days'] == 7
            assert limits['growth_entries'] == 10
            assert limits['active_reminders'] == 3
            assert limits['sleep_record'] == 10
    
    def test_get_tier_limits_premium_user(self, temp_db, test_user):
        """Test tier limits for premium user"""
        from main import get_tier_limits
        
        with patch('main.check_subscription_status') as mock_check:
            mock_check.return_value = {'tier': 'premium', 'messages_today': 0}
            
            limits = get_tier_limits(test_user)
            
            assert limits['history_days'] is None  # Unlimited
            assert limits['growth_entries'] is None
            assert limits['active_reminders'] is None
            assert limits['sleep_record'] is None
