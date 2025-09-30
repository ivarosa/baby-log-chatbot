# tests/test_child_handler.py
"""
Tests for child_handler.py - specifically for session state management bugs
"""
import pytest
from unittest.mock import MagicMock, patch
from handlers.child_handler import ChildHandler


class TestChildHandlerSessionClearing:
    """Test that session state is properly cleared after operations"""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager"""
        manager = MagicMock()
        # Initialize session with proper structure
        manager.get_session.return_value = {
            "state": None,
            "data": {},
            "last_activity": "2024-01-01T00:00:00"
        }
        return manager
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger"""
        return MagicMock()
    
    @pytest.fixture
    def child_handler(self, mock_session_manager, mock_logger):
        """Create ChildHandler instance with mocks"""
        return ChildHandler(mock_session_manager, mock_logger)
    
    def test_session_cleared_after_successful_child_save(self, child_handler, mock_session_manager):
        """Test that session is cleared after successful child registration"""
        # Setup session in confirmation state with data
        session = {
            "state": "ADDCHILD_CONFIRM",
            "data": {
                "name": "Test Baby",
                "gender": "laki-laki",
                "dob": "2023-01-15",
                "height_cm": 75.5,
                "weight_kg": 8.5
            },
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # Mock successful save
        with patch('handlers.child_handler.save_child') as mock_save:
            mock_save.return_value = None  # Success
            
            # User confirms with "ya"
            response = child_handler.handle_add_child("test_user", "ya")
            
            # Verify session was cleared
            assert session["state"] is None
            assert session["data"] == {}
            
            # Verify session manager was updated with cleared state
            mock_session_manager.update_session.assert_called_once()
            call_args = mock_session_manager.update_session.call_args
            assert call_args[1]["state"] is None
            assert call_args[1]["data"] == {}
    
    def test_session_cleared_after_failed_child_save(self, child_handler, mock_session_manager):
        """Test that session is cleared even when child save fails"""
        # Setup session in confirmation state with data
        session = {
            "state": "ADDCHILD_CONFIRM",
            "data": {
                "name": "Test Baby",
                "gender": "laki-laki",
                "dob": "2023-01-15",
                "height_cm": 75.5,
                "weight_kg": 8.5
            },
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # Mock failed save
        with patch('handlers.child_handler.save_child') as mock_save:
            mock_save.side_effect = Exception("Database error")
            
            # User confirms with "ya"
            response = child_handler.handle_add_child("test_user", "ya")
            
            # Verify session was cleared even though save failed
            assert session["state"] is None
            assert session["data"] == {}
            
            # Verify session manager was updated with cleared state
            mock_session_manager.update_session.assert_called_once()
            call_args = mock_session_manager.update_session.call_args
            assert call_args[1]["state"] is None
            assert call_args[1]["data"] == {}
    
    def test_session_cleared_after_successful_growth_tracking(self, child_handler, mock_session_manager):
        """Test that session is cleared after successful growth data save"""
        # Setup session in TIMBANG_HEAD state with data
        session = {
            "state": "TIMBANG_HEAD",
            "data": {
                "date": "2024-01-15",
                "height_cm": 75.5,
                "weight_kg": 8.5
            },
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # Mock successful save
        with patch('handlers.child_handler.save_timbang') as mock_save:
            mock_save.return_value = None  # Success
            
            # User enters head circumference
            response = child_handler.handle_growth_tracking("test_user", "45.5")
            
            # Verify session was cleared
            assert session["state"] is None
            assert session["data"] == {}
            
            # Verify session manager was updated with cleared state
            mock_session_manager.update_session.assert_called_once()
            call_args = mock_session_manager.update_session.call_args
            assert call_args[1]["state"] is None
            assert call_args[1]["data"] == {}
    
    def test_session_cleared_after_failed_growth_tracking(self, child_handler, mock_session_manager):
        """Test that session is cleared even when growth data save fails"""
        # Setup session in TIMBANG_HEAD state with data
        session = {
            "state": "TIMBANG_HEAD",
            "data": {
                "date": "2024-01-15",
                "height_cm": 75.5,
                "weight_kg": 8.5
            },
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # Mock failed save (database error)
        with patch('handlers.child_handler.save_timbang') as mock_save:
            mock_save.side_effect = Exception("Database error")
            
            # User enters head circumference
            response = child_handler.handle_growth_tracking("test_user", "45.5")
            
            # Verify session was cleared even though save failed
            assert session["state"] is None
            assert session["data"] == {}
            
            # Verify session manager was updated with cleared state
            mock_session_manager.update_session.assert_called_once()
            call_args = mock_session_manager.update_session.call_args
            assert call_args[1]["state"] is None
            assert call_args[1]["data"] == {}
    
    def test_session_cleared_after_validation_error_in_growth_tracking(self, child_handler, mock_session_manager):
        """Test that session is cleared even when validation fails"""
        # Setup session in TIMBANG_HEAD state with data
        session = {
            "state": "TIMBANG_HEAD",
            "data": {
                "date": "2024-01-15",
                "height_cm": 75.5,
                "weight_kg": 8.5
            },
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # Mock validation error
        with patch('handlers.child_handler.save_timbang') as mock_save:
            from error_handler import ValidationError
            mock_save.side_effect = ValidationError("Invalid head circumference")
            
            # User enters head circumference
            response = child_handler.handle_growth_tracking("test_user", "45.5")
            
            # Verify session was cleared even with validation error
            assert session["state"] is None
            assert session["data"] == {}
            
            # Verify session manager was updated with cleared state
            mock_session_manager.update_session.assert_called_once()
            call_args = mock_session_manager.update_session.call_args
            assert call_args[1]["state"] is None
            assert call_args[1]["data"] == {}
    
    def test_session_cleared_on_cancel(self, child_handler, mock_session_manager):
        """Test that session is cleared when user cancels"""
        # Setup session in confirmation state
        session = {
            "state": "ADDCHILD_CONFIRM",
            "data": {"name": "Test Baby"},
            "last_activity": "2024-01-01T00:00:00"
        }
        mock_session_manager.get_session.return_value = session
        
        # User cancels with "batal"
        response = child_handler.handle_add_child("test_user", "batal")
        
        # Verify session was cleared
        assert session["state"] is None
        assert session["data"] == {}
        
        # Verify session manager was updated
        mock_session_manager.update_session.assert_called_once()
