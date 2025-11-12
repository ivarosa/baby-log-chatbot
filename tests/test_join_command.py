"""
Test for Twilio sandbox join command handling
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import BackgroundTasks
from main import process_message


@pytest.mark.asyncio
async def test_join_command_with_sandbox_code():
    """Test that 'join shallow-arrow' triggers welcome message"""
    user = "whatsapp:+6281234567890"
    message = "join shallow-arrow"
    
    with patch('main.session_manager') as mock_session_manager, \
         patch('main.WELCOME_MESSAGE', 'Welcome to Babylog!'):
        
        # Setup mock session
        mock_session_manager.get_session.return_value = {"state": None}
        mock_session_manager.clear_session = AsyncMock()
        
        # Create background tasks
        background_tasks = BackgroundTasks()
        
        # Process the message
        response = await process_message(user, message, background_tasks)
        
        # Verify response
        assert response is not None
        assert response.status_code == 200
        assert b"Welcome to Babylog!" in response.body
        
        # Verify session was cleared
        mock_session_manager.clear_session.assert_called_once_with(user)


@pytest.mark.asyncio
async def test_join_command_with_different_code():
    """Test that any 'join <code>' triggers welcome message"""
    user = "whatsapp:+6281234567890"
    message = "join test-code-123"
    
    with patch('main.session_manager') as mock_session_manager, \
         patch('main.WELCOME_MESSAGE', 'Welcome to Babylog!'):
        
        # Setup mock session
        mock_session_manager.get_session.return_value = {"state": None}
        mock_session_manager.clear_session = AsyncMock()
        
        # Create background tasks
        background_tasks = BackgroundTasks()
        
        # Process the message
        response = await process_message(user, message, background_tasks)
        
        # Verify response
        assert response is not None
        assert response.status_code == 200
        assert b"Welcome to Babylog!" in response.body


@pytest.mark.asyncio
async def test_join_command_case_insensitive():
    """Test that 'JOIN', 'Join', 'join' all work"""
    user = "whatsapp:+6281234567890"
    
    for message in ["JOIN shallow-arrow", "Join shallow-arrow", "join shallow-arrow"]:
        with patch('main.session_manager') as mock_session_manager, \
             patch('main.WELCOME_MESSAGE', 'Welcome to Babylog!'):
            
            # Setup mock session
            mock_session_manager.get_session.return_value = {"state": None}
            mock_session_manager.clear_session = AsyncMock()
            
            # Create background tasks
            background_tasks = BackgroundTasks()
            
            # Process the message
            response = await process_message(user, message, background_tasks)
            
            # Verify response
            assert response is not None
            assert response.status_code == 200
            assert b"Welcome to Babylog!" in response.body


@pytest.mark.asyncio
async def test_start_command_still_works():
    """Verify that existing start command still works"""
    user = "whatsapp:+6281234567890"
    message = "start"
    
    with patch('main.session_manager') as mock_session_manager, \
         patch('main.WELCOME_MESSAGE', 'Welcome to Babylog!'):
        
        # Setup mock session
        mock_session_manager.get_session.return_value = {"state": None}
        mock_session_manager.clear_session = AsyncMock()
        
        # Create background tasks
        background_tasks = BackgroundTasks()
        
        # Process the message
        response = await process_message(user, message, background_tasks)
        
        # Verify response
        assert response is not None
        assert response.status_code == 200
        assert b"Welcome to Babylog!" in response.body
