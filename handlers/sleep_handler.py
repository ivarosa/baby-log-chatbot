# handlers/sleep_handler.py
"""
Sleep tracking handler
Handles sleep session management, tracking, and reporting
"""
from datetime import datetime, timedelta
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from sleep_tracking import (
    start_sleep_record, get_latest_open_sleep_id, get_sleep_by_id,
    update_sleep_record, get_sleep_summary, get_sleep_record_count,
    get_sleep_records_with_limit, delete_oldest_sleep_record
)
from validators import InputValidator
from error_handler import ValidationError
from tier_management import get_tier_limits
import logging

class SleepHandler:
    """Handle all sleep tracking operations"""
    
    def __init__(self, session_manager, app_logger):
        self.session_manager = session_manager
        self.app_logger = app_logger
    
    def handle_sleep_commands(self, user: str, message: str) -> Response:
        """Route sleep commands to appropriate handlers"""
        
        # Start sleep tracking
        if message.lower() == "catat tidur":
            return self.handle_start_sleep(user)
        
        # End sleep tracking
        elif message.lower().startswith("selesai tidur"):
            return self.handle_end_sleep(user, message)
        
        # Cancel sleep session
        elif message.lower() == "batal tidur":
            return self.handle_cancel_sleep(user)
        
        # View sleep records
        elif message.lower() in ["lihat tidur", "tidur hari ini"]:
            return self.handle_view_today_sleep(user)
        
        # View sleep history
        elif message.lower() in ["riwayat tidur", "sleep history"]:
            return self.handle_view_sleep_history(user)
        
        else:
            return self._handle_unknown_sleep_command(user, message)
    
    def handle_start_sleep(self, user: str) -> Response:
        """Handle starting a new sleep session"""
        resp = MessagingResponse()
        
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")
            
            # Check if user has an incomplete sleep session first
            existing_sleep_id = get_latest_open_sleep_id(user)
            if existing_sleep_id:
                sleep_data = get_sleep_by_id(existing_sleep_id)
                start_time = sleep_data.get('start_time', 'tidak diketahui')
                
                reply = (
                    f"⚠️ **Anda masih memiliki sesi tidur yang belum selesai**\n\n"
                    f"📅 Dimulai: {start_time}\n\n"
                    f"**Pilihan:**\n"
                    f"• `selesai tidur [HH:MM]` - Selesaikan sesi\n"
                    f"• `batal tidur` - Batalkan sesi\n\n"
                    f"**Contoh:** `selesai tidur 07:30`"
                )
                
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_start_blocked',
                    success=False,
                    details={'reason': 'existing_incomplete_session'}
                )
                
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Check tier limits for new sleep session
            limits = get_tier_limits(user)
            if limits["sleep_record"] is not None:  # Free user
                current_count = get_sleep_record_count(user)
                if current_count >= limits["sleep_record"]:
                    reply = (
                        f"🚫 **Batas Catatan Tidur Tercapai**\n\n"
                        f"Tier gratis dibatasi {limits['sleep_record']} catatan tidur.\n"
                        f"Saat ini: {current_count}/{limits['sleep_record']}\n\n"
                        f"💎 **Upgrade ke premium untuk:**\n"
                        f"• Catatan tidur unlimited\n"
                        f"• Analisis pola tidur\n"
                        f"• Laporan bulanan\n\n"
                        f"💡 **Tip:** Hapus catatan lama atau upgrade ke premium."
                    )
                    
                    self.app_logger.log_user_action(
                        user_id=user,
                        action='sleep_start_blocked',
                        success=False,
                        details={'reason': 'tier_limit_reached', 'current_count': current_count}
                    )
                    
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
            
            # Start new sleep session
            sleep_id, message_result = start_sleep_record(user, today, time_str)
            if sleep_id:
                # Get updated count and limits for display
                updated_count = get_sleep_record_count(user)
                sleep_limit = limits.get('sleep_record')
                
                if sleep_limit is not None:
                    limit_info = f"\n\n📊 **Catatan tidur:** {updated_count}/{sleep_limit}"
                    if updated_count >= sleep_limit * 0.8:  # Warn when 80% full
                        limit_info += f"\n⚠️ Mendekati batas maksimal!"
                else:
                    limit_info = f"\n\n📊 **Catatan tidur:** {updated_count} (unlimited)"
                
                reply = (
                    f"✅ **Mulai mencatat tidur pada {time_str}**{limit_info}\n\n"
                    f"😴 Selamat tidur! Ketika bayi bangun, ketik:\n"
                    f"`selesai tidur [HH:MM]`\n\n"
                    f"**Contoh:**\n"
                    f"• `selesai tidur 07:30`\n"
                    f"• `selesai tidur 06:45`\n\n"
                    f"💡 Atau ketik `batal tidur` untuk membatalkan."
                )
                
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_started',
                    success=True,
                    details={
                        'sleep_id': sleep_id,
                        'start_time': time_str,
                        'date': today,
                        'current_count': updated_count
                    }
                )
            else:
                reply = f"❌ {message_result}"
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_started',
                    success=False,
                    details={'error': message_result}
                )
                
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_start_sleep'})
            reply = f"❌ Terjadi kesalahan saat memulai catatan tidur. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_end_sleep(self, user: str, message: str) -> Response:
        """Handle ending a sleep session"""
        resp = MessagingResponse()
        
        try:
            # Parse the end time from message
            parts = message.split()
            if len(parts) < 3:
                reply = (
                    "❌ **Format tidak lengkap**\n\n"
                    "Gunakan: `selesai tidur [HH:MM]`\n\n"
                    "**Contoh:**\n"
                    "• `selesai tidur 07:30`\n"
                    "• `selesai tidur 19:45`"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            end_time = parts[2]
            
            # Validate time format
            is_valid, error_msg = InputValidator.validate_time(end_time)
            if not is_valid:
                reply = (
                    f"❌ **Format waktu tidak valid**\n\n"
                    f"Detail: {error_msg}\n\n"
                    "Gunakan format HH:MM (24 jam)\n"
                    "**Contoh:** `selesai tidur 07:30`"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Check if there's an active sleep session
            sleep_id = get_latest_open_sleep_id(user)
            if not sleep_id:
                reply = (
                    "❌ **Tidak ada sesi tidur yang sedang berlangsung**\n\n"
                    "Mulai sesi baru dengan: `catat tidur`"
                )
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_end_failed',
                    success=False,
                    details={'reason': 'no_active_session'}
                )
            else:
                # Complete the sleep session
                reply = self._complete_sleep_session(user, sleep_id, end_time)
                
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_end_sleep'})
            reply = f"❌ Terjadi kesalahan saat menyelesaikan catatan tidur. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_cancel_sleep(self, user: str) -> Response:
        """Handle canceling an incomplete sleep session"""
        resp = MessagingResponse()
        
        try:
            sleep_id = get_latest_open_sleep_id(user)
            if not sleep_id:
                reply = "❌ Tidak ada sesi tidur yang sedang berlangsung untuk dibatalkan."
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_cancel_failed',
                    success=False,
                    details={'reason': 'no_active_session'}
                )
            else:
                # Delete the incomplete sleep record
                from database.operations import db_pool
                from database_security import DatabaseSecurity
                import os
                
                database_url = os.environ.get('DATABASE_URL')
                user_col = DatabaseSecurity.get_user_column(database_url)
                table_name = DatabaseSecurity.validate_table_name('sleep_log')
                
                with db_pool.get_connection() as conn:
                    c = conn.cursor()
                    if database_url:
                        c.execute(f'DELETE FROM {table_name} WHERE id=%s', (sleep_id,))
                    else:
                        c.execute(f'DELETE FROM {table_name} WHERE id=?', (sleep_id,))
                
                reply = "✅ Sesi tidur yang belum selesai telah dibatalkan."
                
                self.app_logger.log_user_action(
                    user_id=user,
                    action='sleep_cancelled',
                    success=True,
                    details={'sleep_id': sleep_id}
                )
                
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_cancel_sleep'})
            reply = f"❌ Terjadi kesalahan saat membatalkan sesi tidur. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_view_today_sleep(self, user: str) -> Response:
        """Handle viewing today's sleep records"""
        resp = MessagingResponse()
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            sleep_rows = get_sleep_summary(user, today)
            
            if not sleep_rows:
                reply = (
                    f"😴 **Belum ada catatan tidur hari ini**\n\n"
                    f"Mulai dengan: `catat tidur`\n\n"
                    f"💡 **Tips tidur bayi:**\n"
                    f"• Ciptakan rutinitas tidur yang konsisten\n"
                    f"• Pastikan ruangan nyaman dan gelap\n"
                    f"• Catat pola tidur untuk memahami kebutuhan bayi"
                )
            else:
                reply = f"😴 **Catatan tidur hari ini ({today})**\n\n"
                total_minutes = 0
                
                for i, row in enumerate(sleep_rows, 1):
                    start_time = row[0]
                    end_time = row[1] if row[1] else "berlangsung"
                    duration_mins = row[2] or 0
                    
                    if duration_mins > 0:
                        hours, minutes = divmod(int(duration_mins), 60)
                        duration_text = f"({hours}j {minutes}m)"
                        total_minutes += duration_mins
                    else:
                        duration_text = "(sedang tidur)"
                    
                    reply += f"{i}. {start_time} - {end_time} {duration_text}\n"
                
                # Total for today
                if total_minutes > 0:
                    total_hours, total_mins = divmod(int(total_minutes), 60)
                    reply += f"\n📊 **Total hari ini: {total_hours}j {total_mins}m ({len(sleep_rows)} sesi)**"
                
                # Add recommendations based on total sleep
                if total_minutes > 0:
                    reply += self._get_sleep_recommendations(total_minutes, len(sleep_rows))
                
                reply += f"\n\n💡 Ketik `riwayat tidur` untuk melihat beberapa hari terakhir."
            
            self.app_logger.log_user_action(
                user_id=user,
                action='sleep_view_today',
                success=True,
                details={'sessions_count': len(sleep_rows) if sleep_rows else 0}
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_view_today_sleep'})
            reply = f"❌ Terjadi kesalahan saat mengambil data tidur hari ini. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_view_sleep_history(self, user: str) -> Response:
        """Handle viewing sleep history"""
        resp = MessagingResponse()
        
        try:
            limits = get_tier_limits(user)
            days_limit = limits.get("history_days", 7)
            if days_limit is None:
                days_limit = 30  # Premium users get 30 days
            
            records = get_sleep_records_with_limit(user, limit=None)
            if not records:
                reply = (
                    f"😴 **Belum ada riwayat tidur**\n\n"
                    f"Mulai dengan: `catat tidur`\n\n"
                    f"📊 Dengan mencatat tidur secara rutin, Anda dapat:\n"
                    f"• Memahami pola tidur bayi\n"
                    f"• Mengoptimalkan jadwal tidur\n"
                    f"• Melacak perubahan kebutuhan tidur"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Group by date
            by_date = {}
            for record in records:
                date_str = record['date']
                if isinstance(date_str, str):
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        date_obj = date_str
                else:
                    date_obj = date_str
                
                if date_obj not in by_date:
                    by_date[date_obj] = []
                by_date[date_obj].append(record)
            
            # Limit dates shown
            sorted_dates = sorted(by_date.keys(), reverse=True)[:days_limit]
            
            reply = f"📊 **Riwayat Tidur (maks {days_limit} hari)**\n\n"
            total_sessions = 0
            total_minutes = 0
            
            for date_obj in sorted_dates:
                day_records = by_date[date_obj]
                day_total = sum(r.get('duration_minutes', 0) or 0 for r in day_records)
                hours, minutes = divmod(int(day_total), 60)
                
                # Format date nicely
                if date_obj == datetime.now().date():
                    date_display = "Hari ini"
                elif date_obj == datetime.now().date() - timedelta(days=1):
                    date_display = "Kemarin"
                else:
                    date_display = date_obj.strftime("%d/%m")
                
                reply += f"**{date_display}:**\n"
                for record in day_records:
                    duration = record.get('duration_minutes', 0) or 0
                    h, m = divmod(int(duration), 60)
                    start_time = record.get('start_time', '-')
                    end_time = record.get('end_time', '-')
                    if end_time == '-' or end_time is None:
                        end_time = "berlangsung"
                        duration_text = ""
                    else:
                        duration_text = f" ({h}j {m}m)"
                    reply += f"  • {start_time} - {end_time}{duration_text}\n"
                
                reply += f"  📈 Total: {hours}j {minutes}m ({len(day_records)} sesi)\n\n"
                
                total_sessions += len(day_records)
                total_minutes += day_total
            
            # Overall summary
            if by_date:
                total_hours, total_mins = divmod(int(total_minutes), 60)
                avg_per_day = total_minutes / len(sorted_dates) if sorted_dates else 0
                avg_hours, avg_mins = divmod(int(avg_per_day), 60)
                
                reply += f"📊 **Ringkasan {len(sorted_dates)} hari:**\n"
                reply += f"• Total tidur: {total_hours}j {total_mins}m\n"
                reply += f"• Total sesi: {total_sessions}\n"
                reply += f"• Rata-rata per hari: {avg_hours}j {avg_mins}m\n"
                
                # Add tier info for free users
                if limits.get("history_days"):
                    reply += f"\n💡 **Tier gratis dibatasi {limits['history_days']} hari riwayat**"
                    reply += f"\n💎 Upgrade ke premium untuk riwayat unlimited!"
            
            self.app_logger.log_user_action(
                user_id=user,
                action='sleep_view_history',
                success=True,
                details={
                    'days_shown': len(sorted_dates),
                    'total_sessions': total_sessions,
                    'is_premium': limits.get("sleep_record") is None
                }
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_view_sleep_history'})
            reply = f"❌ Terjadi kesalahan saat mengambil riwayat tidur. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def _complete_sleep_session(self, user: str, sleep_id: int, end_time: str) -> str:
        """Complete a sleep session with enhanced validation and feedback"""
        try:
            # Get the sleep record
            sleep_data = get_sleep_by_id(sleep_id)
            if not sleep_data:
                return "❌ Sesi tidur tidak ditemukan. Mungkin sudah dihapus atau tidak valid."
            
            # Calculate duration with better validation
            try:
                start_datetime = datetime.strptime(f"{sleep_data['date']} {sleep_data['start_time']}", "%Y-%m-%d %H:%M")
                end_datetime = datetime.strptime(f"{sleep_data['date']} {end_time}", "%Y-%m-%d %H:%M")
                
                # Handle sleep across midnight
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                    
                duration_minutes = (end_datetime - start_datetime).total_seconds() / 60
                
                # Enhanced validation
                if duration_minutes < 1:
                    return "❌ Durasi tidur terlalu singkat (kurang dari 1 menit). Periksa waktu mulai dan selesai."
                
                if duration_minutes > 20 * 60:  # More than 20 hours
                    return (
                        f"❌ **Durasi tidur terlalu lama**\n\n"
                        f"Durasi: {int(duration_minutes/60)} jam\n"
                        f"Mulai: {sleep_data['start_time']}\n"
                        f"Selesai: {end_time}\n\n"
                        f"Periksa kembali waktu yang dimasukkan."
                    )
                
                hours, minutes = divmod(int(duration_minutes), 60)
                
                # Update the record
                success = update_sleep_record(sleep_id, end_time, duration_minutes)
                
                if success:
                    # Log successful completion
                    self.app_logger.log_user_action(
                        user_id=user,
                        action='sleep_completed',
                        success=True,
                        details={
                            'sleep_id': sleep_id,
                            'duration_minutes': duration_minutes,
                            'start_time': sleep_data['start_time'],
                            'end_time': end_time
                        }
                    )
                    
                    # Check tier limits after completion
                    limits = get_tier_limits(user)
                    sleep_limit = limits.get("sleep_record")
                    
                    base_message = (
                        f"✅ **Catatan tidur berhasil disimpan!**\n\n"
                        f"📊 **Detail:**\n"
                        f"• Durasi: {hours} jam {minutes} menit\n"
                        f"• Waktu: {sleep_data['start_time']} - {end_time}\n"
                        f"• Tanggal: {sleep_data['date']}"
                    )
                    
                    # Add sleep quality assessment
                    quality_msg = self._assess_sleep_quality(duration_minutes)
                    if quality_msg:
                        base_message += f"\n\n{quality_msg}"
                    
                    if sleep_limit is not None:  # Free user
                        current_count = get_sleep_record_count(user)
                        base_message += f"\n\n📈 **Catatan tidur:** {current_count}/{sleep_limit}"
                        
                        if current_count >= sleep_limit:
                            base_message += (
                                f"\n\n⚠️ **Batas maksimal tercapai!**\n"
                                f"Upgrade ke premium untuk catatan unlimited!"
                            )
                        elif current_count >= sleep_limit * 0.8:
                            base_message += f"\n\n💡 Mendekati batas maksimal. Upgrade ke premium?"
                    
                    return base_message
                else:
                    return "❌ Gagal menyimpan catatan tidur. Silakan coba lagi atau hubungi support."
                    
            except ValueError as e:
                return f"❌ **Format waktu tidak valid:** {str(e)}"
                
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': '_complete_sleep_session'})
            return f"❌ Terjadi kesalahan sistem saat menyimpan catatan tidur. Kode error: {error_id}"
    
    def _assess_sleep_quality(self, duration_minutes: float) -> str:
        """Assess sleep quality based on duration"""
        hours = duration_minutes / 60
        
        if hours < 0.5:
            return "💤 **Tidur sangat singkat** - Mungkin hanya power nap"
        elif hours < 1:
            return "😴 **Tidur singkat** - Good untuk nap time"
        elif hours < 2:
            return "😊 **Tidur sedang** - Durasi nap yang baik"
        elif hours < 4:
            return "😴 **Tidur cukup lama** - Excellent untuk recovery"
        elif hours < 8:
            return "🌙 **Tidur malam yang baik** - Durasi ideal"
        elif hours < 12:
            return "😴 **Tidur panjang** - Sangat baik untuk pertumbuhan"
        else:
            return "🛌 **Tidur sangat panjang** - Pastikan bayi dalam kondisi sehat"
    
    def _get_sleep_recommendations(self, total_minutes: float, session_count: int) -> str:
        """Get sleep recommendations based on daily totals"""
        total_hours = total_minutes / 60
        
        recommendations = "\n\n💡 **Rekomendasi:**\n"
        
        if total_hours < 10:
            recommendations += "• Bayi mungkin perlu tidur lebih banyak\n"
            recommendations += "• Coba tambahkan waktu nap"
        elif total_hours > 18:
            recommendations += "• Total tidur sangat banyak (normal untuk newborn)\n"
            recommendations += "• Monitor pola makan dan pertumbuhan"
        else:
            recommendations += "• Total tidur dalam rentang normal\n"
        
        if session_count > 8:
            recommendations += "• Banyak sesi tidur pendek - normal untuk bayi kecil"
        elif session_count < 3:
            recommendations += "• Sedikit sesi tidur - bayi mulai tidur lebih lama"
        
        return recommendations
    
    def _handle_unknown_sleep_command(self, user: str, message: str) -> Response:
        """Handle unknown sleep commands"""
        resp = MessagingResponse()
        
        self.app_logger.log_user_action(
            user_id=user,
            action='unknown_sleep_command',
            success=False,
            details={'message': message}
        )
        
        reply = (
            f"🤖 Perintah tidak dikenali dalam konteks tidur: '{message[:30]}...'\n\n"
            f"**Perintah tidur yang tersedia:**\n"
            f"• `catat tidur` - Mulai mencatat sesi tidur\n"
            f"• `selesai tidur [HH:MM]` - Selesaikan sesi tidur\n"
            f"• `batal tidur` - Batalkan sesi yang belum selesai\n"
            f"• `lihat tidur` - Lihat catatan hari ini\n"
            f"• `riwayat tidur` - Lihat riwayat beberapa hari\n\n"
            f"**Contoh penggunaan:**\n"
            f"• `selesai tidur 07:30`\n"
            f"• `selesai tidur 19:45`\n\n"
            f"Ketik `help` untuk bantuan lengkap."
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
