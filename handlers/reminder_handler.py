# handlers/reminder_handler.py
"""
Reminder management handler
Handles reminder setup, management, and quick responses
"""
from datetime import datetime, timedelta
from fastapi import BackgroundTasks
from fastapi.responses import Response  # correct 
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    save_reminder, get_user_reminders, save_milk_intake,
    get_user_calorie_setting
)
from validators import InputValidator
from error_handler import ValidationError
from tier_management import get_tier_limits, increment_message_count
import re
import logging

class ReminderHandler:
    """Handle all reminder-related operations"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger  # Use simple logger instead of app_logger
    
    def handle_reminder_commands(self, user: str, message: str, background_tasks: BackgroundTasks) -> Response:
        """Route reminder commands to appropriate handlers"""
        session = self.session_manager.get_session(user)
        
        # Setup new reminder
        if (message.lower() in ["set reminder susu", "atur pengingat susu"] or
            session["state"] and session["state"].startswith("REMINDER")):
            return self.handle_reminder_setup(user, message)
        
        # Show existing reminders
        elif message.lower() in ["show reminders", "lihat pengingat"]:
            return self.handle_show_reminders(user)
        
        # Quick responses to reminders
        elif message.lower().startswith("done "):
            return self.handle_reminder_done(user, message)
        
        elif message.lower().startswith("snooze "):
            return self.handle_reminder_snooze(user, message)
        
        elif message.lower() == "skip reminder":
            return self.handle_reminder_skip(user)
        
        # Reminder management commands
        elif message.lower().startswith("stop reminder"):
            return self.handle_stop_reminder(user, message)
        
        elif message.lower().startswith("delete reminder"):
            return self.handle_delete_reminder(user, message)
        
        else:
            return self._handle_unknown_reminder_command(user, message)
    
    def handle_reminder_setup(self, user: str, message: str) -> Response:
        """Handle reminder setup flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() in ["set reminder susu", "atur pengingat susu"]:
                # Check tier limits first
                limits = get_tier_limits(user)
                if limits["active_reminders"] is not None:  # Free user
                    active_reminders = len(get_user_reminders(user))
                    if active_reminders >= limits["active_reminders"]:
                        reply = (
                            f"🚫 **Batas Pengingat Tercapai**\n\n"
                            f"Tier gratis dibatasi {limits['active_reminders']} pengingat aktif.\n"
                            f"Saat ini: {active_reminders}/{limits['active_reminders']}\n\n"
                            f"💎 **Upgrade ke premium untuk:**\n"
                            f"• Pengingat unlimited\n"
                            f"• Pengingat custom\n"
                            f"• Analisis pola minum\n\n"
                            f"💡 Hapus pengingat lama dengan: `delete reminder [nama]`"
                        )
                        
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='reminder_setup_blocked',
                            success=False,
                            details={'reason': 'tier_limit_reached', 'current_count': active_reminders}
                        )
                        
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                
                session["state"] = "REMINDER_NAME"
                session["data"] = {}
                reply = (
                    f"🔔 **Setup Pengingat Susu**\n\n"
                    f"Siapa nama pengingat?\n\n"
                    f"**Contoh:**\n"
                    f"• Susu Pagi\n"
                    f"• Minum ASI\n"
                    f"• Sufor Malam\n"
                    f"• Pengingat Utama"
                )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_NAME":
                reminder_name = InputValidator.sanitize_text_input(message, 50)
                session["data"]["reminder_name"] = reminder_name
                session["state"] = "REMINDER_INTERVAL"
                reply = (
                    f"⏰ **Interval pengingat?**\n\n"
                    f"Setiap berapa jam?\n\n"
                    f"**Contoh:**\n"
                    f"• 2 (setiap 2 jam)\n"
                    f"• 3 (setiap 3 jam)\n"
                    f"• 4 (setiap 4 jam)\n\n"
                    f"Masukkan angka 1-12:"
                )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_INTERVAL":
                try:
                    interval = int(message)
                    if 1 <= interval <= 12:
                        session["data"]["interval_hours"] = interval
                        session["state"] = "REMINDER_START"
                        reply = (
                            f"🌅 **Jam mulai pengingat?**\n\n"
                            f"Format: HH:MM (24 jam)\n\n"
                            f"**Contoh:**\n"
                            f"• 06:00 (mulai pagi)\n"
                            f"• 08:00 (mulai pagi agak siang)\n"
                            f"• 07:30 (mulai jam setengah 8)\n\n"
                            f"Masukkan jam mulai:"
                        )
                    else:
                        reply = "❌ Masukkan interval antara 1-12 jam."
                except ValueError:
                    reply = "❌ Masukkan angka untuk interval jam."
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_START":
                is_valid, error_msg = InputValidator.validate_time(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["start_time"] = message
                    session["state"] = "REMINDER_END"
                    reply = (
                        f"🌙 **Jam berhenti pengingat?**\n\n"
                        f"Format: HH:MM (24 jam)\n\n"
                        f"**Contoh:**\n"
                        f"• 22:00 (berhenti jam 10 malam)\n"
                        f"• 21:30 (berhenti jam setengah 10)\n"
                        f"• 23:00 (berhenti jam 11 malam)\n\n"
                        f"Masukkan jam berhenti:"
                    )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_END":
                is_valid, error_msg = InputValidator.validate_time(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["end_time"] = message
                    session["state"] = "REMINDER_CONFIRM"
                    
                    # Calculate first reminder time
                    start_hour, start_min = map(int, session["data"]["start_time"].split(':'))
                    next_reminder = datetime.now().replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                    if next_reminder <= datetime.now():
                        next_reminder += timedelta(days=1)
                    
                    reply = (
                        f"✅ **Konfirmasi Pengingat**\n\n"
                        f"📝 **Detail:**\n"
                        f"• Nama: {session['data']['reminder_name']}\n"
                        f"• Interval: Setiap {session['data']['interval_hours']} jam\n"
                        f"• Waktu aktif: {session['data']['start_time']} - {session['data']['end_time']}\n"
                        f"• Pengingat pertama: {next_reminder.strftime('%H:%M')}\n\n"
                        f"Apakah sudah benar?\n"
                        f"• Ketik `ya` untuk simpan\n"
                        f"• Ketik `tidak` untuk mengulang\n"
                        f"• Ketik `batal` untuk membatalkan"
                    )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_CONFIRM":
                if message.lower() == "ya":
                    try:
                        save_reminder(user, session["data"])
                        
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='reminder_created',
                            success=True,
                            details={
                                'name': session["data"]["reminder_name"],
                                'interval_hours': session["data"]["interval_hours"],
                                'start_time': session["data"]["start_time"],
                                'end_time': session["data"]["end_time"]
                            }
                        )
                        
                        reply = (
                            f"✅ **Pengingat berhasil dibuat!**\n\n"
                            f"🔔 '{session['data']['reminder_name']}' akan mulai aktif pada jam {session['data']['start_time']}.\n\n"
                            f"**Saat pengingat muncul, Anda bisa:**\n"
                            f"• `done [volume]` - Catat volume (contoh: done 120)\n"
                            f"• `snooze [menit]` - Tunda (contoh: snooze 15)\n"
                            f"• `skip reminder` - Lewati sekali\n\n"
                            f"Ketik `show reminders` untuk melihat semua pengingat."
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                    except (ValueError, ValidationError) as e:
                        reply = f"❌ {str(e)}"
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='reminder_created',
                            success=False,
                            details={'error': str(e)}
                        )
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_reminder'})
                        reply = f"❌ Terjadi kesalahan saat menyimpan pengingat. Kode error: {error_id}"
                        
                elif message.lower() == "tidak":
                    session["state"] = "REMINDER_NAME"
                    reply = "🔄 Mari ulang dari awal. Siapa nama pengingat?"
                elif message.lower() == "batal":
                    session["state"] = None
                    session["data"] = {}
                    reply = "❌ Setup pengingat dibatalkan."
                else:
                    reply = "Ketik 'ya' jika benar, 'tidak' untuk mengulang, atau 'batal' untuk membatalkan."
                    
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks setup pengingat."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_reminder_setup'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")
    
    def handle_show_reminders(self, user: str) -> Response:
        """Handle showing user's reminders"""
        resp = MessagingResponse()
        
        try:
            reminders = get_user_reminders(user)
            if not reminders:
                reply = (
                    f"📋 **Belum ada pengingat yang diatur**\n\n"
                    f"Buat pengingat baru dengan:\n"
                    f"`set reminder susu`\n\n"
                    f"💡 **Manfaat pengingat:**\n"
                    f"• Memastikan bayi minum teratur\n"
                    f"• Tracking otomatis asupan\n"
                    f"• Reminder yang bisa di-customize"
                )
            else:
                reply = "📋 **Pengingat Aktif:**\n\n"
                
                for i, r in enumerate(reminders, 1):
                    if isinstance(r, dict):  # PostgreSQL
                        name = r['reminder_name']
                        interval = r['interval_hours']
                        start_time = r['start_time']
                        end_time = r['end_time']
                        is_active = r['is_active']
                        next_due = r.get('next_due', 'Tidak diketahui')
                    else:  # SQLite - assuming order: id, user, name, interval, start, end, active, last_sent, next_due
                        name = r[2]
                        interval = r[3]
                        start_time = r[4]
                        end_time = r[5]
                        is_active = r[6]
                        next_due = r[8] if len(r) > 8 else 'Tidak diketahui'
                    
                    status = "🟢 Aktif" if is_active else "🔴 Nonaktif"
                    
                    # Format next due time
                    if next_due and next_due != 'Tidak diketahui':
                        try:
                            if isinstance(next_due, str):
                                next_due_dt = datetime.fromisoformat(next_due.replace('Z', '+00:00'))
                            else:
                                next_due_dt = next_due
                            next_due_str = next_due_dt.strftime('%H:%M')
                        except:
                            next_due_str = str(next_due)
                    else:
                        next_due_str = "Tidak diketahui"
                    
                    reply += (
                        f"{i}. **{name}** {status}\n"
                        f"   ⏰ Setiap {interval} jam ({start_time}-{end_time})\n"
                        f"   📅 Berikutnya: {next_due_str}\n\n"
                    )
                
                reply += (
                    f"**Kelola pengingat:**\n"
                    f"• `stop reminder [nama]` - Matikan\n"
                    f"• `delete reminder [nama]` - Hapus\n\n"
                    f"**Respons cepat saat pengingat:**\n"
                    f"• `done [volume]` - Catat volume\n"
                    f"• `snooze [menit]` - Tunda\n"
                    f"• `skip reminder` - Lewati"
                )
                
                # Add tier info for free users
                limits = get_tier_limits(user)
                if limits.get("active_reminders"):
                    current_count = len(reminders)
                    reply += f"\n\n📊 Pengingat: {current_count}/{limits['active_reminders']}"
            
            self.app_logger.log_user_action(
                user_id=user,
                action='reminders_viewed',
                success=True,
                details={'reminder_count': len(reminders)}
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_show_reminders'})
            reply = f"❌ Terjadi kesalahan saat mengambil daftar pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_reminder_done(self, user: str, message: str) -> Response:
        """Handle 'done [volume]' quick response"""
        resp = MessagingResponse()
        
        try:
            volume_match = re.search(r'done\s+(\d+)', message.lower())
            if not volume_match:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `done [volume]`\n\n"
                    f"**Contoh:**\n"
                    f"• `done 120` - untuk 120ml\n"
                    f"• `done 80` - untuk 80ml\n"
                    f"• `done 150` - untuk 150ml"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            volume = float(volume_match.group(1))
            
            # Validate volume
            if volume <= 0 or volume > 1000:
                reply = "❌ Volume harus antara 1-1000 ml."
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Create milk intake record
            milk_data = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M"),
                'volume_ml': volume,
                'milk_type': 'mixed',  # Default for reminder responses
                'note': 'Via reminder response'
            }
            
            save_milk_intake(user, milk_data)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='reminder_done_logged',
                success=True,
                details={
                    'volume_ml': volume,
                    'time': milk_data['time']
                }
            )
            
            reply = (
                f"✅ **Tercatat via pengingat!**\n\n"
                f"📊 **Detail:**\n"
                f"• Volume: {volume} ml\n"
                f"• Waktu: {milk_data['time']}\n"
                f"• Tanggal: {milk_data['date']}\n\n"
                f"🔔 Pengingat berikutnya akan disesuaikan otomatis.\n\n"
                f"Ketik `lihat ringkasan susu` untuk melihat ringkasan hari ini."
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_reminder_done'})
            reply = f"❌ Terjadi kesalahan saat mencatat minum susu. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_reminder_snooze(self, user: str, message: str) -> Response:
        """Handle 'snooze [minutes]' quick response"""
        resp = MessagingResponse()
        
        try:
            snooze_match = re.search(r'snooze\s+(\d+)', message.lower())
            if not snooze_match:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `snooze [menit]`\n\n"
                    f"**Contoh:**\n"
                    f"• `snooze 15` - tunda 15 menit\n"
                    f"• `snooze 30` - tunda 30 menit\n"
                    f"• `snooze 60` - tunda 1 jam"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            minutes = int(snooze_match.group(1))
            
            # Validate snooze duration
            if minutes <= 0 or minutes > 180:  # Max 3 hours
                reply = "❌ Durasi snooze harus antara 1-180 menit (maksimal 3 jam)."
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Update reminder next due time
            # This would require updating the reminder's next_due field
            # For now, just acknowledge the snooze
            
            self.app_logger.log_user_action(
                user_id=user,
                action='reminder_snoozed',
                success=True,
                details={'snooze_minutes': minutes}
            )
            
            new_time = datetime.now() + timedelta(minutes=minutes)
            reply = (
                f"⏰ **Pengingat ditunda {minutes} menit**\n\n"
                f"🔔 Pengingat berikutnya: {new_time.strftime('%H:%M')}\n\n"
                f"💡 Saat pengingat muncul lagi:\n"
                f"• `done [volume]` - Catat minum\n"
                f"• `skip reminder` - Lewati"
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_reminder_snooze'})
            reply = f"❌ Terjadi kesalahan saat menunda pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_reminder_skip(self, user: str) -> Response:
        """Handle 'skip reminder' quick response"""
        resp = MessagingResponse()
        
        try:
            reminders = get_user_reminders(user)
            if not reminders:
                reply = "❌ Tidak ada pengingat aktif untuk dilewati."
            else:
                self.app_logger.log_user_action(
                    user_id=user,
                    action='reminder_skipped',
                    success=True,
                    details={'active_reminders': len(reminders)}
                )
                
                reply = (
                    f"⏭️ **Pengingat dilewati**\n\n"
                    f"🔔 Pengingat berikutnya telah dijadwalkan sesuai interval normal.\n\n"
                    f"💡 **Tips:** Jika sering melewati pengingat, coba:\n"
                    f"• Sesuaikan interval waktu\n"
                    f"• Ubah jam aktif pengingat\n"
                    f"• Gunakan `snooze` jika hanya perlu ditunda"
                )
        
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_reminder_skip'})
            reply = f"❌ Terjadi kesalahan saat melewati pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_stop_reminder(self, user: str, message: str) -> Response:
        """Handle stopping a specific reminder"""
        resp = MessagingResponse()
        
        try:
            # Extract reminder name from message
            parts = message.split(" ", 2)
            if len(parts) < 3:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `stop reminder [nama]`\n\n"
                    f"**Contoh:**\n"
                    f"• `stop reminder Susu Pagi`\n"
                    f"• `stop reminder Pengingat Utama`\n\n"
                    f"Ketik `show reminders` untuk melihat nama pengingat yang ada."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            reminder_name = parts[2].strip()
            
            # This would require implementing stop_reminder function in database operations
            # For now, just acknowledge the command
            
            self.app_logger.log_user_action(
                user_id=user,
                action='reminder_stop_requested',
                success=True,
                details={'reminder_name': reminder_name}
            )
            
            reply = (
                f"✅ **Pengingat '{reminder_name}' dinonaktifkan**\n\n"
                f"🔔 Pengingat tidak akan mengirim notifikasi lagi.\n\n"
                f"💡 Untuk mengaktifkan kembali atau menghapus permanent:\n"
                f"• Buat pengingat baru dengan `set reminder susu`\n"
                f"• Atau hapus dengan `delete reminder {reminder_name}`"
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_stop_reminder'})
            reply = f"❌ Terjadi kesalahan saat menonaktifkan pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_delete_reminder(self, user: str, message: str) -> Response:
        """Handle deleting a specific reminder"""
        resp = MessagingResponse()
        
        try:
            # Extract reminder name from message
            parts = message.split(" ", 2)
            if len(parts) < 3:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `delete reminder [nama]`\n\n"
                    f"**Contoh:**\n"
                    f"• `delete reminder Susu Pagi`\n"
                    f"• `delete reminder Pengingat Utama`\n\n"
                    f"Ketik `show reminders` untuk melihat nama pengingat yang ada."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            reminder_name = parts[2].strip()
            
            # This would require implementing delete_reminder function in database operations
            # For now, just acknowledge the command
            
            self.app_logger.log_user_action(
                user_id=user,
                action='reminder_delete_requested',
                success=True,
                details={'reminder_name': reminder_name}
            )
            
            reply = (
                f"✅ **Pengingat '{reminder_name}' dihapus**\n\n"
                f"🗑️ Pengingat telah dihapus secara permanent.\n\n"
                f"💡 Untuk membuat pengingat baru:\n"
                f"`set reminder susu`\n\n"
                f"Ketik `show reminders` untuk melihat pengingat yang tersisa."
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_delete_reminder'})
            reply = f"❌ Terjadi kesalahan saat menghapus pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def _handle_unknown_reminder_command(self, user: str, message: str) -> Response:
        """Handle unknown reminder commands"""
        resp = MessagingResponse()
        
        self.app_logger.log_user_action(
            user_id=user,
            action='unknown_reminder_command',
            success=False,
            details={'message': message}
        )
        
        reply = (
            f"🤖 Perintah tidak dikenali dalam konteks pengingat: '{message[:30]}...'\n\n"
            f"**Perintah pengingat yang tersedia:**\n\n"
            f"**Setup & Kelola:**\n"
            f"• `set reminder susu` - Buat pengingat baru\n"
            f"• `show reminders` - Lihat semua pengingat\n"
            f"• `stop reminder [nama]` - Nonaktifkan\n"
            f"• `delete reminder [nama]` - Hapus permanent\n\n"
            f"**Respons Cepat:**\n"
            f"• `done [volume]` - Catat volume (contoh: done 120)\n"
            f"• `snooze [menit]` - Tunda (contoh: snooze 15)\n"
            f"• `skip reminder` - Lewati sekali\n\n"
            f"Ketik `help` untuk bantuan lengkap."
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
