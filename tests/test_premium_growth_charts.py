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
