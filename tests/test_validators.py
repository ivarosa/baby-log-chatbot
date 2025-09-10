# tests/test_validators.py
import pytest
from validators import InputValidator

class TestInputValidator:
    
    def test_validate_date_valid(self):
        """Test valid date formats"""
        valid, error = InputValidator.validate_date("2024-01-15")
        assert valid is True
        assert error is None
    
    def test_validate_date_invalid_format(self):
        """Test invalid date formats"""
        valid, error = InputValidator.validate_date("15-01-2024")
        assert valid is False
        assert "Format tanggal salah" in error
    
    def test_validate_date_future(self):
        """Test future dates are rejected"""
        from datetime import datetime, timedelta
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        valid, error = InputValidator.validate_date(future_date)
        assert valid is False
        assert "masa depan" in error
    
    def test_validate_time_valid(self):
        """Test valid time formats"""
        valid, error = InputValidator.validate_time("14:30")
        assert valid is True
        assert error is None
        
        # Test with dots (should be converted)
        valid, error = InputValidator.validate_time("14.30")
        assert valid is True
        assert error is None
    
    def test_validate_time_invalid(self):
        """Test invalid time formats"""
        valid, error = InputValidator.validate_time("25:30")
        assert valid is False
        
        valid, error = InputValidator.validate_time("14:70")
        assert valid is False
    
    def test_validate_weight_kg_valid(self):
        """Test valid weight values"""
        valid, error = InputValidator.validate_weight_kg("8.5")
        assert valid is True
        assert error is None
    
    def test_validate_weight_kg_invalid(self):
        """Test invalid weight values"""
        valid, error = InputValidator.validate_weight_kg("0.3")  # Too low
        assert valid is False
        
        valid, error = InputValidator.validate_weight_kg("60")   # Too high
        assert valid is False
    
    def test_validate_height_cm_valid(self):
        """Test valid height values"""
        valid, error = InputValidator.validate_height_cm("75.5")
        assert valid is True
        assert error is None
    
    def test_validate_height_cm_invalid(self):
        """Test invalid height values"""
        valid, error = InputValidator.validate_height_cm("20")   # Too low
        assert valid is False
        
        valid, error = InputValidator.validate_height_cm("200")  # Too high
        assert valid is False
    
    def test_validate_volume_ml_valid(self):
        """Test valid volume values"""
        valid, error = InputValidator.validate_volume_ml("120")
        assert valid is True
        assert error is None
    
    def test_validate_volume_ml_invalid(self):
        """Test invalid volume values"""
        valid, error = InputValidator.validate_volume_ml("0")     # Too low
        assert valid is False
        
        valid, error = InputValidator.validate_volume_ml("1500")  # Too high
        assert valid is False
    
    def test_validate_bristol_scale_valid(self):
        """Test valid Bristol scale values"""
        for i in range(1, 8):
            valid, error = InputValidator.validate_bristol_scale(str(i))
            assert valid is True
            assert error is None
    
    def test_validate_bristol_scale_invalid(self):
        """Test invalid Bristol scale values"""
        valid, error = InputValidator.validate_bristol_scale("0")
        assert valid is False
        
        valid, error = InputValidator.validate_bristol_scale("8")
        assert valid is False
    
    def test_sanitize_text_input(self):
        """Test text sanitization"""
        # Test SQL injection prevention
        dangerous_text = "'; DROP TABLE users; --"
        sanitized = InputValidator.sanitize_text_input(dangerous_text)
        assert "''" in sanitized  # Single quotes should be escaped
        assert "--" not in sanitized  # Comments should be removed
        
        # Test length limitation
        long_text = "a" * 600
        sanitized = InputValidator.sanitize_text_input(long_text, max_length=100)
        assert len(sanitized) == 100
