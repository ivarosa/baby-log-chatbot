# tests/test_premium_growth_charts.py
"""Tests for premium growth chart generation"""
import pytest
import os
import tempfile
from datetime import date
from unittest.mock import patch, MagicMock

# Test with matplotlib available
try:
    from utils.premium_growth_charts import PremiumChartGenerator, CHART_MODULES_AVAILABLE
    MATPLOTLIB_AVAILABLE = CHART_MODULES_AVAILABLE
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    PremiumChartGenerator = None


@pytest.fixture
def sample_child_info():
    """Sample child info for testing"""
    return {
        'name': 'Test Baby',
        'gender': 'male',
        'dob': '2024-01-01',
        'height_cm': 50.0,
        'weight_kg': 3.5
    }


@pytest.fixture
def single_growth_data():
    """Single data point for testing"""
    return [
        {
            'date': date(2024, 1, 1),
            'height_cm': 50.0,
            'weight_kg': 3.5,
            'head_circum_cm': 35.0
        }
    ]


@pytest.fixture
def multiple_growth_data():
    """Multiple data points for testing"""
    return [
        {
            'date': date(2024, 1, 1),
            'height_cm': 50.0,
            'weight_kg': 3.5,
            'head_circum_cm': 35.0
        },
        {
            'date': date(2024, 1, 8),
            'height_cm': 51.0,
            'weight_kg': 3.7,
            'head_circum_cm': 35.5
        },
        {
            'date': date(2024, 1, 15),
            'height_cm': 52.0,
            'weight_kg': 4.0,
            'head_circum_cm': 36.0
        }
    ]


