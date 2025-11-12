# tests/test_group_handler.py
"""
Tests for GroupHandler functionality
"""
import pytest
from unittest.mock import MagicMock, patch
from handlers.group_handler import GroupHandler
from session_manager import SessionManager


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing"""
    manager = SessionManager(timeout_minutes=30)
    return manager


@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    return MagicMock()


@pytest.fixture
def group_handler(mock_session_manager, mock_logger):
    """Create GroupHandler instance for testing"""
    return GroupHandler(mock_session_manager, mock_logger)


class TestGroupHandler:
    """Test cases for GroupHandler"""
    
    def test_is_group_message_with_group_id(self, group_handler):
        """Test identifying group messages"""
        # Group messages contain 'g.us' in the identifier
        group_user = "whatsapp:+1234567890-1234567890@g.us"
        assert group_handler.is_group_message(group_user) is True
    
    def test_is_group_message_with_regular_user(self, group_handler):
        """Test identifying regular user messages"""
        regular_user = "whatsapp:+1234567890"
        assert group_handler.is_group_message(regular_user) is False
    
    def test_is_group_message_with_none(self, group_handler):
        """Test handling None user"""
        assert group_handler.is_group_message(None) is False
    
    @patch('handlers.group_handler.save_group_user')
    def test_handle_join_command_from_group_new_user(self, mock_save, group_handler):
        """Test join command from group for new user"""
        mock_save.return_value = True  # New user
        group_user = "whatsapp:+1234567890@g.us"
        
        response = group_handler.handle_join_command(group_user, "join")
        
        # Verify response
        assert response is not None
        assert response.media_type == "application/xml"
        
        # Verify save was called
        mock_save.assert_called_once_with(group_user)
    
    @patch('handlers.group_handler.save_group_user')
    def test_handle_join_command_from_group_existing_user(self, mock_save, group_handler):
        """Test join command from group for existing user"""
        mock_save.return_value = False  # Existing user
        group_user = "whatsapp:+1234567890@g.us"
        
        response = group_handler.handle_join_command(group_user, "join")
        
        # Verify response
        assert response is not None
        assert response.media_type == "application/xml"
        
        # Verify save was called
        mock_save.assert_called_once_with(group_user)
    
    def test_handle_join_command_from_regular_user(self, group_handler):
        """Test join command from regular user (not group)"""
        regular_user = "whatsapp:+1234567890"
        
        response = group_handler.handle_join_command(regular_user, "join")
        
        # Verify response redirects to start command
        assert response is not None
        assert response.media_type == "application/xml"
    
    def test_handle_join_command_with_variations(self, group_handler):
        """Test join command with different variations"""
        group_user = "whatsapp:+1234567890@g.us"
        
        # Test different join variations
        variations = ["join", "Join", "JOIN", "gabung", "Gabung", "/join"]
        
        for variation in variations:
            with patch('handlers.group_handler.save_group_user', return_value=True):
                response = group_handler.handle_join_command(group_user, variation)
                assert response is not None
                assert response.media_type == "application/xml"
    
    def test_handle_join_command_invalid_message(self, group_handler):
        """Test join command with invalid message"""
        group_user = "whatsapp:+1234567890@g.us"
        
        response = group_handler.handle_join_command(group_user, "invalid")
        
        # Should return error message
        assert response is not None
        assert response.media_type == "application/xml"
    
    def test_handle_group_message(self, group_handler):
        """Test handling general group messages"""
        group_user = "whatsapp:+1234567890@g.us"
        
        response = group_handler.handle_group_message(group_user, "Hello")
        
        # Should redirect to private chat
        assert response is not None
        assert response.media_type == "application/xml"
    
    @patch('handlers.group_handler.save_group_user')
    def test_handle_join_command_database_error(self, mock_save, group_handler):
        """Test join command when database fails"""
        mock_save.side_effect = Exception("Database error")
        group_user = "whatsapp:+1234567890@g.us"
        
        response = group_handler.handle_join_command(group_user, "join")
        
        # Should handle error gracefully
        assert response is not None
        assert response.media_type == "application/xml"
    
    def test_handle_group_message_error(self, group_handler, mock_logger):
        """Test error handling in group message"""
        group_user = "whatsapp:+1234567890@g.us"
        
        # Should not raise exception
        response = group_handler.handle_group_message(group_user, "test message")
        assert response is not None
        assert response.media_type == "application/xml"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
