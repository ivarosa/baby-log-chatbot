# handlers/meal_reminder_handler.py
"""
Meal Reminder Handler
Handles setup, management, and quick responses for meal reminders
"""
from datetime import datetime, timedelta
from fastapi import BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    save_meal_reminder, get_meal_reminders, get_meal_reminder_count,
    stop_meal_reminder, delete_meal_reminder
)
from validators import InputValidator
from error_handler import ValidationError
from tier_management import get_tier_limits
from timezone_handler import TimezoneHandler
import json
import logging

class MealReminderHandler:
    """Handle all meal reminder operations"""
    
    # Meal type configurations
    MEAL_TYPES = {
        'breakfast': {
            'emoji': '🌅',
            'default_time': '07:00',
            'name': 'Sarapan',
            'name_en': 'Breakfast'
        },
        'lunch': {
            'emoji': '🌞',
            'default_time': '12:00',
            'name': 'Makan Siang',
            'name_en': 'Lunch'
        },
        'dinner': {
            'emoji': '🌙',
            'default_time': '18:00',
            'name': 'Makan Malam',
            'name_en': 'Dinner'
        },
        'snack': {
            'emoji': '🍎',
            'default_time': '15:00',
            'name': 'Cemilan',
            'name_en': 'Snack'
        }
    }
    
    # Days of week options
    DAYS_OPTIONS = {
        'semua': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
        'weekday': ['mon', 'tue', 'wed', 'thu', 'fri'],
        'weekend': ['sat', 'sun']
    }
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
        
        # Create mock app_logger for compatibility
        class MockAppLogger:
            def log_user_action(self, **kwargs):
                logger.info(f"User action: {kwargs}")
            
            def log_error(self, error, **kwargs):
                logger.error(f"Error: {error}, {kwargs}")
                return f"ERROR_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.app_logger = MockAppLogger()
    
    def handle_meal_reminder_commands(self, user: str, message: str, 
                                     background_tasks: BackgroundTasks) -> Response:
        """Route meal reminder commands"""
        session = self.session_manager.get_session(user)
        message_lower = message.lower()
        
        # Setup new meal reminder
        if (message_lower in ["set reminder makan", "atur pengingat makan"] or
            session["state"] and session["state"].startswith("MEAL_REMINDER")):
            return self.handle_meal_reminder_setup(user, message)
        
        # Show meal reminders
        elif message_lower in ["show meal reminders", "lihat pengingat makan"]:
            return self.handle_show_meal_reminders(user)
        
        # Quick responses
        elif message_lower in ["done makan", "selesai makan"]:
            return self.handle_done_meal(user)
        
        # Management commands
        elif message_lower.startswith("henti reminder makan"):
            return self.handle_stop_meal_reminder(user, message)
        
        elif message_lower.startswith("delete reminder makan"):
            return self.handle_delete_meal_reminder(user, message)
        
        else:
            return self._handle_unknown_meal_reminder_command(user, message)
    
    def handle_meal_reminder_setup(self, user: str, message: str) -> Response:
        """Handle meal reminder setup flow"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() in ["set reminder makan", "atur pengingat makan"]:
                # Check tier limits
                limits = get_tier_limits(user)
                total_reminders = get_meal_reminder_count(user)
                
                # For simplicity, count meal reminders against same limit as milk reminders
                # Or create separate limit if needed
                if limits["active_reminders"] is not None:
                    from database.operations import get_user_reminders
                    milk_reminder_count = len(get_user_reminders(user))
                    total_all_reminders = milk_reminder_count + total_reminders
                    
                    if total_all_reminders >= limits["active_reminders"]:
                        reply = (
                            f"🚫 **Batas Pengingat Tercapai**\n\n"
                            f"Tier gratis dibatasi {limits['active_reminders']} pengingat total.\n"
                            f"Saat ini: {total_all_reminders}/{limits['active_reminders']}\n\n"
                            f"💎 **Upgrade ke premium untuk:**\n"
                            f"• Pengingat unlimited\n"
                            f"• Semua jenis pengingat\n\n"
                            f"💡 Hapus pengingat lama dengan: `delete reminder [nama]`"
                        )
                        
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='meal_reminder_setup_blocked',
                            success=False,
                            details={'reason': 'tier_limit_reached', 'current_count': total_all_reminders}
                        )
                        
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                
                # Start setup flow
                session["state"] = "MEAL_REMINDER_TYPE"
                session["data"] = {}
                
                reply = (
                    f"🍽️ **Setup Pengingat Makan**\n\n"
                    f"Pilih jenis pengingat:\n\n"
                    f"🌅 `sarapan` - Pengingat sarapan pagi\n"
                    f"🌞 `makan siang` - Pengingat makan siang\n"
                    f"🌙 `makan malam` - Pengingat makan malam\n"
                    f"🍎 `snack` - Pengingat cemilan\n\n"
                    f"Ketik jenis pengingat:"
                )
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            elif session["state"] == "MEAL_REMINDER_TYPE":
                meal_type = self._parse_meal_type(message)
                
                if meal_type:
                    session["data"]["meal_type"] = meal_type
                    meal_info = self.MEAL_TYPES[meal_type]
                    
                    session["state"] = "MEAL_REMINDER_TIME"
                    reply = (
                        f"{meal_info['emoji']} **Pengingat {meal_info['name']}**\n\n"
                        f"⏰ Jam berapa pengingat dikirim?\n"
                        f"Format: HH:MM (24 jam)\n\n"
                        f"**Default:** {meal_info['default_time']}\n"
                        f"Ketik 'default' untuk menggunakan waktu default.\n\n"
                        f"**Contoh:**\n"
                        f"• `07:30` - Jam 7:30 pagi\n"
                        f"• `19:00` - Jam 7 malam\n"
                        f"• `default` - Gunakan {meal_info['default_time']}"
                    )
                else:
                    reply = (
                        f"❌ Jenis makan tidak valid.\n\n"
                        f"Pilih salah satu:\n"
                        f"• `sarapan`\n"
                        f"• `makan siang`\n"
                        f"• `makan malam`\n"
                        f"• `snack`"
                    )
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            elif session["state"] == "MEAL_REMINDER_TIME":
                meal_type = session["data"]["meal_type"]
                meal_info = self.MEAL_TYPES[meal_type]
                
                if message.lower().strip() == "default":
                    reminder_time = meal_info['default_time']
                else:
                    # Validate time
                    time_input = message.replace('.', ':').strip()
                    is_valid, error_msg = InputValidator.validate_time(time_input)
                    
                    if not is_valid:
                        reply = f"❌ {error_msg}\n\nMasukkan waktu dengan format HH:MM (contoh: 07:30)"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    
                    reminder_time = time_input
                
                session["data"]["reminder_time"] = reminder_time
                session["state"] = "MEAL_REMINDER_DAYS"
                
                reply = (
                    f"📅 **Hari apa saja pengingat dikirim?**\n\n"
                    f"Pilih salah satu:\n"
                    f"• `semua` - Setiap hari (Senin-Minggu)\n"
                    f"• `weekday` - Hari kerja (Senin-Jumat)\n"
                    f"• `weekend` - Akhir pekan (Sabtu-Minggu)\n"
                    f"• `custom` - Pilih hari tertentu\n\n"
                    f"Ketik pilihan Anda:"
                )
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            elif session["state"] == "MEAL_REMINDER_DAYS":
                days_option = message.lower().strip()
                
                if days_option in ['semua', 'weekday', 'weekend']:
                    days_of_week = self.DAYS_OPTIONS[days_option]
                    session["data"]["days_of_week"] = json.dumps(days_of_week)
                    session["state"] = "MEAL_REMINDER_CONFIRM"
                    
                    reply = self._format_meal_reminder_confirmation(session["data"])
                    
                elif days_option == 'custom':
                    session["state"] = "MEAL_REMINDER_CUSTOM_DAYS"
                    reply = (
                        f"📅 **Pilih Hari Spesifik**\n\n"
                        f"Masukkan hari yang diinginkan (pisahkan dengan koma):\n\n"
                        f"**Contoh:**\n"
                        f"• `senin, rabu, jumat`\n"
                        f"• `selasa, kamis`\n"
                        f"• `sabtu, minggu`\n\n"
                        f"Ketik hari-hari yang diinginkan:"
                    )
                else:
                    reply = (
                        f"❌ Pilihan tidak valid.\n\n"
                        f"Pilih: `semua`, `weekday`, `weekend`, atau `custom`"
                    )
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            elif session["state"] == "MEAL_REMINDER_CUSTOM_DAYS":
                days_of_week = self._parse_custom_days(message)
                
                if days_of_week:
                    session["data"]["days_of_week"] = json.dumps(days_of_week)
                    session["state"] = "MEAL_REMINDER_CONFIRM"
                    
                    reply = self._format_meal_reminder_confirmation(session["data"])
                else:
                    reply = (
                        f"❌ Hari tidak valid.\n\n"
                        f"Masukkan hari dengan format:\n"
                        f"`senin, rabu, jumat` atau `sabtu, minggu`\n\n"
                        f"Hari yang valid:\n"
                        f"senin, selasa, rabu, kamis, jumat, sabtu, minggu"
                    )
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            elif session["state"] == "MEAL_REMINDER_CONFIRM":
                if message.lower() == "ya":
                    try:
                        # Calculate next due time
                        meal_type = session["data"]["meal_type"]
                        reminder_time = session["data"]["reminder_time"]
                        meal_info = self.MEAL_TYPES[meal_type]
                        
                        # Create reminder name
                        reminder_name = f"Pengingat {meal_info['name']}"
                        session["data"]["reminder_name"] = reminder_name
                        
                        # Calculate next due
                        next_due = self._calculate_next_due(
                            user, 
                            reminder_time, 
                            json.loads(session["data"]["days_of_week"])
                        )
                        session["data"]["next_due"] = next_due
                        
                        # Save to database
                        save_meal_reminder(user, session["data"])
                        
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='meal_reminder_created',
                            success=True,
                            details={
                                'meal_type': meal_type,
                                'reminder_time': reminder_time,
                                'days_of_week': session["data"]["days_of_week"]
                            }
                        )
                        
                        # Format next due for display
                        next_due_local = TimezoneHandler.to_local(next_due, user)
                        next_due_str = next_due_local.strftime('%d/%m/%Y %H:%M')
                        
                        reply = (
                            f"✅ **Pengingat {meal_info['name']} berhasil dibuat!**\n\n"
                            f"{meal_info['emoji']} Pengingat pertama: {next_due_str}\n\n"
                            f"**Saat pengingat muncul:**\n"
                            f"• `done makan` - Tandai sudah makan\n"
                            f"• `snooze 30` - Tunda 30 menit\n"
                            f"• `skip reminder` - Lewati\n\n"
                            f"💡 Jangan lupa catat makanan dengan `catat mpasi`"
                        )
                        
                        session["state"] = None
                        session["data"] = {}
                        
                    except ValidationError as e:
                        reply = f"❌ {str(e)}"
                        self.app_logger.log_user_action(
                            user_id=user,
                            action='meal_reminder_created',
                            success=False,
                            details={'error': str(e)}
                        )
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user, 
                            context={'function': 'save_meal_reminder'})
                        reply = f"❌ Terjadi kesalahan saat menyimpan pengingat. Kode error: {error_id}"
                    
                elif message.lower() == "tidak":
                    session["state"] = "MEAL_REMINDER_TYPE"
                    session["data"] = {}
                    reply = "🔄 Mari ulang dari awal. Pilih jenis pengingat:\n\n🌅 `sarapan`\n🌞 `makan siang`\n🌙 `makan malam`\n🍎 `snack`"
                
                elif message.lower() == "batal":
                    session["state"] = None
                    session["data"] = {}
                    reply = "❌ Setup pengingat makan dibatalkan."
                
                else:
                    reply = "Ketik `ya` jika benar, `tidak` untuk mengulang, atau `batal` untuk membatalkan."
                
                self.session_manager.update_session(user, 
                    state=session["state"], data=session["data"])
            
            else:
                reply = "Perintah tidak dikenali dalam konteks setup pengingat makan."
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, 
                context={'function': 'handle_meal_reminder_setup'})
            resp.message(f"❌ Terjadi kesalahan sistem. Kode error: {error_id}")
            return Response(str(resp), media_type="application/xml")
    
    def handle_show_meal_reminders(self, user: str) -> Response:
        """Show user's meal reminders"""
        resp = MessagingResponse()
        
        try:
            reminders = get_meal_reminders(user)
            
            if not reminders:
                reply = (
                    f"📋 **Pengingat Makan**\n\n"
                    f"Belum ada pengingat makan yang diatur.\n\n"
                    f"**Buat pengingat baru:**\n"
                    f"`set reminder makan`\n\n"
                    f"💡 **Manfaat pengingat makan:**\n"
                    f"• Jadwal makan teratur untuk bayi\n"
                    f"• Reminder otomatis setiap hari\n"
                    f"• Tracking nutrisi lebih mudah"
                )
            else:
                reply = "📋 **Pengingat Makan Aktif:**\n\n"
                
                for i, r in enumerate(reminders, 1):
                    if isinstance(r, dict):
                        reminder_name = r['reminder_name']
                        meal_type = r['meal_type']
                        reminder_time = r['reminder_time']
                        is_active = r['is_active']
                        days_of_week = r.get('days_of_week')
                        next_due = r.get('next_due')
                    else:
                        # Tuple: id, reminder_name, meal_type, reminder_time, is_active, next_due, days_of_week
                        reminder_name = r[1]
                        meal_type = r[2]
                        reminder_time = r[3]
                        is_active = r[4]
                        next_due = r[5] if len(r) > 5 else None
                        days_of_week = r[6] if len(r) > 6 else None
                    
                    meal_info = self.MEAL_TYPES.get(meal_type, {})
                    emoji = meal_info.get('emoji', '🍽️')
                    meal_name = meal_info.get('name', meal_type)
                    status = "🟢 Aktif" if is_active else "🔴 Nonaktif"
                    
                    # Format days
                    if days_of_week:
                        try:
                            days_list = json.loads(days_of_week)
                            days_display = self._format_days_display(days_list)
                        except:
                            days_display = "Setiap hari"
                    else:
                        days_display = "Setiap hari"
                    
                    # Format next due
                    if next_due:
                        try:
                            if isinstance(next_due, str):
                                next_due_dt = datetime.fromisoformat(next_due.replace('Z', '+00:00'))
                            else:
                                next_due_dt = next_due
                            
                            next_due_local = TimezoneHandler.to_local(next_due_dt, user)
                            next_due_str = next_due_local.strftime('%d/%m %H:%M')
                        except:
                            next_due_str = "Tidak diketahui"
                    else:
                        next_due_str = "Tidak diketahui"
                    
                    reply += (
                        f"{i}. {emoji} **{meal_name}** {status}\n"
                        f"   ⏰ Jam: {reminder_time}\n"
                        f"   📅 Hari: {days_display}\n"
                        f"   📍 Berikutnya: {next_due_str}\n\n"
                    )
                
                reply += (
                    f"**Kelola pengingat:**\n"
                    f"• `henti reminder makan [nama]` - Matikan\n"
                    f"• `delete reminder makan [nama]` - Hapus\n\n"
                    f"**Respons cepat saat pengingat:**\n"
                    f"• `done makan` - Tandai selesai\n"
                    f"• `snooze [menit]` - Tunda\n"
                    f"• `skip reminder` - Lewati"
                )
                
                # Add tier info
                limits = get_tier_limits(user)
                if limits.get("active_reminders"):
                    reply += f"\n\n📊 Pengingat makan: {len(reminders)}"
            
            self.app_logger.log_user_action(
                user_id=user,
                action='meal_reminders_viewed',
                success=True,
                details={'reminder_count': len(reminders)}
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, 
                context={'function': 'handle_show_meal_reminders'})
            reply = f"❌ Terjadi kesalahan saat mengambil pengingat. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_done_meal(self, user: str) -> Response:
        """Handle 'done makan' quick response"""
        resp = MessagingResponse()
        
        try:
            self.app_logger.log_user_action(
                user_id=user,
                action='meal_completed_via_reminder',
                success=True,
                details={'time': datetime.now().strftime('%H:%M')}
            )
            
            reply = (
                f"✅ **Selesai makan!**\n\n"
                f"📝 Jangan lupa catat makanannya:\n"
                f"• `catat mpasi` - Detail makanan bayi\n\n"
                f"💡 **Tips:**\n"
                f"Tracking makanan membantu monitor:\n"
                f"• Asupan nutrisi harian\n"
                f"• Variasi menu\n"
                f"• Pola makan bayi\n\n"
                f"Ketik `catat mpasi` untuk mencatat sekarang."
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, 
                context={'function': 'handle_done_meal'})
            reply = f"❌ Terjadi kesalahan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_stop_meal_reminder(self, user: str, message: str) -> Response:
        """Stop a meal reminder"""
        resp = MessagingResponse()
        
        try:
            parts = message.split(" ", 3)
            if len(parts) < 4:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `henti reminder makan [nama]`\n\n"
                    f"**Contoh:**\n"
                    f"• `henti reminder makan Pengingat Sarapan`\n"
                    f"• `henti reminder makan Pengingat Makan Siang`\n\n"
                    f"Ketik `show meal reminders` untuk melihat nama pengingat."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            reminder_name = parts[3].strip()
            success = stop_meal_reminder(user, reminder_name)
            
            if success:
                self.app_logger.log_user_action(
                    user_id=user,
                    action='meal_reminder_stopped',
                    success=True,
                    details={'reminder_name': reminder_name}
                )
                
                reply = (
                    f"✅ **Pengingat '{reminder_name}' dinonaktifkan**\n\n"
                    f"🔔 Pengingat tidak akan mengirim notifikasi lagi.\n\n"
                    f"💡 Untuk mengaktifkan kembali atau menghapus permanent:\n"
                    f"• Buat baru: `set reminder makan`\n"
                    f"• Hapus: `delete reminder makan {reminder_name}`"
                )
            else:
                reply = (
                    f"❌ **Tidak dapat menonaktifkan '{reminder_name}'**\n\n"
                    f"Kemungkinan:\n"
                    f"• Nama pengingat tidak ditemukan\n"
                    f"• Sudah tidak aktif\n\n"
                    f"Ketik `show meal reminders` untuk melihat daftar."
                )
                
                self.app_logger.log_user_action(
                    user_id=user,
                    action='meal_reminder_stopped',
                    success=False,
                    details={'reminder_name': reminder_name}
                )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, 
                context={'function': 'handle_stop_meal_reminder'})
            reply = f"❌ Terjadi kesalahan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_delete_meal_reminder(self, user: str, message: str) -> Response:
        """Delete a meal reminder permanently"""
        resp = MessagingResponse()
        
        try:
            parts = message.split(" ", 3)
            if len(parts) < 4:
                reply = (
                    f"❌ **Format tidak lengkap**\n\n"
                    f"Gunakan: `delete reminder makan [nama]`\n\n"
                    f"**Contoh:**\n"
                    f"• `delete reminder makan Pengingat Sarapan`\n"
                    f"• `delete reminder makan Pengingat Snack`\n\n"
                    f"Ketik `show meal reminders` untuk melihat nama pengingat."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            reminder_name = parts[3].strip()
            success = delete_meal_reminder(user, reminder_name)
            
            if success:
                self.app_logger.log_user_action(
                    user_id=user,
                    action='meal_reminder_deleted',
                    success=True,
                    details={'reminder_name': reminder_name}
                )
                
                reply = (
                    f"✅ **Pengingat '{reminder_name}' dihapus**\n\n"
                    f"🗑️ Pengingat telah dihapus permanent.\n\n"
                    f"💡 Untuk membuat pengingat baru:\n"
                    f"`set reminder makan`"
                )
            else:
                reply = (
                    f"❌ **Tidak dapat menghapus '{reminder_name}'**\n\n"
                    f"Kemungkinan:\n"
                    f"• Nama pengingat tidak ditemukan\n"
                    f"• Sudah terhapus\n\n"
                    f"Ketik `show meal reminders` untuk melihat daftar."
                )
                
                self.app_logger.log_user_action(
                    user_id=user,
                    action='meal_reminder_deleted',
                    success=False,
                    details={'reminder_name': reminder_name}
                )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, 
                context={'function': 'handle_delete_meal_reminder'})
            reply = f"❌ Terjadi kesalahan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def _parse_meal_type(self, message: str) -> Optional[str]:
        """Parse user input to meal type"""
        message = message.lower().strip()
        
        meal_mapping = {
            'sarapan': 'breakfast',
            'breakfast': 'breakfast',
            'pagi': 'breakfast',
            
            'makan siang': 'lunch',
            'lunch': 'lunch',
            'siang': 'lunch',
            
            'makan malam': 'dinner',
            'dinner': 'dinner',
            'malam': 'dinner',
            
            'snack': 'snack',
            'cemilan': 'snack',
            'camilan': 'snack'
        }
        
        return meal_mapping.get(message)
    
    def _parse_custom_days(self, message: str) -> Optional[list]:
        """Parse custom days input"""
        day_mapping = {
            'senin': 'mon', 'monday': 'mon',
            'selasa': 'tue', 'tuesday': 'tue',
            'rabu': 'wed', 'wednesday': 'wed',
            'kamis': 'thu', 'thursday': 'thu',
            'jumat': 'fri', 'friday': 'fri',
            'sabtu': 'sat', 'saturday': 'sat',
            'minggu': 'sun', 'sunday': 'sun'
        }
        
        # Split by comma and clean
        day_inputs = [d.strip().lower() for d in message.split(',')]
        
        parsed_days = []
        for day_input in day_inputs:
            if day_input in day_mapping:
                parsed_days.append(day_mapping[day_input])
        
        return parsed_days if parsed_days else None
    
    def _format_days_display(self, days_list: list) -> str:
        """Format days list for display"""
        day_names = {
            'mon': 'Sen', 'tue': 'Sel', 'wed': 'Rab',
            'thu': 'Kam', 'fri': 'Jum', 'sat': 'Sab', 'sun': 'Min'
        }
        
        if len(days_list) == 7:
            return "Setiap hari"
        elif set(days_list) == {'mon', 'tue', 'wed', 'thu', 'fri'}:
            return "Hari kerja (Sen-Jum)"
        elif set(days_list) == {'sat', 'sun'}:
            return "Akhir pekan (Sab-Min)"
        else:
            return ", ".join([day_names.get(d, d) for d in days_list])
    
    def _calculate_next_due(self, user: str, reminder_time: str, 
                           days_of_week: list) -> datetime:
        """Calculate next due time for reminder"""
        current_local = TimezoneHandler.now_local(user)
        
        hour, minute = map(int, reminder_time.split(':'))
        
        # Start from today
        next_due_local = current_local.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        
        # If time has passed today, start from tomorrow
        if next_due_local <= current_local:
            next_due_local += timedelta(days=1)
        
        # Find next valid day
        max_attempts = 7  # Check up to 7 days
        for _ in range(max_attempts):
            day_abbr = next_due_local.strftime('%a').lower()[:3]
            if day_abbr in days_of_week:
                break
            next_due_local += timedelta(days=1)
        
        # Convert to UTC for storage
        next_due_utc = TimezoneHandler.to_utc(next_due_local, user).replace(tzinfo=None)
        
        return next_due_utc
    
    def _format_meal_reminder_confirmation(self, data: dict) -> str:
        """Format confirmation message"""
        meal_type = data['meal_type']
        meal_info = self.MEAL_TYPES[meal_type]
        reminder_time = data['reminder_time']
        days_of_week = json.loads(data['days_of_week'])
        
        days_display = self._format_days_display(days_of_week)
        
        return (
            f"✅ **Konfirmasi Pengingat Makan**\n\n"
            f"{meal_info['emoji']} **Jenis:** {meal_info['name']}\n"
            f"⏰ **Jam:** {reminder_time}\n"
            f"📅 **Hari:** {days_display}\n\n"
            f"Apakah data sudah benar?\n"
            f"• Ketik `ya` untuk simpan\n"
            f"• Ketik `tidak` untuk mengulang\n"
            f"• Ketik `batal` untuk membatalkan"
        )
    
    def _handle_unknown_meal_reminder_command(self, user: str, message: str) -> Response:
        """Handle unknown meal reminder commands"""
        resp = MessagingResponse()
        
        self.app_logger.log_user_action(
            user_id=user,
            action='unknown_meal_reminder_command',
            success=False,
            details={'message': message}
        )
        
        reply = (
            f"🤖 Perintah tidak dikenali: '{message[:30]}...'\n\n"
            f"**Perintah pengingat makan:**\n\n"
            f"**Setup & Kelola:**\n"
            f"• `set reminder makan` - Buat baru\n"
            f"• `show meal reminders` - Lihat semua\n"
            f"• `henti reminder makan [nama]` - Nonaktifkan\n"
            f"• `delete reminder makan [nama]` - Hapus\n\n"
            f"**Respons Cepat:**\n"
            f"• `done makan` - Tandai selesai\n"
            f"• `snooze [menit]` - Tunda\n"
            f"• `skip reminder` - Lewati\n\n"
            f"Ketik `help` untuk bantuan lengkap."
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