@pytest.mark.skipif(not MATPLOTLIB_AVAILABLE, reason="matplotlib not available")
class TestPremiumChartGenerator:
    """Test premium chart generation"""
    
    def test_single_data_point_chart(self, single_growth_data, sample_child_info):
        """Test chart generation with single data point"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = f.name
        
        try:
            result = PremiumChartGenerator.generate_weight_chart(
                single_growth_data, 
                sample_child_info, 
                output_path
            )
            
            assert result is True, "Chart generation should succeed with single data point"
            assert os.path.exists(output_path), "Chart file should be created"
            assert os.path.getsize(output_path) > 0, "Chart file should not be empty"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_multiple_data_points_chart(self, multiple_growth_data, sample_child_info):
        """Test chart generation with multiple data points"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = f.name
        
        try:
            result = PremiumChartGenerator.generate_weight_chart(
                multiple_growth_data, 
                sample_child_info, 
                output_path
            )
            
            assert result is True, "Chart generation should succeed with multiple data points"
            assert os.path.exists(output_path), "Chart file should be created"
            assert os.path.getsize(output_path) > 0, "Chart file should not be empty"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_no_data_chart(self, sample_child_info):
        """Test chart generation with no data"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = f.name
        
        try:
            result = PremiumChartGenerator.generate_weight_chart(
                [], 
                sample_child_info, 
                output_path
            )
            
            assert result is False, "Chart generation should fail with no data"
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_convert_tuple_to_dict(self):
        """Test tuple to dict conversion"""
        growth_records = [
            ('2024-01-01', 50.0, 3.5, 35.0),
            ('2024-01-08', 51.0, 3.7, 35.5),
        ]
        child_record = ('Test Baby', 'male', '2024-01-01', 50.0, 3.5)
        
        growth_data, child_info = PremiumChartGenerator.convert_tuple_to_dict(
            growth_records, 
            child_record
        )
        
        assert len(growth_data) == 2
        assert growth_data[0]['date'] == '2024-01-01'
        assert growth_data[0]['height_cm'] == 50.0
        assert growth_data[0]['weight_kg'] == 3.5
        assert growth_data[0]['head_circum_cm'] == 35.0
        
        assert child_info['name'] == 'Test Baby'
        assert child_info['gender'] == 'male'
        assert child_info['dob'] == '2024-01-01'
        assert child_info['height_cm'] == 50.0
        assert child_info['weight_kg'] == 3.5


def test_chart_modules_availability():
    """Test that we can check chart module availability"""
    if MATPLOTLIB_AVAILABLE:
        assert PremiumChartGenerator is not None
    # This test just validates the import logic works


def test_filename_sanitization_for_whatsapp_users():
    """
    Test that WhatsApp user identifiers are properly sanitized for filenames.
    This prevents URL issues when generating growth chart links.
    
    Issue: WhatsApp user identifiers like 'whatsapp:+6285261264323' contain
    special characters (: and +) that break URLs when used directly in filenames.
    """
    # Simulate the user identifier from WhatsApp
    user = "whatsapp:+6285261264323"
    
    # Apply the sanitization as done in child_handler.py
    safe_user = user.replace(':', '_').replace('+', '')
    chart_filename = f"growth_chart_{safe_user}.png"
    
    # Verify the filename doesn't contain problematic characters
    assert ':' not in chart_filename, "Colon should be removed from filename"
    assert '+' not in chart_filename, "Plus sign should be removed from filename"
    
    # Verify expected format
    expected = "growth_chart_whatsapp_6285261264323.png"
    assert chart_filename == expected, f"Expected {expected}, got {chart_filename}"
    
    # Verify the filename can be used in a URL without issues
    base_url = "http://localhost:8000"
    chart_url = f"{base_url}/static/{chart_filename}"
    expected_url = "http://localhost:8000/static/growth_chart_whatsapp_6285261264323.png"
    assert chart_url == expected_url, f"Expected {expected_url}, got {chart_url}"
    
    # Verify no problematic 'whatsapp:' pattern in URL
    assert 'whatsapp:' not in chart_url, "Original 'whatsapp:' identifier should not be in URL"


def test_filename_sanitization_multiple_formats():
    """Test sanitization works for various user identifier formats"""
    test_cases = [
        ("whatsapp:+6281234567890", "growth_chart_whatsapp_6281234567890.png"),
        ("whatsapp:+1234567890", "growth_chart_whatsapp_1234567890.png"),
        ("telegram:+9876543210", "growth_chart_telegram_9876543210.png"),
        ("user:test@example.com", "growth_chart_user_test@example.com.png"),  # @ is safe in URLs
    ]
    
    for user, expected_filename in test_cases:
        safe_user = user.replace(':', '_').replace('+', '')
        chart_filename = f"growth_chart_{safe_user}.png"
        assert chart_filename == expected_filename, f"For user {user}, expected {expected_filename}, got {chart_filename}"


def test_base_url_environment_variable():
    """Test that chart URL generation respects BASE_URL environment variable"""
    import os
    from chart_generator import format_chart_url
    
    # Save original BASE_URL if it exists
    original_base_url = os.environ.get('BASE_URL')
    
    try:
        # Test 1: Default localhost when BASE_URL is not set
        if 'BASE_URL' in os.environ:
            del os.environ['BASE_URL']
        
        user_phone = "whatsapp:+1234567890"
        chart_url = format_chart_url(user_phone, 'mpasi-milk')
        assert 'localhost:8000' in chart_url, f"Expected localhost in default URL, got: {chart_url}"
        
        # Test 2: Custom Railway URL when BASE_URL is set
        os.environ['BASE_URL'] = 'https://baby-log.up.railway.app'
        chart_url = format_chart_url(user_phone, 'mpasi-milk')
        assert chart_url.startswith('https://baby-log.up.railway.app/'), f"Expected Railway URL, got: {chart_url}"
        assert 'localhost' not in chart_url, f"Should not contain localhost when BASE_URL is set, got: {chart_url}"
        
        # Test 3: PDF report URL with BASE_URL
        pdf_url = format_chart_url(user_phone, 'pdf-report')
        assert pdf_url.startswith('https://baby-log.up.railway.app/report-mpasi-milk/'), f"Expected PDF URL with BASE_URL, got: {pdf_url}"
        
    finally:
        # Restore original BASE_URL
        if original_base_url:
            os.environ['BASE_URL'] = original_base_url
        elif 'BASE_URL' in os.environ:
            del os.environ['BASE_URL']
