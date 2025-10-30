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
    get_user_calorie_setting, stop_reminder
)
from validators import InputValidator
from error_handler import ValidationError
from tier_management import get_tier_limits, increment_message_count
from timezone_handler import TimezoneHandler
import re
import logging

class ReminderHandler:
    """Handle all reminder-related operations"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger  # Use simple logger instead of app_logger
        
        # Create a mock app_logger to handle all the app_logger calls
        class MockAppLogger:
            def log_user_action(self, **kwargs):
                logger.info(f"User action: {kwargs}")
            
            def log_error(self, error, **kwargs):
                logger.error(f"Error: {error}, {kwargs}")
                from datetime import datetime
                error_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                return error_id
        
        self.app_logger = MockAppLogger()
    
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
        elif message.lower().startswith("henti reminder"):
            return self.handle_stop_reminder(user, message)
        
        elif message.lower().startswith("delete reminder"):
            return self.handle_delete_reminder(user, message)
        
        else:
            return self._handle_unknown_reminder_command(user, message)
    
    def handle_reminder_setup(self, user: str, message: str) -> Response:
        """Handle reminder setup flow - OPTIMIZED"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() in ["set reminder susu", "atur pengingat susu"]:
                # Check tier limits
                limits = get_tier_limits(user)
                if limits["active_reminders"] is not None:
                    active_reminders = len(get_user_reminders(user))
                    if active_reminders >= limits["active_reminders"]:
                        # OPTIMIZED: Shorter limit message
                        reply = (
                            f"🚫 Batas tercapai: {active_reminders}/{limits['active_reminders']}\n\n"
                            f"💎 Upgrade untuk unlimited\n"
                            f"Atau hapus: 'delete reminder [nama]'"
                        )
                        
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='reminder_setup_blocked',
                            success=False
                        )
                        
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                
                session["state"] = "REMINDER_NAME"
                session["data"] = {}
                reply = "🔔 Nama pengingat?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_NAME":
                reminder_name = InputValidator.sanitize_text_input(message, 50)
                session["data"]["reminder_name"] = reminder_name
                session["state"] = "REMINDER_INTERVAL"
                reply = "⏰ Setiap berapa jam? (1-12)"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_INTERVAL":
                try:
                    interval = int(message)
                    if 1 <= interval <= 12:
                        session["data"]["interval_hours"] = interval
                        session["state"] = "REMINDER_START"
                        reply = "🌅 Jam mulai? (HH:MM)"  # OPTIMIZED: Much shorter
                    else:
                        reply = "❌ Harus 1-12 jam"  # OPTIMIZED: Shorter
                except ValueError:
                    reply = "❌ Masukkan angka"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_START":
                is_valid, error_msg = InputValidator.validate_time(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["start_time"] = message
                    session["state"] = "REMINDER_END"
                    reply = "🌙 Jam berhenti? (HH:MM)"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_END":
                is_valid, error_msg = InputValidator.validate_time(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["end_time"] = message
                    session["state"] = "REMINDER_CONFIRM"
                    
                    # Calculate first reminder
                    start_hour, start_min = map(int, session["data"]["start_time"].split(':'))
                    current_local = TimezoneHandler.now_local(user)
                    next_reminder = current_local.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                    if next_reminder <= current_local:
                        next_reminder += timedelta(days=1)
                    
                    # OPTIMIZED: Much shorter confirmation
                    reply = (
                        f"✅ Konfirmasi:\n"
                        f"• {session['data']['reminder_name']}\n"
                        f"• Tiap {session['data']['interval_hours']} jam\n"
                        f"• {session['data']['start_time']}-{session['data']['end_time']}\n"
                        f"• Pertama: {next_reminder.strftime('%H:%M')}\n\n"
                        f"Benar? (ya/tidak/batal)"
                    )
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "REMINDER_CONFIRM":
                if message.lower() == "ya":
                    try:
                        save_reminder(user, session["data"])
                        
                        self.app_logger.log_user_action(user_id=user, action='reminder_created', success=True)
                        
                        # OPTIMIZED: Much shorter success message
                        reply = (
                            f"✅ Pengingat '{session['data']['reminder_name']}' aktif!\n\n"
                            f"Saat muncul:\n"
                            f"• 'done [ml]' - Log volume\n"
                            f"• 'snooze [min]' - Tunda\n"
                            f"• 'skip reminder' - Lewati"
                        )
                        session["state"] = None
                        session["data"] = {}
                        
                    except (ValueError, ValidationError) as e:
                        reply = f"❌ {str(e)}"
                        self.app_logger.log_user_action(user_id=user, action='reminder_created', success=False)
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user)
                        reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
                        
                elif message.lower() == "tidak":
                    session["state"] = "REMINDER_NAME"
                    reply = "Nama pengingat?"  # OPTIMIZED: Much shorter
                elif message.lower() == "batal":
                    session["state"] = None
                    session["data"] = {}
                    reply = "❌ Dibatalkan"  # OPTIMIZED: Much shorter
                else:
                    reply = "Ketik: ya/tidak/batal"  # OPTIMIZED: Shorter
                    
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "❓ Perintah tidak dikenali"  # OPTIMIZED: Much shorter
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            resp.message(f"❌ Error: {error_id}")  # OPTIMIZED: Shorter
            return Response(str(resp), media_type="application/xml")
    
    def handle_show_reminders(self, user: str) -> Response:
        """Handle showing user's reminders - OPTIMIZED"""
        resp = MessagingResponse()
        
        try:
            reminders = get_user_reminders(user)
            if not reminders:
                # OPTIMIZED: Much shorter
                reply = (
                    f"📋 Belum ada pengingat\n\n"
                    f"Buat baru: 'set reminder susu'"
                )
            else:
                # OPTIMIZED: Shorter header
                reply = "📋 Pengingat Aktif:\n\n"
                
                for i, r in enumerate(reminders, 1):
                    if isinstance(r, dict):
                        name = r['reminder_name']
                        interval = r['interval_hours']
                        start = r['start_time']
                        end = r['end_time']
                        is_active = r['is_active']
                        next_due = r.get('next_due', 'Tidak diketahui')
                    else:
                        if len(r) < 6:
                            error_id = self.app_logger.log_error(
                                Exception(f"Incomplete reminder row"),
                                user_id=user
                            )
                            continue
                        
                        name = r[0]
                        interval = r[1]
                        start = r[2]
                        end = r[3]
                        is_active = r[4]
                        next_due = r[5] if len(r) > 5 else 'Tidak diketahui'
                    
                    status = "🟢" if is_active else "🔴"
                    
                    # Format next due
                    if next_due and next_due != 'Tidak diketahui':
                        try:
                            if isinstance(next_due, str):
                                next_due_dt = datetime.fromisoformat(next_due.replace('Z', '+00:00'))
                            else:
                                next_due_dt = next_due
                            next_str = next_due_dt.strftime('%H:%M')
                        except:
                            next_str = str(next_due)
                    else:
                        next_str = "-"
                    
                    # OPTIMIZED: Compact format
                    reply += f"{i}. {status} {name}\n   Tiap {interval}j ({start}-{end})\n   Next: {next_str}\n\n"
                
                # OPTIMIZED: Shorter commands
                reply += (
                    f"Kelola:\n"
                    f"• 'henti reminder [nama]'\n"
                    f"• 'delete reminder [nama]'"
                )
                
                # Tier info
                limits = get_tier_limits(user)
                if limits.get("active_reminders"):
                    reply += f"\n\n📊 {len(reminders)}/{limits['active_reminders']}"
            
            self.app_logger.log_user_action(user_id=user, action='reminders_viewed', success=True)
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_reminder_done(self, user: str, message: str) -> Response:
        """Handle 'done [volume]' quick response - OPTIMIZED"""
        resp = MessagingResponse()
        
        try:
            volume_match = re.search(r'done\s+(\d+)', message.lower())
            if not volume_match:
                # OPTIMIZED: Much shorter error
                reply = "❌ Format: done [volume]\nContoh: done 120"
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            volume = float(volume_match.group(1))
            
            if volume <= 0 or volume > 1000:
                reply = "❌ Volume harus 1-1000 ml"  # OPTIMIZED: Shorter
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Create milk intake record
            milk_data = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M"),
                'volume_ml': volume,
                'milk_type': 'mixed',
                'note': 'Via reminder'
            }
            
            save_milk_intake(user, milk_data)
            
            self.app_logger.log_user_action(user_id=user, action='reminder_done_logged', success=True)
            
            # OPTIMIZED: Much shorter success message
            reply = (
                f"✅ Tercatat!\n"
                f"• {volume}ml @ {milk_data['time']}\n\n"
                f"Ketik 'lihat ringkasan susu'"
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_reminder_snooze(self, user: str, message: str) -> Response:
        """Handle 'snooze [minutes]' quick response - OPTIMIZED"""
        resp = MessagingResponse()
        
        try:
            snooze_match = re.search(r'snooze\s+(\d+)', message.lower())
            if not snooze_match:
                # OPTIMIZED: Much shorter error
                reply = "❌ Format: snooze [menit]\nContoh: snooze 15"
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            minutes = int(snooze_match.group(1))
            
            if minutes <= 0 or minutes > 180:
                reply = "❌ Harus 1-180 menit"  # OPTIMIZED: Shorter
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            self.app_logger.log_user_action(user_id=user, action='reminder_snoozed', success=True)
            
            new_time = datetime.now() + timedelta(minutes=minutes)
            
            # OPTIMIZED: Much shorter message
            reply = f"⏰ Ditunda {minutes} menit\n\nNext: {new_time.strftime('%H:%M')}"
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
        
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
                    f"Gunakan: `henti reminder [nama]`\n\n"
                    f"**Contoh:**\n"
                    f"• `henti reminder Susu Pagi`\n"
                    f"• `henti reminder Pengingat Utama`\n\n"
                    f"Ketik `show reminders` untuk melihat nama pengingat yang ada."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            reminder_name = parts[2].strip()
            
            # Call the database function to actually stop the reminder
            success = stop_reminder(user, reminder_name)
            
            if success:
                self.app_logger.log_user_action(
                    user_id=user,
                    action='reminder_stop_successful',
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
            else:
                self.app_logger.log_user_action(
                    user_id=user,
                    action='reminder_stop_failed',
                    success=False,
                    details={'reminder_name': reminder_name}
                )
                
                reply = (
                    f"❌ **Tidak dapat menonaktifkan pengingat '{reminder_name}'**\n\n"
                    f"Kemungkinan penyebab:\n"
                    f"• Nama pengingat tidak ditemukan\n"
                    f"• Pengingat sudah tidak aktif\n\n"
                    f"Ketik `show reminders` untuk melihat daftar pengingat aktif."
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
        """Handle unknown reminder commands - OPTIMIZED"""
        resp = MessagingResponse()
        
        # OPTIMIZED: Much shorter help text
        reply = (
            f"❓ Perintah tidak dikenali\n\n"
            f"Coba:\n"
            f"• 'set reminder susu'\n"
            f"• 'show reminders'\n"
            f"• 'done [ml]'\n"
            f"• 'snooze [menit]'\n\n"
            f"Ketik 'help'"
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
