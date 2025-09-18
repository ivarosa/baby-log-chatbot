#!/usr/bin/env python3
"""
Simple test to verify timezone handling for reminder system
"""
import pytz
from datetime import datetime, timedelta

# Define WIB timezone
WIB_TZ = pytz.timezone('Asia/Jakarta')

def test_time_in_range():
    """Test the _time_in_range logic"""
    
    def _time_in_range(start_str: str, end_str: str, check_time: datetime) -> bool:
        """Check if check_time is within start and end time range"""
        try:
            start_hour, start_minute = map(int, start_str.split(":"))
            end_hour, end_minute = map(int, end_str.split(":"))
            
            # Ensure we're working with timezone-aware datetime
            if check_time.tzinfo is None:
                check_time = WIB_TZ.localize(check_time)
            elif check_time.tzinfo != WIB_TZ:
                check_time = check_time.astimezone(WIB_TZ)
            
            # Create start and end times for the same date as check_time
            start_time = check_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            end_time = check_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            
            if start_time <= end_time:
                # Same day range (e.g., 08:00 to 18:00)
                return start_time <= check_time <= end_time
            else:
                # Over midnight range (e.g., 20:00 to 06:00)
                # Check if time is after start_time on same day OR before end_time on same day
                return check_time >= start_time or check_time <= end_time
                
        except Exception as e:
            print(f"Error in _time_in_range: {e}")
            return True  # Default to allowing reminder if parsing fails
    
    # Test with 20:00 to 06:00 range (overnight)
    start_time = "20:00"
    end_time = "06:00"
    
    # Test times that should be IN RANGE
    test_times_in_range = [
        "20:00",  # Exactly at start
        "21:00",  # Evening
        "23:00",  # Late evening
        "00:00",  # Midnight
        "02:00",  # Early morning
        "05:00",  # Early morning
        "06:00",  # Exactly at end
    ]
    
    # Test times that should be OUT OF RANGE
    test_times_out_of_range = [
        "06:01",  # Just after end
        "07:00",  # Morning
        "12:00",  # Noon
        "15:00",  # Afternoon
        "18:00",  # Evening but before start
        "19:59",  # Just before start
    ]
    
    print("Testing overnight time range (20:00 to 06:00):")
    print("=" * 50)
    
    # Get current date in WIB for testing
    now_wib = datetime.now(WIB_TZ)
    
    print("Times that SHOULD be in range:")
    for time_str in test_times_in_range:
        hour, minute = map(int, time_str.split(':'))
        test_time = now_wib.replace(hour=hour, minute=minute, second=0, microsecond=0)
        result = _time_in_range(start_time, end_time, test_time)
        status = "✓" if result else "✗"
        print(f"  {status} {time_str}: {result}")
    
    print("\nTimes that should be OUT OF range:")
    for time_str in test_times_out_of_range:
        hour, minute = map(int, time_str.split(':'))
        test_time = now_wib.replace(hour=hour, minute=minute, second=0, microsecond=0)
        result = _time_in_range(start_time, end_time, test_time)
        status = "✓" if not result else "✗"
        print(f"  {status} {time_str}: {result}")
    
    # Test 4-hour intervals from 20:00
    print(f"\nTesting 4-hour intervals starting from 20:00:")
    print("=" * 50)
    start_wib = now_wib.replace(hour=20, minute=0, second=0, microsecond=0)
    
    for i in range(6):  # Test 6 intervals (24 hours worth)
        test_time = start_wib + timedelta(hours=4*i)
        in_range = _time_in_range(start_time, end_time, test_time)
        status = "✓" if in_range else "✗"
        print(f"  {status} {test_time.strftime('%H:%M')} (T+{4*i}h): {in_range}")


def test_timezone_conversion():
    """Test timezone conversion between WIB and UTC"""
    print(f"\nTesting timezone conversion:")
    print("=" * 50)
    
    # Test time in WIB
    wib_time = datetime.now(WIB_TZ)
    print(f"Current time in WIB: {wib_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Convert to UTC
    utc_time = wib_time.astimezone(pytz.UTC)
    print(f"Same time in UTC: {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Remove timezone for database storage
    utc_naive = utc_time.replace(tzinfo=None)
    print(f"UTC naive (for DB): {utc_naive.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 20:00 WIB conversion
    wib_evening = wib_time.replace(hour=20, minute=0, second=0, microsecond=0)
    utc_evening = wib_evening.astimezone(pytz.UTC).replace(tzinfo=None)
    print(f"20:00 WIB = {utc_evening.strftime('%H:%M')} UTC")
    
    # Test 06:00 WIB conversion
    wib_morning = wib_time.replace(hour=6, minute=0, second=0, microsecond=0)
    utc_morning = wib_morning.astimezone(pytz.UTC).replace(tzinfo=None)
    print(f"06:00 WIB = {utc_morning.strftime('%H:%M')} UTC")


if __name__ == "__main__":
    test_time_in_range()
    test_timezone_conversion()