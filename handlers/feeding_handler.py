# handlers/feeding_handler.py
from datetime import datetime
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    save_mpasi, get_mpasi_summary, save_milk_intake, 
    get_milk_intake_summary, get_user_calorie_setting,
    set_user_calorie_setting, save_pumping, get_pumping_summary
)
from validators import InputValidator
from error_handler import ValidationError
import logging
import re

class FeedingHandler:
    """Handle feeding-related operations (MPASI, milk, pumping)"""
    
    def __init__(self, session_manager, db_pool):
        self.session_manager = session_manager
        self.db_pool = db_pool
    
    def handle_mpasi_logging(self, user: str, message: str) -> Response:
        """Handle MPASI logging flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        if message.lower() == "catat mpasi":
            session["state"] = "MPASI_DATE"
            session["data"] = {}
            reply = "Tanggal makan? (YYYY-MM-DD, atau ketik 'today')"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "MPASI_DATE":
            if message.lower().strip() == "today":
                session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                session["state"] = "MPASI_TIME"
                reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
            else:
                is_valid, error_msg = InputValidator.validate_date(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["date"] = message
                    session["state"] = "MPASI_TIME"
                    reply = "Jam makan? (format 24 jam, HH:MM, contoh: 07:30)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "MPASI_TIME":
            time_input = message.replace('.', ':')
            is_valid, error_msg = InputValidator.validate_time(time_input)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["time"] = time_input
                session["state"] = "MPASI_VOL"
                reply = "Berapa ml yang dimakan?"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "MPASI_VOL":
            is_valid, error_msg = InputValidator.validate_volume_ml(message)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["volume_ml"] = float(message)
                session["state"] = "MPASI_DETAIL"
                reply = "Makanan apa saja? (cth: nasi 50gr, ayam 30gr, wortel 20gr)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "MPASI_DETAIL":
            session["data"]["food_detail"] = InputValidator.sanitize_text_input(message, 200)
            session["state"] = "MPASI_GRAMS"
            reply = "Masukkan menu dan porsi MPASI (misal: nasi santan 5 sdm, ayam 1 potong), atau 'skip'."
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state
