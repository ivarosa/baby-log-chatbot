# validators.py - Production minimal version
import re
from datetime import datetime
from typing import Optional, Tuple

class InputValidator:
    """Minimal input validation for production"""
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
        """Validate date format YYYY-MM-DD"""
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            if parsed_date.date() > datetime.now().date():
                return False, "Tanggal tidak boleh di masa depan"
            return True, None
        except ValueError:
            return False, "Format tanggal salah. Gunakan YYYY-MM-DD"
    
    @staticmethod
    def validate_time(time_str: str) -> Tuple[bool, Optional[str]]:
        """Validate time format HH:MM"""
        time_str = time_str.replace('.', ':')
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            return False, "Format waktu salah. Gunakan HH:MM"
        try:
            datetime.strptime(time_str, "%H:%M")
            return True, None
        except ValueError:
            return False, "Waktu tidak valid"
    
    @staticmethod
    def validate_weight_kg(value: str) -> Tuple[bool, Optional[str]]:
        """Validate weight in kg"""
        try:
            weight = float(value.replace(',', '.'))
            if weight < 0.5 or weight > 50:
                return False, "Berat badan harus antara 0.5 - 50 kg"
            return True, None
        except ValueError:
            return False, "Masukkan angka yang valid untuk berat badan"
    
    @staticmethod
    def validate_height_cm(value: str) -> Tuple[bool, Optional[str]]:
        """Validate height in cm"""
        try:
            height = float(value.replace(',', '.'))
            if height < 30 or height > 150:
                return False, "Tinggi badan harus antara 30 - 150 cm"
            return True, None
        except ValueError:
            return False, "Masukkan angka yang valid untuk tinggi badan"
    
    @staticmethod
    def validate_volume_ml(value: str) -> Tuple[bool, Optional[str]]:
        """Validate volume in ml"""
        try:
            volume = float(value.replace(',', '.'))
            if volume < 1 or volume > 1000:
                return False, "Volume harus antara 1 - 1000 ml"
            return True, None
        except ValueError:
            return False, "Masukkan angka yang valid untuk volume"
    
    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 500) -> str:
        """Sanitize text input"""
        if not text:
            return ""
        
        # Basic sanitization
        text = text.replace("'", "''")
        text = text.replace('"', '""')
        text = re.sub(r'[;<>]', '', text)
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
