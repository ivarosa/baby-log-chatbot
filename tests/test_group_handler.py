# tests/test_group_handler.py
import pytest
import logging
from unittest.mock import Mock
import sys
import os

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.group_handler import GroupHandler


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
def group_handler(mock_session_manager, mock_logger):
    """Create GroupHandler instance for testing"""
    return GroupHandler(mock_session_manager, mock_logger)


def test_normalize_group_name_basic(group_handler):
    """Test basic group name normalization"""
    assert group_handler._normalize_group_name("shallow-arrow") == "shallow-arrow"
    assert group_handler._normalize_group_name("  shallow-arrow  ") == "shallow-arrow"
    assert group_handler._normalize_group_name("test group") == "test group"


def test_normalize_group_name_with_special_dashes(group_handler):
    """Test normalization of special dash characters"""
    # Test various dash types (em dash, en dash, etc.)
    assert group_handler._normalize_group_name("shallow–arrow") == "shallow-arrow"
    assert group_handler._normalize_group_name("shallow—arrow") == "shallow-arrow"
    

def test_normalize_group_name_multiple_spaces(group_handler):
    """Test collapsing multiple spaces"""
    assert group_handler._normalize_group_name("test    group") == "test group"
    assert group_handler._normalize_group_name("test  multiple   spaces") == "test multiple spaces"


def test_normalize_group_name_empty(group_handler):
    """Test empty group name"""
    assert group_handler._normalize_group_name("") == ""
    assert group_handler._normalize_group_name("   ") == ""


def test_handle_join_success(group_handler):
    """Test successful join request"""
    response = group_handler.handle_join("whatsapp:+1234567890", "shallow-arrow")
    
    assert response.status_code == 200
    response_body = response.body.decode('utf-8')
    assert "✅" in response_body
    assert "shallow-arrow" in response_body
    assert "Permintaan bergabung" in response_body


def test_handle_join_empty_group(group_handler):
    """Test join with empty group name"""
    response = group_handler.handle_join("whatsapp:+1234567890", "")
    
    assert response.status_code == 200
    response_body = response.body.decode('utf-8')
    assert "❌" in response_body
    assert "tidak ditemukan" in response_body


def test_handle_join_whitespace_group(group_handler):
    """Test join with whitespace-only group name"""
    response = group_handler.handle_join("whatsapp:+1234567890", "   ")
    
    assert response.status_code == 200
    response_body = response.body.decode('utf-8')
    assert "❌" in response_body
    assert "tidak ditemukan" in response_body


def test_handle_join_with_special_dashes(group_handler):
    """Test join with special dash characters"""
    response = group_handler.handle_join("whatsapp:+1234567890", "shallow–arrow")
    
    assert response.status_code == 200
    response_body = response.body.decode('utf-8')
    assert "✅" in response_body
    assert "shallow-arrow" in response_body


def test_handle_join_logging(group_handler, caplog):
    """Test that join requests are logged"""
    with caplog.at_level(logging.INFO):
        group_handler.handle_join("whatsapp:+1234567890", "test-group")
        
        assert "Join requested" in caplog.text
        assert "test-group" in caplog.text
        assert "whatsapp:+1234567890" in caplog.text
