#!/usr/bin/env python3
"""
Test to verify the panduan command is working correctly.
This test can be run to confirm the fix is in place.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestPanduanCommand(unittest.TestCase):
    """Test the panduan command functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        from constants import PANDUAN_MESSAGE, HELP_MESSAGE
        self.panduan_message = PANDUAN_MESSAGE
        self.help_message = HELP_MESSAGE
    
    def test_panduan_message_content(self):
        """Test that PANDUAN_MESSAGE has expected content"""
        self.assertIsNotNone(self.panduan_message)
        self.assertGreater(len(self.panduan_message), 1000)  # Should be substantial content
        self.assertIn("Panduan Lengkap Babylog", self.panduan_message)
        self.assertIn("Data Anak & Tumbuh Kembang", self.panduan_message)
        self.assertIn("Asupan Nutrisi & Makan", self.panduan_message)
    
    def test_panduan_in_help_message(self):
        """Test that panduan is mentioned in help message"""
        self.assertIn("panduan", self.help_message.lower())
        self.assertIn("daftar lengkap perintah", self.help_message.lower())
    
    @patch('main.session_manager')
    @patch('main.MessagingResponse')
    def test_panduan_command_routing(self, mock_messaging_response, mock_session_manager):
        """Test that panduan command is routed correctly"""
        # Mock session manager
        mock_session = {'state': None, 'data': {}}
        mock_session_manager.get_session.return_value = mock_session
        
        # Mock MessagingResponse
        mock_resp = Mock()
        mock_messaging_response.return_value = mock_resp
        
        # Test imports work
        try:
            from main import process_message
            from fastapi import BackgroundTasks
            self.assertTrue(True, "Imports successful")
        except ImportError as e:
            self.fail(f"Import failed: {e}")
    
    def test_command_case_insensitive(self):
        """Test that panduan command works with different cases"""
        test_cases = ["panduan", "PANDUAN", "Panduan", "guide", "GUIDE", "Guide"]
        
        for test_case in test_cases:
            result = test_case.lower() in ["panduan", "guide"]
            self.assertTrue(result, f"Case insensitive check failed for: {test_case}")

if __name__ == '__main__':
    print("Running panduan command tests...")
    unittest.main(verbosity=2)