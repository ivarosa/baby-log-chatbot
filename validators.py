import re
from datetime import datetime
from typing import Optional, Tuple

class InputValidator:
    """Centralized input validation"""
    
    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate WhatsApp phone number format
        Returns: (is_valid, error_message)
        """
        # Pattern: whatsapp:+[country_code][number]
        pattern = r'^whatsapp:\+\d{10,15}$'
        
        if not phone:
            return False, "Nomor telepon tidak boleh kosong"
        
        if not re.match(pattern, phone):
            return False, "Format nomor tidak valid. Format: whatsapp:+628xxx"
        
        return True, None
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
        """Validate date format YYYY-MM-DD"""
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Check if date is not in future
            if parsed_date.date() > datetime.now().date():
                return False, "Tanggal tidak boleh di masa depan"
            
            # Check if date is not too old (e.g., 5 years)
            if (datetime.now() - parsed_date).days > 1825:
                return False, "Tanggal terlalu lama (maksimal 5 tahun)"
            
            return True, None
        except ValueError:
            return False, "Format tanggal salah. Gunakan YYYY-MM-DD"
    
    @staticmethod
    def validate_time(time_str: str) -> Tuple[bool, Optional[str]]:
        """Validate time format HH:MM"""
        time_str = time_str.replace('.', ':')  # Handle common typo
        
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            return False, "Format waktu salah. Gunakan HH:MM (contoh: 09:30)"
        
        try:
            datetime.strptime(time_str, "%H:%M")
            return True, None
        except ValueError:
            return False, "Waktu tidak valid. Gunakan format 24 jam (00:00 - 23:59)"
    
    @staticmethod
    def validate_number(value: str, min_val: float = None, 
                       max_val: float = None, allow_decimal: bool = True) -> Tuple[bool, Optional[str]]:
        """Validate numeric input"""
        try:
            if allow_decimal:
                num = float(value.replace(',', '.'))
            else:
                num = int(value)
            
            if min_val is not None and num < min_val:
                return False, f"Nilai minimal adalah {min_val}"
            
            if max_val is not None and num > max_val:
                return False, f"Nilai maksimal adalah {max_val}"
            
            return True, None
        except ValueError:
            return False, "Masukkan angka yang valid"
    
    @staticmethod
    def validate_bristol_scale(value: str) -> Tuple[bool, Optional[str]]:
        """Validate Bristol Stool Scale (1-7)"""
        is_valid, error = InputValidator.validate_number(
            value, min_val=1, max_val=7, allow_decimal=False
        )
        if not is_valid:
            return False, "Skala Bristol harus antara 1-7"
        return True, None
    
    @staticmethod
    def validate_weight(value: str) -> Tuple[bool, Optional[str]]:
        """Validate weight in kg (0.5 - 50 kg for babies)"""
        is_valid, error = InputValidator.validate_number(
            value, min_val=0.5, max_val=50
        )
        if not is_valid:
            return False, "Berat badan bayi harus antara 0.5 - 50 kg"
        return True, None
    
    @staticmethod
    def validate_height(value: str) -> Tuple[bool, Optional[str]]:
        """Validate height in cm (30 - 150 cm for babies/toddlers)"""
        is_valid, error = InputValidator.validate_number(
            value, min_val=30, max_val=150
        )
        if not is_valid:
            return False, "Tinggi badan harus antara 30 - 150 cm"
        return True, None
    
    @staticmethod
    def validate_volume_ml(value: str) -> Tuple[bool, Optional[str]]:
        """Validate volume in ml (1 - 1000 ml)"""
        is_valid, error = InputValidator.validate_number(
            value, min_val=1, max_val=1000
        )
        if not is_valid:
            return False, "Volume harus antara 1 - 1000 ml"
        return True, None
    
    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 500) -> str:
        """Sanitize free text input"""
        # Remove any potential SQL injection attempts
        text = text.replace("'", "''")
        text = text.replace('"', '""')
        text = text.replace(';', '')
        text = text.replace('--', '')
        text = text.replace('/*', '')
        text = text.replace('*/', '')
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()

# Integration in main.py - Example for MPASI flow:
elif session["state"] == "MPASI_DATE":
    if msg.lower().strip() == "today":
        session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
        session["state"] = "MPASI_TIME"
        reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
    else:
        # Validate date input
        is_valid, error_msg = InputValidator.validate_date(msg)
        if not is_valid:
            reply = f"❌ {error_msg}"
        else:
            session["data"]["date"] = msg
            session["state"] = "MPASI_TIME"
            reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
    user_sessions[user] = session
    resp.message(reply)
    return Response(str(resp), media_type="application/xml")

elif session["state"] == "MPASI_VOL":
    # Validate volume input
    is_valid, error_msg = InputValidator.validate_volume_ml(msg)
    if not is_valid:
        reply = f"❌ {error_msg}"
    else:
        session["data"]["volume_ml"] = float(msg)
        session["state"] = "MPASI_DETAIL"
        reply = "Makanan apa saja? (cth: nasi 50gr, ayam 30gr, wortel 20gr)"
    user_sessions[user] = session
    resp.message(reply)
    return Response(str(resp), media_type="application/xml")
