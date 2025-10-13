# handlers/onboarding_handler.py
"""
Smart Onboarding Handler for New Users
Guides users through initial setup in ~2 minutes
"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import save_child, get_child
from validators import InputValidator
import re

class OnboardingHandler:
    """Handle progressive onboarding for new users"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
    
    def is_new_user(self, user: str) -> bool:
        """Check if user has completed onboarding"""
        try:
            child_data = get_child(user)
            return child_data is None
        except:
            return True
    
    def handle_onboarding(self, user: str, message: str) -> Response:
        """Main onboarding flow handler"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        # Check if user wants to exit onboarding
        if message.lower() in ["batal", "cancel", "keluar", "exit"]:
            self.session_manager.clear_session(user)
            resp.message(
                "👋 Onboarding dibatalkan.\n\n"
                "Ketik 'start' atau 'mulai' kapanpun untuk mulai lagi!"
            )
            return Response(str(resp), media_type="application/xml")
        
        # Get current onboarding state
        onboarding_state = session.get("state")
        
        # STAGE 0: First contact - welcome message
        if not onboarding_state or onboarding_state == "NEW_USER":
            return self._send_welcome_message(user)
        
        # STAGE 1: Collect baby name
        elif onboarding_state == "ONBOARD_NAME":
            return self._handle_name_input(user, message)
        
        # STAGE 2: Collect gender
        elif onboarding_state == "ONBOARD_GENDER":
            return self._handle_gender_input(user, message)
        
        # STAGE 3: Collect birth date
        elif onboarding_state == "ONBOARD_DOB":
            return self._handle_dob_input(user, message)
        
        # STAGE 4: Collect weight (optional)
        elif onboarding_state == "ONBOARD_WEIGHT":
            return self._handle_weight_input(user, message)
        
        # STAGE 5: Collect height (optional)
        elif onboarding_state == "ONBOARD_HEIGHT":
            return self._handle_height_input(user, message)
        
        # STAGE 6: Show summary and activation options
        elif onboarding_state == "ONBOARD_ACTIVATION":
            return self._handle_activation_choice(user, message)
        
        # STAGE 7: Reminder setup
        elif onboarding_state.startswith("ONBOARD_REMINDER"):
            return self._handle_reminder_setup(user, message)
        
        # STAGE 8: Quick activity log
        elif onboarding_state.startswith("ONBOARD_ACTIVITY"):
            return self._handle_quick_activity(user, message)
        
        # Fallback
        else:
            return self._send_welcome_message(user)
    
    def _send_welcome_message(self, user: str) -> Response:
        """Send initial welcome message"""
        resp = MessagingResponse()
        
        message = (
            "👋 Halo! Selamat datang di Babylog!\n\n"
            "Saya akan membantu Anda melacak tumbuh kembang si kecil - "
            "dari makan, tidur, hingga grafik pertumbuhan. "
            "Semua via WhatsApp, simple! 📱\n\n"
            "Untuk memulai, siapa nama bayi Anda? 👶\n\n"
            "💡 Tips: Ketik nama saja, contoh: \"Alya\" atau \"Rizki\"\n\n"
            "_(Ketik \"batal\" kapanpun untuk keluar)_"
        )
        
        resp.message(message)
        
        # Set onboarding state
        self.session_manager.update_session(
            user, 
            state="ONBOARD_NAME",
            data={"onboarding_started": datetime.now().isoformat()}
        )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_name_input(self, user: str, message: str) -> Response:
        """Handle baby name input"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        
        # Validate name
        name = InputValidator.sanitize_text_input(message, max_length=50)
        
        if len(name) < 2:
            resp.message(
                "❌ Nama terlalu pendek.\n\n"
                "Ketik nama bayi Anda (minimal 2 huruf):"
            )
            return Response(str(resp), media_type="application/xml")
        
        # Save name
        session["data"]["name"] = name
        
        # Move to gender
        reply = (
            f"🎉 Senang berkenalan dengan {name}!\n\n"
            f"{name} bayi perempuan atau laki-laki?\n\n"
            f"Ketik:\n"
            f"• \"perempuan\" atau \"p\"\n"
            f"• \"laki-laki\" atau \"l\""
        )
        
        resp.message(reply)
        
        self.session_manager.update_session(
            user, 
            state="ONBOARD_GENDER",
            data=session["data"]
        )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_gender_input(self, user: str, message: str) -> Response:
        """Handle gender input"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        
        msg_lower = message.lower().strip()
        
        # Parse gender
        if msg_lower in ["perempuan", "p", "pr", "girl", "female", "wanita", "cewe"]:
            gender = "perempuan"
            emoji = "👧"
        elif msg_lower in ["laki-laki", "l", "lk", "boy", "male", "pria", "cowo"]:
            gender = "laki-laki"
            emoji = "👦"
        else:
            resp.message(
                "❌ Tidak valid.\n\n"
                "Ketik \"perempuan\" atau \"laki-laki\":"
            )
            return Response(str(resp), media_type="application/xml")
        
        # Save gender
        session["data"]["gender"] = gender
        name = session["data"]["name"]
        
        # Move to DOB
        reply = (
            f"{emoji} {name} {gender}, noted!\n\n"
            f"Kapan {name} lahir? 📅\n\n"
            f"Ketik tanggal lahir: YYYY-MM-DD\n"
            f"Contoh: 2024-03-15\n\n"
            f"💡 Atau ketik \"today\" jika baru lahir hari ini!"
        )
        
        resp.message(reply)
        
        self.session_manager.update_session(
            user,
            state="ONBOARD_DOB",
            data=session["data"]
        )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_dob_input(self, user: str, message: str) -> Response:
        """Handle birth date input"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        
        # Handle "today" shortcut
        if message.lower().strip() == "today":
            dob = date.today().isoformat()
        else:
            # Validate date
            is_valid, error_msg = InputValidator.validate_date(message)
            if not is_valid:
                resp.message(f"❌ {error_msg}\n\nCoba lagi dengan format: YYYY-MM-DD")
                return Response(str(resp), media_type="application/xml")
            dob = message
        
        # Calculate age
        birth_date = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        age = relativedelta(today, birth_date)
        
        # Format age string
        if age.years > 0:
            age_str = f"{age.years} tahun {age.months} bulan"
        elif age.months > 0:
            age_str = f"{age.months} bulan"
        else:
            age_str = f"{age.days} hari"
        
        # Save DOB
        session["data"]["dob"] = dob
        session["data"]["age_str"] = age_str
        name = session["data"]["name"]
        
        # Move to weight (optional)
        reply = (
            f"✨ {name} lahir {birth_date.strftime('%d %B %Y')} - "
            f"berarti sekarang {age_str} ya!\n\n"
            f"Berapa berat {name} sekarang? (kg) ⚖️\n\n"
            f"Contoh: 7.5 atau 7500 (dalam gram)\n\n"
            f"💡 Tidak ingat? Ketik \"skip\" - bisa diisi nanti!"
        )
        
        resp.message(reply)
        
        self.session_manager.update_session(
            user,
            state="ONBOARD_WEIGHT",
            data=session["data"]
        )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_weight_input(self, user: str, message: str) -> Response:
        """Handle weight input (optional)"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        name = session["data"]["name"]
        
        # Allow skip
        if message.lower().strip() == "skip":
            session["data"]["weight_kg"] = None
            
            reply = (
                f"👍 No problem! Nanti bisa diisi dengan:\n"
                f"\"catat timbang\"\n\n"
                f"Tinggi {name} berapa? (cm) 📏\n\n"
                f"Contoh: 68 atau 68.5\n\n"
                f"💡 Atau ketik \"skip\" untuk lanjut"
            )
        else:
            # Validate weight
            try:
                weight = float(message.replace(',', '.'))
                # Convert grams to kg if needed
                weight_kg = weight / 1000 if weight > 100 else weight
                
                is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                if not is_valid:
                    resp.message(f"❌ {error_msg}\n\nCoba lagi:")
                    return Response(str(resp), media_type="application/xml")
                
                session["data"]["weight_kg"] = weight_kg
                
                reply = (
                    f"✅ Berat {name}: {weight_kg} kg\n\n"
                    f"Tinggi {name} berapa? (cm) 📏\n\n"
                    f"Contoh: 68 atau 68.5\n\n"
                    f"💡 Atau ketik \"skip\" untuk lanjut"
                )
            except ValueError:
                resp.message("❌ Masukkan angka yang valid. Contoh: 7.5")
                return Response(str(resp), media_type="application/xml")
        
        resp.message(reply)
        
        self.session_manager.update_session(
            user,
            state="ONBOARD_HEIGHT",
            data=session["data"]
        )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_height_input(self, user: str, message: str) -> Response:
        """Handle height input (optional) and save baby data"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        
        # Allow skip
        if message.lower().strip() == "skip":
            session["data"]["height_cm"] = None
        else:
            # Validate height
            is_valid, error_msg = InputValidator.validate_height_cm(message)
            if not is_valid:
                resp.message(f"❌ {error_msg}\n\nCoba lagi:")
                return Response(str(resp), media_type="application/xml")
            
            session["data"]["height_cm"] = float(message.replace(',', '.'))
        
        # SAVE BABY DATA TO DATABASE
        try:
            # Set defaults for skipped fields
            if session["data"].get("weight_kg") is None:
                session["data"]["weight_kg"] = 3.5  # Default newborn weight
            if session["data"].get("height_cm") is None:
                session["data"]["height_cm"] = 50.0  # Default newborn height
            
            save_child(user, session["data"])
            
            # Show completion summary
            reply = self._format_onboarding_summary(session["data"])
            
            resp.message(reply)
            
            # Move to activation
            self.session_manager.update_session(
                user,
                state="ONBOARD_ACTIVATION",
                data=session["data"]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save baby data: {e}")
            resp.message(
                "❌ Terjadi kesalahan saat menyimpan data.\n\n"
                "Ketik 'start' untuk coba lagi."
            )
        
        return Response(str(resp), media_type="application/xml")
    
    def _format_onboarding_summary(self, data: dict) -> str:
        """Format completion summary with activation options"""
        name = data["name"]
        gender_emoji = "👧" if data["gender"] == "perempuan" else "👦"
        age_str = data.get("age_str", "")
        weight = data.get("weight_kg", "Belum diisi")
        height = data.get("height_cm", "Belum diisi")
        
        if weight != "Belum diisi":
            weight = f"{weight} kg"
        if height != "Belum diisi":
            height = f"{height} cm"
        
        return (
            f"🎉 SELESAI! Data {name} sudah tersimpan!\n\n"
            f"📊 Ringkasan {name}:\n"
            f"{gender_emoji} Nama: {name}\n"
            f"🎂 Usia: {age_str}\n"
            f"⚖️ Berat: {weight}\n"
            f"📏 Tinggi: {height}\n\n"
            f"Ayo mulai tracking! Mau yang mana dulu?\n\n"
            f"1️⃣ Set pengingat minum susu 🍼\n"
            f"   (Saya akan ingatkan Anda setiap X jam)\n\n"
            f"2️⃣ Catat aktivitas {name} sekarang 📝\n"
            f"   (Makan, tidur, atau minum?)\n\n"
            f"Ketik \"1\" atau \"2\" untuk lanjut\n"
            f"Atau ketik \"panduan\" untuk lihat semua fitur"
        )
    
    def _handle_activation_choice(self, user: str, message: str) -> Response:
        """Handle activation path choice"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        
        msg = message.strip()
        
        if msg == "1":
            # Start reminder setup
            name = session["data"]["name"]
            reply = (
                f"⏰ PENGINGAT MINUM SUSU\n\n"
                f"Saya akan kirim pesan otomatis untuk ingatkan "
                f"Anda kapan waktunya {name} minum.\n\n"
                f"Setiap berapa jam {name} minum susu?\n\n"
                f"Ketik angka 2-4 jam:\n"
                f"• \"2\" = setiap 2 jam\n"
                f"• \"3\" = setiap 3 jam\n"
                f"• \"4\" = setiap 4 jam\n\n"
                f"💡 Paling umum: 3 jam untuk bayi"
            )
            
            resp.message(reply)
            
            self.session_manager.update_session(
                user,
                state="ONBOARD_REMINDER_INTERVAL",
                data=session["data"]
            )
            
        elif msg == "2":
            # Start quick activity log
            name = session["data"]["name"]
            reply = (
                f"📝 CATAT AKTIVITAS {name.upper()}\n\n"
                f"Mau catat apa sekarang?\n\n"
                f"1️⃣ {name} baru minum susu 🍼\n"
                f"2️⃣ {name} baru makan MPASI 🍽️\n"
                f"3️⃣ {name} mulai tidur 😴\n\n"
                f"Ketik \"1\", \"2\", atau \"3\""
            )
            
            resp.message(reply)
            
            self.session_manager.update_session(
                user,
                state="ONBOARD_ACTIVITY_TYPE",
                data=session["data"]
            )
            
        elif msg.lower() == "panduan":
            # Show full guide
            from constants import PANDUAN_MESSAGE
            resp.message(PANDUAN_MESSAGE)
            
            # Mark onboarding as complete
            self.session_manager.update_session(user, state=None, data={})
            
        else:
            resp.message(
                "❌ Tidak valid.\n\n"
                "Ketik \"1\" untuk pengingat\n"
                "Ketik \"2\" untuk catat aktivitas\n"
                "Atau ketik \"panduan\" untuk lihat semua fitur"
            )
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_reminder_setup(self, user: str, message: str) -> Response:
        """Quick reminder setup during onboarding"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        state = session["state"]
        
        # Handle interval input
        if state == "ONBOARD_REMINDER_INTERVAL":
            try:
                interval = int(message)
                if interval not in [2, 3, 4]:
                    resp.message("❌ Pilih 2, 3, atau 4 jam:")
                    return Response(str(resp), media_type="application/xml")
                
                session["data"]["reminder_interval"] = interval
                
                reply = (
                    f"👍 Oke! Setiap {interval} jam.\n\n"
                    f"Jam berapa mulai pengingat?\n"
                    f"(Pengingat pertama besok)\n\n"
                    f"Contoh: 07:00 (jam 7 pagi)\n\n"
                    f"💡 Atau ketik \"now\" untuk mulai sekarang"
                )
                
                resp.message(reply)
                
                self.session_manager.update_session(
                    user,
                    state="ONBOARD_REMINDER_TIME",
                    data=session["data"]
                )
                
            except ValueError:
                resp.message("❌ Masukkan angka: 2, 3, atau 4")
        
        # Handle start time input
        elif state == "ONBOARD_REMINDER_TIME":
            from database.operations import save_reminder
            from datetime import datetime, timedelta
            
            if message.lower() == "now":
                start_time = datetime.now().strftime("%H:%M")
            else:
                is_valid, error_msg = InputValidator.validate_time(message)
                if not is_valid:
                    resp.message(f"❌ {error_msg}\n\nContoh: 07:00")
                    return Response(str(resp), media_type="application/xml")
                start_time = message
            
            # Save reminder
            try:
                interval = session["data"]["reminder_interval"]
                name = session["data"]["name"]
                
                reminder_data = {
                    "reminder_name": f"Minum Susu {name}",
                    "interval_hours": interval,
                    "start_time": start_time,
                    "end_time": "22:00"  # Default end time
                }
                
                save_reminder(user, reminder_data)
                
                # Success message
                reply = (
                    f"✅ PENGINGAT SIAP!\n\n"
                    f"🔔 Saya akan ingatkan Anda setiap {interval} jam,\n"
                    f"   mulai besok jam {start_time}.\n\n"
                    f"📱 Saat pengingat muncul, Anda bisa:\n"
                    f"   • Ketik \"done 120\" (minum 120ml)\n"
                    f"   • Ketik \"snooze 30\" (tunda 30 menit)\n"
                    f"   • Ketik \"skip\" (lewati)\n\n"
                    f"🎉 Selamat! Anda sudah siap pakai Babylog!\n\n"
                    f"📚 3 Perintah Paling Penting:\n"
                    f"   • \"catat susu\" - Log minum manual\n"
                    f"   • \"catat tidur\" - Track jam tidur\n"
                    f"   • \"ringkasan hari ini\" - Lihat summary\n\n"
                    f"Ketik \"help\" kapanpun untuk bantuan lengkap.\n\n"
                    f"Selamat mencoba! 💙"
                )
                
                resp.message(reply)
                
                # Mark onboarding complete
                self.session_manager.update_session(user, state=None, data={})
                
            except Exception as e:
                self.logger.error(f"Failed to save reminder: {e}")
                resp.message(
                    "❌ Gagal menyimpan pengingat.\n\n"
                    "Tapi tidak apa! Anda tetap bisa buat pengingat "
                    "kapanpun dengan: \"set reminder susu\"\n\n"
                    "Ketik \"help\" untuk mulai."
                )
                self.session_manager.update_session(user, state=None, data={})
        
        return Response(str(resp), media_type="application/xml")
    
    def _handle_quick_activity(self, user: str, message: str) -> Response:
        """Quick activity logging during onboarding"""
        resp = MessagingResponse()
        session = self.session_manager.get_session(user)
        state = session["state"]
        name = session["data"]["name"]
        
        # Handle activity type selection
        if state == "ONBOARD_ACTIVITY_TYPE":
            if message == "1":
                # Milk
                reply = (
                    f"🍼 CATAT MINUM SUSU\n\n"
                    f"Berapa ml {name} minum?\n\n"
                    f"Contoh: 120 atau 150\n\n"
                    f"💡 Estimasi aja juga gpp!"
                )
                
                resp.message(reply)
                
                self.session_manager.update_session(
                    user,
                    state="ONBOARD_ACTIVITY_MILK_VOL",
                    data=session["data"]
                )
                
            elif message == "2":
                # MPASI
                reply = (
                    f"🍽️ CATAT MAKAN MPASI\n\n"
                    f"Berapa ml/sendok {name} makan?\n\n"
                    f"Contoh: 100 (untuk 100ml)\n\n"
                    f"💡 Atau ketik angka estimasi"
                )
                
                resp.message(reply)
                
                self.session_manager.update_session(
                    user,
                    state="ONBOARD_ACTIVITY_MPASI_VOL",
                    data=session["data"]
                )
                
            elif message == "3":
                # Sleep
                from sleep_tracking import start_sleep_record
                
                try:
                    today = date.today().isoformat()
                    now_time = datetime.now().strftime("%H:%M")
                    
                    sleep_id, msg = start_sleep_record(user, today, now_time)
                    
                    reply = (
                        f"😴 CATAT TIDUR\n\n"
                        f"✅ Mulai mencatat tidur {name} pada {now_time}\n\n"
                        f"Nanti ketika {name} bangun, ketik:\n"
                        f"\"selesai tidur [HH:MM]\"\n\n"
                        f"Contoh: selesai tidur 06:30\n\n"
                        f"🎉 Anda sudah siap pakai Babylog!\n\n"
                        f"Ketik \"help\" untuk bantuan lengkap."
                    )
                    
                    resp.message(reply)
                    
                    # Mark onboarding complete
                    self.session_manager.update_session(user, state=None, data={})
                    
                except Exception as e:
                    self.logger.error(f"Failed to start sleep: {e}")
                    resp.message("❌ Gagal mencatat tidur. Ketik \"help\" untuk mulai.")
                    self.session_manager.update_session(user, state=None, data={})
            
            else:
                resp.message("❌ Pilih 1, 2, atau 3")
        
        # Handle milk volume input
        elif state == "ONBOARD_ACTIVITY_MILK_VOL":
            from database.operations import save_milk_intake
            
            try:
                volume = float(message)
                
                milk_data = {
                    "date": date.today().isoformat(),
                    "time": datetime.now().strftime("%H:%M"),
                    "volume_ml": volume,
                    "milk_type": "mixed",
                    "note": "Onboarding entry"
                }
                
                save_milk_intake(user, milk_data)
                
                reply = (
                    f"✅ TERCATAT!\n\n"
                    f"🍼 {name} minum {volume}ml pada "
                    f"{datetime.now().strftime('%H:%M')}\n\n"
                    f"Mau set pengingat otomatis untuk minum berikutnya?\n\n"
                    f"Ketik \"ya\" atau \"tidak\""
                )
                
                resp.message(reply)
                
                self.session_manager.update_session(
                    user,
                    state="ONBOARD_ACTIVITY_OFFER_REMINDER",
                    data=session["data"]
                )
                
            except ValueError:
                resp.message("❌ Masukkan angka. Contoh: 120")
        
        # Handle MPASI volume input
        elif state == "ONBOARD_ACTIVITY_MPASI_VOL":
            from database.operations import save_mpasi
            
            try:
                volume = float(message)
                
                mpasi_data = {
                    "date": date.today().isoformat(),
                    "time": datetime.now().strftime("%H:%M"),
                    "volume_ml": volume,
                    "food_detail": "MPASI (onboarding)",
                    "food_grams": ""
                }
                
                save_mpasi(user, mpasi_data)
                
                reply = (
                    f"✅ TERCATAT!\n\n"
                    f"🍽️ {name} makan {volume}ml MPASI pada "
                    f"{datetime.now().strftime('%H:%M')}\n\n"
                    f"🎉 Anda sudah siap pakai Babylog!\n\n"
                    f"📚 Top Commands:\n"
                    f"   • \"catat mpasi\" - Log makan lagi\n"
                    f"   • \"catat susu\" - Log minum\n"
                    f"   • \"ringkasan hari ini\" - Lihat summary\n\n"
                    f"Ketik \"help\" untuk bantuan lengkap."
                )
                
                resp.message(reply)
                
                # Mark onboarding complete
                self.session_manager.update_session(user, state=None, data={})
                
            except ValueError:
                resp.message("❌ Masukkan angka. Contoh: 100")
        
        # Handle reminder offer
        elif state == "ONBOARD_ACTIVITY_OFFER_REMINDER":
            if message.lower() in ["ya", "yes", "y"]:
                reply = (
                    f"⏰ SETUP PENGINGAT\n\n"
                    f"Setiap berapa jam {name} minum?\n\n"
                    f"Ketik: 2, 3, atau 4"
                )
                
                resp.message(reply)
                
                self.session_manager.update_session(
                    user,
                    state="ONBOARD_REMINDER_INTERVAL",
                    data=session["data"]
                )
            else:
                reply = (
                    f"👍 Oke! Anda bisa set pengingat kapanpun dengan:\n"
                    f"\"set reminder susu\"\n\n"
                    f"🎉 Selamat! Anda sudah siap pakai Babylog!\n\n"
                    f"Ketik \"help\" untuk bantuan lengkap."
                )
                
                resp.message(reply)
                
                # Mark onboarding complete
                self.session_manager.update_session(user, state=None, data={})
        
        return Response(str(resp), media_type="application/xml")
