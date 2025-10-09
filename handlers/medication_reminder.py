# handlers/medication_reminder.py
from datetime import datetime
from fastapi import BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    save_medication_reminder, get_medication_reminders,
    log_medication_intake
)
from validators import InputValidator
from error_handler import ValidationError

class MedicationHandler:
    """Handle medication reminder operations"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
    
    def handle_medication_commands(self, user: str, message: str, background_tasks: BackgroundTasks) -> Response:
        """Route medication commands"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        # Check for specific commands
        if message.lower() in ["set reminder obat", "atur pengingat obat"]:
            return self.handle_medication_setup(user, message)
        
        elif message.lower() in ["lihat obat", "show medication"]:
            return self.handle_show_medications(user)
        
        elif message.lower().startswith("taken "):
            return self.handle_medication_taken(user, message)
        
        elif session["state"] and session["state"].startswith("MED_"):
            return self.handle_medication_setup(user, message)
        
        else:
            resp.message("❓ Perintah obat tidak dikenali. Ketik 'help' untuk bantuan.")
            return Response(str(resp), media_type="application/xml")
    
    def handle_medication_setup(self, user: str, message: str) -> Response:
        """Handle medication setup flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() in ["set reminder obat", "atur pengingat obat"]:
                session["state"] = "MED_NAME"
                session["data"] = {}
                reply = (
                    "🏥 **Setup Pengingat Obat**\n\n"
                    "Nama obat?\n\n"
                    "**Contoh:**\n"
                    "• Paracetamol\n"
                    "• Amoxicillin\n"
                    "• Vitamin D"
                )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_NAME":
                session["data"]["medication_name"] = InputValidator.sanitize_text_input(message, 100)
                session["state"] = "MED_TYPE"
                reply = (
                    "Jenis obat?\n\n"
                    "Pilih:\n"
                    "• `obat` - Obat resep\n"
                    "• `vitamin` - Vitamin/suplemen\n"
                    "• `herbal` - Suplemen herbal"
                )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_TYPE":
                med_type_map = {
                    'obat': 'medicine',
                    'vitamin': 'vitamin',
                    'herbal': 'supplement'
                }
                med_type = med_type_map.get(message.lower())
                
                if not med_type:
                    reply = "❌ Pilih: obat, vitamin, atau herbal"
                else:
                    session["data"]["medication_type"] = med_type
                    session["state"] = "MED_DOSAGE"
                    reply = (
                        "Dosis per konsumsi?\n\n"
                        "**Contoh:**\n"
                        "• 1 tablet\n"
                        "• 5 ml\n"
                        "• 2 kapsul"
                    )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_DOSAGE":
                session["data"]["dosage"] = InputValidator.sanitize_text_input(message, 50)
                session["state"] = "MED_FREQUENCY"
                reply = (
                    "Frekuensi konsumsi?\n\n"
                    "Pilih:\n"
                    "• `daily` - Setiap hari\n"
                    "• `interval` - Setiap X jam\n"
                    "• `times` - Waktu spesifik (misal: 08:00, 14:00)"
                )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_FREQUENCY":
                freq = message.lower()
                if freq == "daily":
                    session["data"]["frequency"] = "daily"
                    session["state"] = "MED_TIMES"
                    reply = "Jam berapa saja? (pisahkan dengan koma)\n\nContoh: 08:00, 14:00, 20:00"
                elif freq == "interval":
                    session["data"]["frequency"] = "interval"
                    session["state"] = "MED_INTERVAL"
                    reply = "Setiap berapa jam?\n\nContoh: 8 (untuk setiap 8 jam)"
                elif freq == "times":
                    session["data"]["frequency"] = "specific"
                    session["state"] = "MED_TIMES"
                    reply = "Jam berapa saja? (pisahkan dengan koma)\n\nContoh: 08:00, 14:00, 20:00"
                else:
                    reply = "❌ Pilih: daily, interval, atau times"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_INTERVAL":
                try:
                    interval = int(message)
                    if interval < 1 or interval > 24:
                        reply = "❌ Interval harus antara 1-24 jam"
                    else:
                        session["data"]["interval_hours"] = interval
                        session["state"] = "MED_START_DATE"
                        reply = "Tanggal mulai? (YYYY-MM-DD atau 'today')"
                except ValueError:
                    reply = "❌ Masukkan angka yang valid"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_TIMES":
                # Validate times format
                times = [t.strip() for t in message.split(',')]
                valid_times = []
                for t in times:
                    is_valid, error = InputValidator.validate_time(t)
                    if is_valid:
                        valid_times.append(t)
                
                if not valid_times:
                    reply = "❌ Format waktu tidak valid. Gunakan HH:MM"
                else:
                    session["data"]["specific_times"] = ','.join(valid_times)
                    session["state"] = "MED_START_DATE"
                    reply = "Tanggal mulai? (YYYY-MM-DD atau 'today')"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_START_DATE":
                if message.lower() == 'today':
                    start_date = datetime.now().strftime("%Y-%m-%d")
                else:
                    is_valid, error = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error}"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    start_date = message
                
                session["data"]["start_date"] = start_date
                session["state"] = "MED_DURATION"
                reply = "Berapa hari durasi pengobatan? (atau ketik 'ongoing' jika tidak terbatas)"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_DURATION":
                if message.lower() == 'ongoing':
                    session["data"]["end_date"] = None
                else:
                    try:
                        days = int(message)
                        from datetime import timedelta
                        start_date = datetime.strptime(session["data"]["start_date"], "%Y-%m-%d")
                        end_date = (start_date + timedelta(days=days)).strftime("%Y-%m-%d")
                        session["data"]["end_date"] = end_date
                    except ValueError:
                        reply = "❌ Masukkan angka atau ketik 'ongoing'"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                
                session["state"] = "MED_CONFIRM"
                reply = self._format_medication_summary(session["data"])
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            elif session["state"] == "MED_CONFIRM":
                if message.lower() == "ya":
                    try:
                        save_medication_reminder(user, session["data"])
                        reply = (
                            f"✅ Pengingat obat '{session['data']['medication_name']}' berhasil dibuat!\n\n"
                            f"💡 Saat pengingat muncul:\n"
                            f"• `taken {session['data']['medication_name']}` - Sudah minum\n"
                            f"• `skip medication` - Lewati"
                        )
                        session["state"] = None
                        session["data"] = {}
                    except Exception as e:
                        self.logger.error(f"Error saving medication: {e}")
                        reply = "❌ Terjadi kesalahan. Silakan coba lagi."
                elif message.lower() == "tidak":
                    session["state"] = "MED_NAME"
                    reply = "Mari ulangi. Nama obat?"
                else:
                    reply = "Ketik 'ya' untuk simpan atau 'tidak' untuk ulang"
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam setup obat."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            self.logger.error(f"Error in medication setup: {e}")
            self.session_manager.clear_session(user)
            resp.message("❌ Terjadi kesalahan. Sesi direset.")
            return Response(str(resp), media_type="application/xml")
    
    def handle_show_medications(self, user: str) -> Response:
        """Show active medications"""
        resp = MessagingResponse()
        
        try:
            medications = get_medication_reminders(user)
            
            if not medications:
                reply = (
                    "📋 **Belum ada pengingat obat**\n\n"
                    "Buat pengingat baru:\n"
                    "`set reminder obat`"
                )
            else:
                reply = "💊 **Obat & Vitamin Aktif:**\n\n"
                for i, med in enumerate(medications, 1):
                    name = med[0] if len(med) > 0 else 'N/A'
                    med_type = med[1] if len(med) > 1 else 'N/A'
                    dosage = med[2] if len(med) > 2 else 'N/A'
                    frequency = med[3] if len(med) > 3 else 'N/A'
                    
                    reply += f"{i}. **{name}** ({med_type})\n"
                    reply += f"   Dosis: {dosage}\n"
                    reply += f"   Frekuensi: {frequency}\n\n"
                
                reply += "\n💡 Respons cepat:\n• `taken [nama obat]`"
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            self.logger.error(f"Error showing medications: {e}")
            resp.message("❌ Gagal mengambil daftar obat.")
            return Response(str(resp), media_type="application/xml")
    
    def handle_medication_taken(self, user: str, message: str) -> Response:
        """Handle medication taken response"""
        resp = MessagingResponse()
        
        try:
            parts = message.split(" ", 1)
            if len(parts) < 2:
                reply = "Format: `taken [nama obat]`\n\nContoh: taken Paracetamol"
            else:
                medication_name = parts[1]
                now = datetime.now()
                
                log_data = {
                    'medication_name': medication_name,
                    'date': now.strftime("%Y-%m-%d"),
                    'time': now.strftime("%H:%M"),
                    'taken': True
                }
                
                log_medication_intake(user, log_data)
                
                reply = f"✅ Dicatat: {medication_name} sudah diminum pada {now.strftime('%H:%M')}"
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            self.logger.error(f"Error logging medication: {e}")
            resp.message("❌ Gagal mencatat obat.")
            return Response(str(resp), media_type="application/xml")
    
    def _format_medication_summary(self, data: dict) -> str:
        """Format medication summary for confirmation"""
        summary = "✅ **Konfirmasi Pengingat Obat:**\n\n"
        summary += f"• Nama: {data['medication_name']}\n"
        summary += f"• Jenis: {data['medication_type']}\n"
        summary += f"• Dosis: {data['dosage']}\n"
        summary += f"• Frekuensi: {data['frequency']}\n"
        
        if data.get('specific_times'):
            summary += f"• Waktu: {data['specific_times']}\n"
        if data.get('interval_hours'):
            summary += f"• Interval: Setiap {data['interval_hours']} jam\n"
        
        summary += f"• Mulai: {data['start_date']}\n"
        
        if data.get('end_date'):
            summary += f"• Selesai: {data['end_date']}\n"
        else:
            summary += f"• Durasi: Tidak terbatas\n"
        
        summary += "\nApakah sudah benar? (ya/tidak)"
        
        return summary
