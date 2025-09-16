# handlers/feeding_handler.py
"""
Complete feeding operations handler - CORRECTED VERSION
Handles MPASI, milk intake, pumping, calorie calculations, and health tracking
"""
from datetime import datetime
from fastapi import BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    save_mpasi, get_mpasi_summary, save_milk_intake,
    get_milk_intake_summary, get_user_calorie_setting,
    set_user_calorie_setting, save_pumping, get_pumping_summary,
    save_poop, get_poop_log
)
from validators import InputValidator
from error_handler import ValidationError
from tier_management import get_tier_limits
import re


class FeedingHandler:
    """Handle all feeding-related operations"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
        
        # Create a mock app_logger to handle all the app_logger calls
        class MockAppLogger:
            def log_user_action(self, **kwargs):
                logger.info(f"User action: {kwargs}")
            
            def log_error(self, error, **kwargs):
                logger.error(f"Error: {error}, {kwargs}")
                return f"ERROR_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.app_logger = MockAppLogger()
    
    def handle_feeding_commands(self, user: str, message: str) -> Response:
        """Route feeding commands to appropriate handlers"""
        session = self.session_manager.get_session(user)
        
        # DEBUG
        print(f"DEBUG: message='{message}', message.lower()='{message.lower()}', session_state='{session.get('state')}'")
        
        # MPASI-related commands
        if (message.lower() == "catat mpasi" or 
            session["state"] and session["state"].startswith("MPASI")):
            return self.handle_mpasi_logging(user, message)
        
        # Milk intake commands
        elif (message.lower() == "catat susu" or 
              session["state"] and session["state"].startswith("MILK")):
            return self.handle_milk_logging(user, message)
        
        # Pumping commands
        elif (message.lower() == "catat pumping" or 
              session["state"] and session["state"].startswith("PUMP")):
            return self.handle_pumping_logging(user, message)
        
        # Calorie calculation
        elif (message.lower() == "hitung kalori susu" or 
              session["state"] and session["state"].startswith("CALC")):
            return self.handle_calorie_calculation(user, message)
        
        # Calorie settings
        elif (message.lower().startswith("set kalori") or
              message.lower() == "lihat kalori" or
              session["state"] and session["state"].startswith("SET_KALORI")):
            return self.handle_calorie_settings(user, message)
        
        # Health tracking (poop)
        elif (message.lower() in ["log poop", "catat bab"] or
              message.lower() in ["show poop log", "lihat riwayat bab"] or
              session["state"] and session["state"].startswith("POOP")):
            return self.handle_health_tracking(user, message)
        
        # Summary commands
        elif message.lower().startswith("lihat ringkasan"):
            return self.handle_summary_requests(user, message)
        
        else:
            return self._handle_unknown_feeding_command(user, message)
    
    def handle_mpasi_logging(self, user: str, message: str) -> Response:
        """Handle MPASI logging flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "catat mpasi":
                # Start MPASI logging flow
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
                    reply = "Makanan apa saja? (contoh: nasi 50gr, ayam 30gr, wortel 20gr)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_DETAIL":
                session["data"]["food_detail"] = InputValidator.sanitize_text_input(message, 200)
                session["state"] = "MPASI_GRAMS"
                reply = "Masukkan menu dan porsi MPASI untuk estimasi kalori (misal: nasi santan 5 sdm, ayam 1 potong), atau 'skip'."
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_GRAMS":
                if message.lower() != "skip":
                    session["data"]["food_grams"] = message
                    session["data"]["est_calories"] = None  # Will be updated by GPT
                else:
                    session["data"]["food_grams"] = ""
                    session["data"]["est_calories"] = None
                
                try:
                    save_mpasi(user, session["data"])
                    
                    # Log successful MPASI entry
                    self.logger.info(f"User action: user_id={user}, action='mpasi_logged', success=True, "
                                   f"details={{'volume_ml': {session['data']['volume_ml']}, "
                                   f"'food_detail': '{session['data']['food_detail']}'}}")
                    
                    reply = (
                        f"✅ Catatan MPASI tersimpan!\n\n"
                        f"Detail:\n"
                        f"• Tanggal: {session['data']['date']}\n"
                        f"• Jam: {session['data']['time']}\n"
                        f"• Volume: {session['data']['volume_ml']} ml\n"
                        f"• Makanan: {session['data']['food_detail']}\n\n"
                        f"Ketik 'lihat ringkasan mpasi' untuk melihat ringkasan lengkap."
                    )
                    
                    session["state"] = None
                    session["data"] = {}
                    
                except (ValueError, ValidationError) as e:
                    reply = f"❌ {str(e)}"
                    self.logger.info(f"User action: user_id={user}, action='mpasi_logged', success=False, "
                                   f"details={{'error': '{str(e)}'}}")
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_mpasi'})
                    reply = f"❌ Terjadi kesalahan saat menyimpan data MPASI. Kode error: {error_id}"
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks MPASI."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_mpasi_logging'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")
    
    def handle_milk_logging(self, user: str, message: str) -> Response:
        """Handle milk intake logging flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "catat susu":
                session["state"] = "MILK_DATE"
                session["data"] = {}
                reply = "Tanggal minum susu? (YYYY-MM-DD atau 'today')"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_DATE":
                if message.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    is_valid, error_msg = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    session["data"]["date"] = message
                
                session["state"] = "MILK_TIME"
                reply = "Jam berapa minum susu? (format 24 jam, HH:MM, contoh: 09:00)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_TIME":
                time_input = message.replace('.', ':')
                is_valid, error_msg = InputValidator.validate_time(time_input)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["time"] = time_input
                    session["state"] = "MILK_VOL"
                    reply = "Berapa ml yang diminum?"
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_VOL":
                is_valid, error_msg = InputValidator.validate_volume_ml(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["volume_ml"] = float(message)
                    session["state"] = "MILK_TYPE"
                    reply = "Susu apa yang diminum?\n• 'asi' untuk ASI\n• 'sufor' untuk susu formula"
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_TYPE":
                milk_type = message.lower()
                if milk_type == "asi":
                    session["data"]["milk_type"] = "asi"
                    session["state"] = "ASI_METHOD"
                    reply = "ASI diberikan bagaimana?\n• 'dbf' untuk direct breastfeeding\n• 'pumping' untuk hasil perahan"
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                elif milk_type == "sufor":
                    session["data"]["milk_type"] = "sufor"
                    # Calculate calories automatically
                    try:
                        user_kcal = get_user_calorie_setting(user)
                        session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                        session["state"] = "MILK_NOTE"
                        reply = (
                            f"✅ Kalori otomatis dihitung: {session['data']['sufor_calorie']:.2f} kkal\n\n"
                            f"Catatan tambahan? (atau ketik 'skip')"
                        )
                        self.session_manager.update_session(user, state=session["state"], data=session["data"])
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'get_calorie_setting'})
                        reply = f"❌ Gagal menghitung kalori. Kode error: {error_id}"
                else:
                    reply = "❌ Masukkan 'asi' untuk ASI atau 'sufor' untuk susu formula."
                
            elif session["state"] == "ASI_METHOD":
                method = message.lower()
                if method in ["dbf", "pumping"]:
                    session["data"]["asi_method"] = method
                    session["state"] = "MILK_NOTE"
                    reply = "Catatan tambahan? (atau ketik 'skip')"
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                else:
                    reply = "❌ Masukkan 'dbf' untuk direct breastfeeding atau 'pumping' untuk hasil perahan."
                
            elif session["state"] == "MILK_NOTE":
                # Validate required session data before processing
                required_fields = ["milk_type", "volume_ml", "date", "time"]
                missing_fields = [field for field in required_fields if field not in session["data"]]
                
                if missing_fields:
                    # Session data is corrupted, clear and restart
                    self.logger.warning(f"Invalid session data for MILK_NOTE state. Missing fields: {missing_fields}")
                    self.session_manager.clear_session(user)
                    reply = "❌ Sesi tidak valid. Silakan mulai catat susu dari awal dengan 'catat susu'."
                else:
                    note_text = "" if message.lower() == "skip" else InputValidator.sanitize_text_input(message, 200)
                    session["data"]["note"] = note_text
                    
                    # Ensure sufor_calorie is set for sufor entries
                    if session["data"]["milk_type"] == "sufor" and "sufor_calorie" not in session["data"]:
                        user_kcal = get_user_calorie_setting(user)
                        session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                
                    try:
                        save_milk_intake(user, session["data"])
                        
                        # Log successful milk intake
                        self.logger.info(f"User action: user_id={user}, action='milk_logged', success=True, "
                                       f"details={{'volume_ml': {session['data']['volume_ml']}, "
                                       f"'milk_type': '{session['data']['milk_type']}', "
                                       f"'calories': {session['data'].get('sufor_calorie', 0)}}}")
                        
                        extra = ""
                        if session["data"]["milk_type"] == "sufor":
                            extra = f" (kalori: {session['data']['sufor_calorie']:.2f} kkal)"
                        elif session["data"]["milk_type"] == "asi":
                            extra = f" ({session['data'].get('asi_method','')})"
                        
                        reply = (
                            f"✅ Catatan minum susu tersimpan!\n\n"
                            f"Detail:\n"
                            f"• Jam: {session['data']['time']}\n"
                            f"• Volume: {session['data']['volume_ml']} ml\n"
                            f"• Jenis: {session['data']['milk_type'].upper()}{extra}\n"
                            f"• Catatan: {session['data']['note'] or '-'}\n\n"
                            f"Ketik 'lihat ringkasan susu' untuk melihat ringkasan harian."
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                    except (ValueError, ValidationError) as e:
                        reply = f"❌ {str(e)}"
                        self.logger.info(f"User action: user_id={user}, action='milk_logged', success=False, "
                                       f"details={{'error': '{str(e)}'}}")
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_milk_intake'})
                        reply = f"❌ Terjadi kesalahan saat menyimpan data susu. Kode error: {error_id}"
                    
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks susu."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_milk_logging'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")
    
    def handle_calorie_settings(self, user: str, message: str) -> Response:
        """Handle calorie setting commands"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower().startswith("set kalori asi"):
                session["state"] = "SET_KALORI_ASI"
                session["data"] = {}
                reply = "Masukkan nilai kalori per ml ASI (default 0.67 kkal/ml):\n\nContoh: 0.67 atau tekan enter untuk default"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "SET_KALORI_ASI":
                val = message.strip()
                try:
                    kcal = 0.67 if val == "" else float(val.replace(",", "."))
                    if kcal <= 0 or kcal > 5:
                        reply = "❌ Nilai kalori harus antara 0.1 - 5.0 kkal/ml"
                    else:
                        set_user_calorie_setting(user, "asi", kcal)
                        
                        # Log setting change
                        self.logger.info(f"User action: user_id={user}, action='calorie_setting_updated', success=True, "
                                       f"details={{'milk_type': 'asi', 'new_value': {kcal}}}")
                        
                        reply = f"✅ Nilai kalori ASI berhasil diset ke {kcal} kkal/ml."
                        session["state"] = None
                        session["data"] = {}
                except ValueError:
                    reply = "❌ Format tidak valid. Masukkan angka (contoh: 0.67) atau tekan enter untuk default."
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif message.lower().startswith("set kalori sufor"):
                session["state"] = "SET_KALORI_SUFOR"
                session["data"] = {}
                reply = "Masukkan nilai kalori per ml susu formula (default 0.7 kkal/ml):\n\nContoh: 0.7 atau tekan enter untuk default"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "SET_KALORI_SUFOR":
                val = message.strip()
                try:
                    kcal = 0.7 if val == "" else float(val.replace(",", "."))
                    if kcal <= 0 or kcal > 5:
                        reply = "❌ Nilai kalori harus antara 0.1 - 5.0 kkal/ml"
                    else:
                        set_user_calorie_setting(user, "sufor", kcal)
                        
                        # Log setting change
                        self.logger.info(f"User action: user_id={user}, action='calorie_setting_updated', success=True, "
                                       f"details={{'milk_type': 'sufor', 'new_value': {kcal}}}")
                        
                        reply = f"✅ Nilai kalori susu formula berhasil diset ke {kcal} kkal/ml."
                        session["state"] = None
                        session["data"] = {}
                except ValueError:
                    reply = "❌ Format tidak valid. Masukkan angka (contoh: 0.7) atau tekan enter untuk default."
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif message.lower() == "lihat kalori":
                try:
                    settings = get_user_calorie_setting(user)
                    reply = (
                        f"Pengaturan Kalori Saat Ini:\n\n"
                        f"• ASI: {settings['asi']} kkal/ml\n"
                        f"• Susu Formula: {settings['sufor']} kkal/ml\n\n"
                        f"Untuk mengubah:\n"
                        f"• 'set kalori asi' untuk ASI\n"
                        f"• 'set kalori sufor' untuk susu formula"
                    )
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'get_calorie_settings'})
                    reply = f"❌ Gagal mengambil pengaturan kalori. Kode error: {error_id}"
            
            else:
                reply = "Perintah tidak dikenali dalam konteks pengaturan kalori."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_calorie_settings'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")

    def handle_calorie_calculation(self, user: str, message: str) -> Response:
        """Handle calorie calculation for milk"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "hitung kalori susu":
                session["state"] = "CALC_MILK_VOL"
                session["data"] = {}
                reply = "Masukkan jumlah susu (ml):"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "CALC_MILK_VOL":
                is_valid, error_msg = InputValidator.validate_volume_ml(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["volume_ml"] = float(message)
                    session["state"] = "CALC_MILK_JENIS"
                    reply = "Jenis susu?\n• 'asi' untuk ASI\n• 'sufor' untuk susu formula"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "CALC_MILK_JENIS":
                jenis = message.lower().strip()
                if jenis not in ["asi", "sufor"]:
                    reply = "❌ Masukkan 'asi' untuk ASI atau 'sufor' untuk susu formula."
                else:
                    try:
                        kcal_settings = get_user_calorie_setting(user)
                        kcal_per_ml = kcal_settings[jenis]
                        total_calories = session["data"]["volume_ml"] * kcal_per_ml
                        
                        # Log calorie calculation
                        self.logger.info(f"User action: user_id={user}, action='calorie_calculated', success=True, "
                                       f"details={{'volume_ml': {session['data']['volume_ml']}, "
                                       f"'milk_type': '{jenis}', 'calories': {total_calories}}}")
                        
                        reply = (
                            f"Hasil Kalkulasi Kalori:\n\n"
                            f"• Volume: {session['data']['volume_ml']} ml\n"
                            f"• Jenis: {jenis.upper()}\n"
                            f"• Kalori per ml: {kcal_per_ml} kkal\n"
                            f"• Total kalori: {total_calories:.2f} kkal\n\n"
                            f"Untuk mengubah nilai kalori per ml:\n"
                            f"• 'set kalori asi' untuk ASI\n"
                            f"• 'set kalori sufor' untuk susu formula"
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'calculate_calories'})
                        reply = f"❌ Terjadi kesalahan saat menghitung kalori. Kode error: {error_id}"
                    
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks kalkulasi kalori."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_calorie_calculation'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")

    def handle_pumping_logging(self, user: str, message: str) -> Response:
        """Handle pumping logging flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "catat pumping":
                session["state"] = "PUMP_DATE"
                session["data"] = {}
                reply = "Tanggal pumping? (YYYY-MM-DD, atau 'today')"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "PUMP_DATE":
                if message.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    is_valid, error_msg = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    session["data"]["date"] = message
                
                session["state"] = "PUMP_TIME"
                reply = "Pukul berapa pumping? (format 24 jam, HH:MM, contoh: 07:30)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "PUMP_TIME":
                time_input = message.replace('.', ':')
                is_valid, error_msg = InputValidator.validate_time(time_input)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["time"] = time_input
                    session["state"] = "PUMP_LEFT"
                    reply = "Jumlah ASI dari payudara kiri (ml)? (masukkan 0 jika tidak ada)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "PUMP_LEFT":
                try:
                    left_ml = float(message)
                    if left_ml < 0 or left_ml > 1000:
                        reply = "❌ Volume harus antara 0-1000 ml"
                    else:
                        session["data"]["left_ml"] = left_ml
                        session["state"] = "PUMP_RIGHT"
                        reply = "Jumlah ASI dari payudara kanan (ml)? (masukkan 0 jika tidak ada)"
                except ValueError:
                    reply = "❌ Masukkan angka yang valid untuk volume ASI (ml)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "PUMP_RIGHT":
                try:
                    right_ml = float(message)
                    if right_ml < 0 or right_ml > 1000:
                        reply = "❌ Volume harus antara 0-1000 ml"
                    else:
                        session["data"]["right_ml"] = right_ml
                        session["state"] = "PUMP_BAGS"
                        reply = "Berapa kantong ASI yang disimpan? (masukkan 0 jika langsung diminum)"
                except ValueError:
                    reply = "❌ Masukkan angka yang valid untuk volume ASI (ml)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "PUMP_BAGS":
                try:
                    bags = int(message)
                    if bags < 0 or bags > 50:
                        reply = "❌ Jumlah kantong harus antara 0-50"
                    else:
                        session["data"]["milk_bags"] = bags
                        
                        save_pumping(user, session["data"])
                        
                        total_ml = session["data"]["left_ml"] + session["data"]["right_ml"]
                        
                        # Log successful pumping
                        self.logger.info(f"User action: user_id={user}, action='pumping_logged', success=True, "
                                       f"details={{'total_ml': {total_ml}, 'left_ml': {session['data']['left_ml']}, "
                                       f"'right_ml': {session['data']['right_ml']}, 'bags': {session['data']['milk_bags']}}}")
                        
                        reply = (
                            f"✅ Catatan pumping tersimpan!\n\n"
                            f"Detail:\n"
                            f"• Tanggal: {session['data']['date']} {session['data']['time']}\n"
                            f"• Total ASI: {total_ml} ml\n"
                            f"• Payudara kiri: {session['data']['left_ml']} ml\n"
                            f"• Payudara kanan: {session['data']['right_ml']} ml\n"
                            f"• Kantong disimpan: {session['data']['milk_bags']}\n\n"
                            f"Ketik 'lihat ringkasan pumping' untuk melihat ringkasan lengkap."
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                except ValueError:
                    reply = "❌ Masukkan angka bulat untuk jumlah kantong ASI"
                except (ValidationError) as e:
                    reply = f"❌ {str(e)}"
                    self.logger.info(f"User action: user_id={user}, action='pumping_logged', success=False, "
                                   f"details={{'error': '{str(e)}'}}")
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_pumping'})
                    reply = f"❌ Terjadi kesalahan saat menyimpan data pumping. Kode error: {error_id}"
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks pumping."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_pumping_logging'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")

    def handle_health_tracking(self, user: str, message: str) -> Response:
        """Handle health tracking (poop logging)"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() in ["log poop", "catat bab"]:
                session["state"] = "POOP_DATE"
                session["data"] = {}
                reply = "Tanggal BAB? (YYYY-MM-DD, atau 'today')"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "POOP_DATE":
                if message.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    is_valid, error_msg = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    session["data"]["date"] = message
                
                session["state"] = "POOP_TIME"
                reply = "Jam berapa BAB? (format 24 jam, HH:MM, contoh: 07:30)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "POOP_TIME":
                time_input = message.replace('.', ':')
                is_valid, error_msg = InputValidator.validate_time(time_input)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["time"] = time_input
                    session["state"] = "POOP_BRISTOL"
                    reply = (
                        f"Tekstur feses (Skala Bristol 1-7):\n\n"
                        f"1: Sangat keras (seperti kacang-kacang)\n"
                        f"2: Berbentuk sosis, bergelombang\n"
                        f"3: Sosis dengan retakan di permukaan\n"
                        f"4: Lembut, berbentuk sosis (normal)\n"
                        f"5: Potongan-potongan lunak\n"
                        f"6: Potongan lembek, tepi bergerigi\n"
                        f"7: Cair, tanpa bentuk padat\n\n"
                        f"Masukkan angka 1-7 sesuai tekstur:"
                    )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "POOP_BRISTOL":
                try:
                    bristol = int(message)
                    if 1 <= bristol <= 7:
                        session["data"]["bristol_scale"] = bristol
                        
                        save_poop(user, session["data"])
                        
                        # Log successful poop entry
                        self.logger.info(f"User action: user_id={user}, action='poop_logged', success=True, "
                                       f"details={{'bristol_scale': {bristol}, 'date': '{session['data']['date']}', "
                                       f"'time': '{session['data']['time']}'}}")
                        
                        bristol_desc = {
                            1: "Sangat keras (konstipasi)",
                            2: "Keras (konstipasi ringan)",
                            3: "Normal (sedikit keras)",
                            4: "Normal (ideal)",
                            5: "Normal (lembut)",
                            6: "Lembek (diare ringan)", 
                            7: "Cair (diare)"
                        }
                        
                        reply = (
                            f"✅ Catatan BAB tersimpan!\n\n"
                            f"Detail:\n"
                            f"• Tanggal: {session['data']['date']} {session['data']['time']}\n"
                            f"• Skala Bristol: {bristol}\n"
                            f"• Kondisi: {bristol_desc[bristol]}\n\n"
                            f"Ketik 'lihat riwayat bab' untuk melihat riwayat lengkap."
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                    else:
                        reply = "❌ Masukkan angka 1-7 untuk skala Bristol."
                        
                except ValueError:
                    reply = "❌ Masukkan angka 1-7 untuk skala Bristol."
                except (ValidationError) as e:
                    reply = f"❌ {str(e)}"
                    self.logger.info(f"User action: user_id={user}, action='poop_logged', success=False, "
                                   f"details={{'error': '{str(e)}'}}")
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_poop'})
                    reply = f"❌ Terjadi kesalahan saat menyimpan data BAB. Kode error: {error_id}"
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif message.lower() in ["show poop log", "lihat riwayat bab"]:
                try:
                    logs = get_poop_log(user)
                    if logs:
                        reply = "Riwayat BAB:\n\n"
                        bristol_status = {
                            1: "Sangat keras", 2: "Keras", 3: "Normal-keras",
                            4: "Normal", 5: "Normal-lembut", 6: "Lembek", 7: "Cair"
                        }
                        
                        for i, log in enumerate(logs[:10], 1):  # Show last 10 entries
                            if isinstance(log, (list, tuple)):
                                date_val, time_val, bristol = log[0], log[1], log[2]
                            else:
                                date_val = log.get('date', '-')
                                time_val = log.get('time', '-')
                                bristol = log.get('bristol_scale', '-')
                            
                            status = bristol_status.get(bristol, f"Skala {bristol}")
                            reply += f"{i}. {date_val} {time_val} - {status}\n"
                        
                        if len(logs) > 10:
                            reply += f"\n... dan {len(logs) - 10} catatan lainnya"
                        
                        # Add tier info for free users
                        limits = get_tier_limits(user)
                        if limits.get("history_days"):
                            reply += f"\n\nTier gratis dibatasi {limits['history_days']} hari riwayat."
                    else:
                        reply = "Belum ada catatan BAB. Ketik 'catat bab' untuk menambah data."
                        
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'get_poop_log'})
                    reply = f"❌ Terjadi kesalahan saat mengambil riwayat BAB. Kode error: {error_id}"
            
            else:
                reply = "Perintah tidak dikenali dalam konteks kesehatan."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_health_tracking'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")

    def handle_summary_requests(self, user: str, message: str) -> Response:
        """Handle summary request commands"""
        resp = MessagingResponse()
        
        try:
            # Extract date from message if provided
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
            if "today" in message.lower() or "hari ini" in message.lower():
                summary_date = datetime.now().strftime("%Y-%m-%d")
            elif date_match:
                summary_date = date_match.group(0)
            else:
                summary_date = datetime.now().strftime("%Y-%m-%d")
            
            if "mpasi" in message.lower():
                reply = self._generate_mpasi_summary(user, summary_date)
            elif "susu" in message.lower() or "milk" in message.lower():
                reply = self._generate_milk_summary(user, summary_date)
            elif "pumping" in message.lower():
                reply = self._generate_pumping_summary(user, summary_date)
            elif "kalori" in message.lower():
                reply = self._generate_calorie_summary(user, summary_date)
            else:
                reply = self._generate_feeding_overview(user, summary_date)
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_summary_requests'})
            resp.message(f"❌ Terjadi kesalahan saat mengambil ringkasan. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")

    def _generate_mpasi_summary(self, user: str, date: str) -> str:
        """Generate MPASI summary for given date"""
        try:
            rows = get_mpasi_summary(user, date, date)
            if not rows:
                return f"Belum ada catatan MPASI pada {date}.\n\nKetik 'catat mpasi' untuk menambah data."
            
            total_ml = sum([row[2] or 0 for row in rows])
            total_cal = sum([row[5] or 0 for row in rows])
            
            reply = (
                f"Ringkasan MPASI ({date})\n\n"
                f"• Total sesi makan: {len(rows)}\n"
                f"• Total volume: {total_ml} ml\n"
                f"• Estimasi kalori: {total_cal} kkal\n\n"
                f"Detail per sesi:\n"
            )
            
            for i, row in enumerate(rows[:5], 1):  # Show last 5 entries
                time_val = row[1] if len(row) > 1 else '-'
                volume = row[2] if len(row) > 2 else 0
                food = row[3] if len(row) > 3 else 'Tidak ada detail'
                calories = row[5] if len(row) > 5 and row[5] else 0
                
                reply += f"{i}. {time_val} - {volume}ml ({calories} kkal)\n   {food[:50]}{'...' if len(food) > 50 else ''}\n\n"
            
            if len(rows) > 5:
                reply += f"... dan {len(rows) - 5} sesi lainnya"
            
            return reply
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_generate_mpasi_summary'})
            return f"❌ Gagal mengambil ringkasan MPASI. Kode error: {error_id}"

    def _generate_milk_summary(self, user: str, date: str) -> str:
        """Generate milk summary for given date, robust to missing keys."""
        try:
            rows = get_milk_intake_summary(user, date, date)
            if not rows:
                return f"Belum ada catatan minum susu/ASI pada {date}.\n\nKetik 'catat susu' untuk menambah data."

            total_count = 0
            total_ml = 0
            total_cal = 0

            for r in rows:
                # r can be tuple/list or dict
                if isinstance(r, (list, tuple)):
                    total_count += r[2] if len(r) > 2 and r[2] else 0
                    total_ml += r[3] if len(r) > 3 and r[3] else 0
                    total_cal += r[4] if len(r) > 4 and r[4] else 0
                elif isinstance(r, dict):
                    total_count += r.get("count", 0)
                    total_ml += r.get("volume_ml", 0)
                    total_cal += r.get("calories", 0)
                else:
                    continue

            reply = (
                f"Ringkasan Susu/ASI ({date})\n\n"
                f"• Total sesi minum: {total_count}\n"
                f"• Total volume: {total_ml} ml\n"
                f"• Total kalori: {total_cal:.1f} kkal\n\n"
                f"Detail per jenis:\n"
            )

            for r in rows:
                if isinstance(r, (list, tuple)):
                    milk_type = r[0] if len(r) > 0 else "-"
                    asi_method = r[1] if len(r) > 1 else ""
                    count = r[2] if len(r) > 2 else 0
                    volume = r[3] if len(r) > 3 else 0
                    calories = r[4] if len(r) > 4 and r[4] else 0
                elif isinstance(r, dict):
                    milk_type = r.get("milk_type", "-")
                    asi_method = r.get("asi_method", "")
                    count = r.get("count", 0)
                    volume = r.get("volume_ml", 0)
                    calories = r.get("calories", 0)
                else:
                    continue

                if milk_type == 'asi':
                    method_text = f" ({asi_method})" if asi_method else ""
                    reply += f"• ASI{method_text}: {count}x, {volume} ml\n"
                else:
                    reply += f"• Sufor: {count}x, {volume} ml ({calories:.1f} kkal)\n"

            return reply
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_generate_milk_summary'})
            return f"❌ Gagal mengambil ringkasan susu. Kode error: {error_id}"

    def _generate_pumping_summary(self, user: str, date: str) -> str:
        """Generate pumping summary for given date"""
        try:
            rows = get_pumping_summary(user, date, date)
            if not rows:
                return f"Belum ada catatan pumping pada {date}.\n\nKetik 'catat pumping' untuk menambah data."
            
            total_sessions = len(rows)
            total_left = sum([row[2] or 0 for row in rows])
            total_right = sum([row[3] or 0 for row in rows])
            total_ml = total_left + total_right
            total_bags = sum([row[4] or 0 for row in rows])
            
            reply = (
                f"Ringkasan Pumping ({date})\n\n"
                f"• Total sesi: {total_sessions}\n"
                f"• Total ASI: {total_ml} ml\n"
                f"• Payudara kiri: {total_left} ml\n"
                f"• Payudara kanan: {total_right} ml\n"
                f"• Total kantong: {total_bags}\n\n"
                f"Detail per sesi:\n"
            )
            
            for i, row in enumerate(rows[:5], 1):  # Show last 5 sessions
                time_val = row[1] if len(row) > 1 else '-'
                left_ml = row[2] if len(row) > 2 else 0
                right_ml = row[3] if len(row) > 3 else 0
                bags = row[4] if len(row) > 4 else 0
                session_total = left_ml + right_ml
                
                reply += f"{i}. {time_val} - {session_total}ml (L:{left_ml}, R:{right_ml}, Kantong:{bags})\n"
            
            if len(rows) > 5:
                reply += f"\n... dan {len(rows) - 5} sesi lainnya"
            
            return reply
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_generate_pumping_summary'})
            return f"❌ Gagal mengambil ringkasan pumping. Kode error: {error_id}"
    
    def _generate_calorie_summary(self, user: str, date: str) -> str:
        """Generate calorie summary from all sources, robust to missing keys."""
        try:
            # Get MPASI calories
            mpasi_rows = get_mpasi_summary(user, date, date)
            mpasi_calories = sum([row[5] if len(row) > 5 and row[5] else 0 for row in mpasi_rows if isinstance(row, (list, tuple))])

            # Get milk calories
            milk_rows = get_milk_intake_summary(user, date, date)
            milk_calories = 0
            for r in milk_rows:
                if isinstance(r, (list, tuple)):
                    milk_calories += r[4] if len(r) > 4 and r[4] else 0
                elif isinstance(r, dict):
                    milk_calories += r.get("calories", 0)

            total_calories = mpasi_calories + milk_calories

            if total_calories == 0:
                return f"Belum ada catatan kalori pada {date}.\n\nMulai dengan 'catat mpasi' atau 'catat susu'."

            # Calculate percentages
            mpasi_percent = (mpasi_calories / total_calories * 100) if total_calories > 0 else 0
            milk_percent = (milk_calories / total_calories * 100) if total_calories > 0 else 0

            return (
                f"Ringkasan Kalori ({date})\n\n"
                f"• Total kalori: {total_calories:.1f} kkal\n\n"
                f"Sumber kalori:\n"
                f"• MPASI: {mpasi_calories:.1f} kkal ({mpasi_percent:.1f}%)\n"
                f"• Susu/ASI: {milk_calories:.1f} kkal ({milk_percent:.1f}%)\n\n"
                f"Detail:\n"
                f"• Sesi MPASI: {len(mpasi_rows)}\n"
                f"• Sesi minum: {sum([r[2] if len(r) > 2 and r[2] else 0 for r in milk_rows if isinstance(r, (list, tuple))])}\n\n"
                f"Ketik 'hitung kalori susu' untuk kalkulator kalori"
            )
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_generate_calorie_summary'})
            return f"❌ Gagal mengambil ringkasan kalori. Kode error: {error_id}"
    
    def _generate_feeding_overview(self, user: str, date: str) -> str:
        """Generate comprehensive feeding overview, robust to missing keys."""
        try:
            # Check if there's any feeding data for the date
            mpasi_rows = get_mpasi_summary(user, date, date)
            milk_rows = get_milk_intake_summary(user, date, date)
            pumping_rows = get_pumping_summary(user, date, date)

            has_mpasi = bool(mpasi_rows)
            has_milk = bool(milk_rows)
            has_pumping = bool(pumping_rows)

            if not any([has_mpasi, has_milk, has_pumping]):
                return (
                    f"Ringkasan Makan & Minum ({date})\n\n"
                    f"Belum ada catatan untuk hari ini.\n\n"
                    f"Mulai mencatat:\n"
                    f"• 'catat mpasi' untuk makanan\n"
                    f"• 'catat susu' untuk ASI/sufor\n"
                    f"• 'catat pumping' untuk ASI perah"
                )

            overview_lines = [f"Ringkasan Makan & Minum ({date})\n"]

            if has_mpasi:
                mpasi_count = len(mpasi_rows)
                mpasi_total_ml = sum([row[2] if len(row) > 2 and row[2] else 0 for row in mpasi_rows if isinstance(row, (list, tuple))])
                mpasi_total_cal = sum([row[5] if len(row) > 5 and row[5] else 0 for row in mpasi_rows if isinstance(row, (list, tuple))])
                overview_lines.append(f"• MPASI: {mpasi_count} sesi, {mpasi_total_ml}ml, {mpasi_total_cal} kkal")

            if has_milk:
                milk_count = sum([r[2] if len(r) > 2 and r[2] else 0 for r in milk_rows if isinstance(r, (list, tuple))])
                milk_total_ml = sum([r[3] if len(r) > 3 and r[3] else 0 for r in milk_rows if isinstance(r, (list, tuple))])
                milk_total_cal = sum([r[4] if len(r) > 4 and r[4] else 0 for r in milk_rows if isinstance(r, (list, tuple))])
                overview_lines.append(f"• Susu/ASI: {milk_count} sesi, {milk_total_ml}ml, {milk_total_cal:.1f} kkal")

            if has_pumping:
                pumping_count = len(pumping_rows)
                pumping_total_ml = sum([(row[2] if len(row) > 2 and row[2] else 0) + (row[3] if len(row) > 3 and row[3] else 0) for row in pumping_rows if isinstance(row, (list, tuple))])
                pumping_bags = sum([row[4] if len(row) > 4 and row[4] else 0 for row in pumping_rows if isinstance(row, (list, tuple))])
                overview_lines.append(f"• Pumping: {pumping_count} sesi, {pumping_total_ml}ml, {pumping_bags} kantong")

            overview_lines.extend([
                "",
                "Detail lebih lanjut:",
                "• 'lihat ringkasan mpasi'",
                "• 'lihat ringkasan susu'",
                "• 'lihat ringkasan pumping'",
                "• 'lihat ringkasan kalori'"
            ])

            return "\n".join(overview_lines)

        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_generate_feeding_overview'})
            return f"❌ Gagal mengambil ringkasan umum. Kode error: {error_id}"
    
    def _handle_unknown_feeding_command(self, user: str, message: str) -> Response:
        """Handle unknown feeding commands"""
        resp = MessagingResponse()
        
        self.logger.info(f"User action: user_id={user}, action='unknown_feeding_command', success=False, "
                       f"details={{'message': '{message}'}}")
        
        reply = (
            f"Perintah tidak dikenali dalam konteks makan/minum: '{message[:30]}...'\n\n"
            f"Perintah yang tersedia:\n"
            f"• 'catat mpasi' - log makanan bayi\n"
            f"• 'catat susu' - log ASI/sufor\n"
            f"• 'catat pumping' - log ASI perah\n"
            f"• 'hitung kalori susu' - kalkulator kalori\n"
            f"• 'lihat ringkasan mpasi/susu' - lihat ringkasan\n"
            f"• 'catat bab' - log kesehatan pencernaan\n\n"
            f"Ketik 'help' untuk bantuan lengkap."
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
