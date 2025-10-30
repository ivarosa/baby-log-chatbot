"""
Complete Summary and reports handler
Handles daily summaries, comprehensive reports, and analytics
"""
from datetime import datetime, date, timedelta
from fastapi import BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import (
    get_mpasi_summary, get_milk_intake_summary, get_pumping_summary,
    get_poop_log, get_user_calorie_setting, get_timbang_history
)
from sleep_tracking import get_sleep_summary
from tier_management import get_tier_limits, can_access_feature
import re
import logging

class SummaryHandler:
    """Handle all summary and reporting operations"""
    
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
        
    def handle_summary_commands(self, user: str, message: str) -> Response:
        """Route summary commands to appropriate handlers"""
        
        # Daily summary commands
        if any(cmd in message.lower() for cmd in ["summary today", "ringkasan hari ini", "show summary", "daily summary"]):
            return self.handle_daily_summary(user, message)
        
        # Weekly summary
        elif any(cmd in message.lower() for cmd in ["summary week", "ringkasan minggu", "weekly summary"]):
            return self.handle_weekly_summary(user)
        
        # Monthly summary
        elif any(cmd in message.lower() for cmd in ["summary month", "ringkasan bulan", "monthly summary"]):
            return self.handle_monthly_summary(user)
        
        # Specific date summary
        elif re.match(r"^(summary|ringkasan) \d{4}-\d{2}-\d{2}", message.lower()):
            return self.handle_date_specific_summary(user, message)
        
        # Growth summary
        elif any(cmd in message.lower() for cmd in ["growth summary", "ringkasan tumbuh kembang", "summary pertumbuhan"]):
            return self.handle_growth_summary(user)
        
        # Nutrition summary
        elif any(cmd in message.lower() for cmd in ["nutrition summary", "ringkasan nutrisi", "summary gizi"]):
            return self.handle_nutrition_summary(user)
        
        else:
            return self._handle_unknown_summary_command(user, message)
    
    def handle_daily_summary(self, user: str, message: str) -> Response:
        """Handle daily summary requests"""
        resp = MessagingResponse()
        
        try:
            # Extract date from message
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
            if "today" in message.lower() or "hari ini" in message.lower():
                summary_date = datetime.now().strftime("%Y-%m-%d")
            elif date_match:
                summary_date = date_match.group(0)
            else:
                summary_date = datetime.now().strftime("%Y-%m-%d")
            
            # Get comprehensive daily data
            daily_data = self._get_daily_summary_data(user, summary_date)
            
            # Format comprehensive summary
            reply = self._format_daily_summary(daily_data, summary_date, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='daily_summary_viewed',
                success=True,
                details={
                    'date': summary_date,
                    'has_mpasi': daily_data['mpasi']['count'] > 0,
                    'has_milk': daily_data['milk']['count'] > 0,
                    'has_sleep': daily_data['sleep']['sessions'] > 0
                }
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_daily_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil ringkasan harian. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_weekly_summary(self, user: str) -> Response:
        """Handle weekly summary requests"""
        resp = MessagingResponse()
        
        try:
            # Check if user can access weekly summaries
            if not can_access_feature(user, "weekly_trends"):
                reply = (
                    f"💎 **Fitur Premium: Ringkasan Mingguan**\n\n"
                    f"Ringkasan mingguan tersedia untuk user premium.\n\n"
                    f"**Fitur yang Anda dapatkan:**\n"
                    f"• Analisis pola makan & tidur\n"
                    f"• Grafik pertumbuhan mingguan\n"
                    f"• Rekomendasi nutrisi\n"
                    f"• Perbandingan dengan minggu sebelumnya\n\n"
                    f"Upgrade ke premium untuk akses penuh!"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Calculate date range (last 7 days)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=6)
            
            weekly_data = self._get_weekly_summary_data(user, start_date, end_date)
            reply = self._format_weekly_summary(weekly_data, start_date, end_date, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='weekly_summary_viewed',
                success=True,
                details={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_weekly_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil ringkasan mingguan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_monthly_summary(self, user: str) -> Response:
        """Handle monthly summary requests"""
        resp = MessagingResponse()
        
        try:
            # Check if user can access monthly reports
            if not can_access_feature(user, "monthly_reports"):
                reply = (
                    f"💎 **Fitur Premium: Laporan Bulanan**\n\n"
                    f"Laporan bulanan tersedia untuk user premium.\n\n"
                    f"**Fitur yang Anda dapatkan:**\n"
                    f"• Analisis pertumbuhan bulanan\n"
                    f"• Grafik pola makan & tidur\n"
                    f"• Milestone tracking\n"
                    f"• Export PDF laporan\n"
                    f"• Rekomendasi dokter anak\n\n"
                    f"Upgrade ke premium untuk akses penuh!"
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Calculate current month range
            now = datetime.now()
            start_date = now.replace(day=1).date()
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            end_date = (next_month - timedelta(days=1)).date()
            
            monthly_data = self._get_monthly_summary_data(user, start_date, end_date)
            reply = self._format_monthly_summary(monthly_data, start_date, end_date, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='monthly_summary_viewed',
                success=True,
                details={
                    'month': now.strftime('%Y-%m'),
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_monthly_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil laporan bulanan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_date_specific_summary(self, user: str, message: str) -> Response:
        """Handle summary for specific date"""
        resp = MessagingResponse()
        
        try:
            # Extract date from message
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', message)
            if not date_match:
                reply = "❌ Format tanggal tidak valid. Gunakan: summary YYYY-MM-DD"
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            summary_date = date_match.group(1)
            
            # Validate date
            try:
                datetime.strptime(summary_date, "%Y-%m-%d")
            except ValueError:
                reply = "❌ Tanggal tidak valid. Gunakan format: YYYY-MM-DD (contoh: 2024-01-15)"
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # Get data for specific date
            daily_data = self._get_daily_summary_data(user, summary_date)
            reply = self._format_daily_summary(daily_data, summary_date, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='specific_date_summary_viewed',
                success=True,
                details={'requested_date': summary_date}
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_date_specific_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil ringkasan tanggal. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_growth_summary(self, user: str) -> Response:
        """Handle growth summary requests"""
        resp = MessagingResponse()
        
        try:
            # Get growth data
            growth_records = get_timbang_history(user, limit=10)  # Last 10 records
            
            if not growth_records:
                reply = (
                    f"📈 **Ringkasan Pertumbuhan**\n\n"
                    f"Belum ada data pertumbuhan yang tercatat.\n\n"
                    f"**Mulai tracking pertumbuhan:**\n"
                    f"• `catat timbang` - Catat berat & tinggi\n"
                    f"• `tampilkan anak` - Lihat data anak\n\n"
                    f"💡 Dengan data pertumbuhan rutin, Anda dapat:\n"
                    f"• Memantau perkembangan optimal\n"
                    f"• Mendapatkan rekomendasi nutrisi\n"
                    f"• Melacak milestone pertumbuhan"
                )
            else:
                # Format growth summary
                reply = self._format_growth_summary(growth_records, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='growth_summary_viewed',
                success=True,
                details={'records_count': len(growth_records)}
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_growth_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil ringkasan pertumbuhan. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_nutrition_summary(self, user: str) -> Response:
        """Handle nutrition summary requests"""
        resp = MessagingResponse()
        
        try:
            # Get nutrition data for today
            today = datetime.now().strftime("%Y-%m-%d")
            nutrition_data = self._get_nutrition_summary_data(user, today)
            reply = self._format_nutrition_summary(nutrition_data, today, user)
            
            self.app_logger.log_user_action(
                user_id=user,
                action='nutrition_summary_viewed',
                success=True,
                details={
                    'date': today,
                    'total_calories': nutrition_data['total_calories']
                }
            )
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_nutrition_summary'})
            reply = f"❌ Terjadi kesalahan saat mengambil ringkasan nutrisi. Kode error: {error_id}"
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def _get_daily_summary_data(self, user: str, summary_date: str) -> dict:
        """Get comprehensive daily summary data"""
        try:
            # MPASI data
            mpasi_rows = get_mpasi_summary(user, summary_date, summary_date) or []
            mpasi_count = len(mpasi_rows)
            mpasi_ml = sum([row[2] or 0 for row in mpasi_rows])
            mpasi_calories = sum([row[5] or 0 for row in mpasi_rows])
            
            # Milk data
            milk_rows = get_milk_intake_summary(user, summary_date, summary_date) or []
            milk_total_sessions = sum([r[2] or 0 for r in milk_rows])
            milk_total_ml = sum([r[3] or 0 for r in milk_rows])
            milk_total_calories = sum([r[4] or 0 for r in milk_rows])
            
            # Pumping data
            pump_rows = get_pumping_summary(user, summary_date, summary_date) or []
            pump_sessions = len(pump_rows)
            pump_total = sum([(row[2] or 0) + (row[3] or 0) for row in pump_rows])
            pump_bags = sum([row[4] or 0 for row in pump_rows])
            
            # Sleep data
            sleep_rows = get_sleep_summary(user, summary_date) or []
            sleep_sessions = len(sleep_rows)
            sleep_total_minutes = sum([row[2] or 0 for row in sleep_rows])
            
            # Poop data
            poop_rows = get_poop_log(user, summary_date, summary_date) or []
            poop_count = len(poop_rows)
            
            return {
                'mpasi': {
                    'count': mpasi_count,
                    'total_ml': mpasi_ml,
                    'calories': mpasi_calories,
                    'sessions': mpasi_rows
                },
                'milk': {
                    'count': milk_total_sessions,
                    'total_ml': milk_total_ml,
                    'calories': milk_total_calories,
                    'sessions': milk_rows
                },
                'pumping': {
                    'sessions': pump_sessions,
                    'total_ml': pump_total,
                    'bags': pump_bags
                },
                'sleep': {
                    'sessions': sleep_sessions,
                    'total_minutes': sleep_total_minutes
                },
                'poop': {
                    'count': poop_count
                },
                'total_calories': mpasi_calories + milk_total_calories
            }
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_get_daily_summary_data', 'date': summary_date})
            return self._get_empty_summary_data()
    
    def _get_empty_summary_data(self) -> dict:
        """Return empty summary data structure"""
        return {
            'mpasi': {'count': 0, 'total_ml': 0, 'calories': 0, 'sessions': []},
            'milk': {'count': 0, 'total_ml': 0, 'calories': 0, 'sessions': []},
            'pumping': {'sessions': 0, 'total_ml': 0, 'bags': 0},
            'sleep': {'sessions': 0, 'total_minutes': 0},
            'poop': {'count': 0},
            'total_calories': 0
        }
    
    def _format_daily_summary(self, data: dict, summary_date: str, user: str) -> str:
        """Format daily summary message - OPTIMIZED TO SINGLE MESSAGE"""
        try:
            is_today = summary_date == datetime.now().strftime("%Y-%m-%d")
            date_display = "Hari Ini" if is_today else summary_date
            
            # OPTIMIZED: Single consolidated message instead of multiple sections
            sleep_hours, sleep_mins = divmod(int(data['sleep']['total_minutes']), 60)
            sleep_str = f"{sleep_hours}j{sleep_mins}m" if data['sleep']['sessions'] > 0 else "-"
            
            # Build everything in ONE message
            lines = [f"📊 Ringkasan {date_display}\n"]
            
            # Core stats in compact format
            lines.append(
                f"🍽️ MPASI: {data['mpasi']['count']}x, {data['mpasi']['total_ml']}ml\n"
                f"🍼 Susu: {data['milk']['count']}x, {data['milk']['total_ml']}ml\n"
                f"🔥 Kalori: {data['total_calories']:.0f} kkal\n"
                f"😴 Tidur: {data['sleep']['sessions']}x, {sleep_str}\n"
                f"💩 BAB: {data['poop']['count']}x"
            )
            
            # OPTIMIZED: Only add recommendations if critical
            if data['total_calories'] < 300:
                lines.append("\n\n⚠️ Kalori rendah - tambah asupan")
            elif data['total_calories'] > 1000:
                lines.append("\n\n✅ Asupan kalori tinggi")
            
            # OPTIMIZED: Only add action prompts if needed and TODAY
            if is_today:
                actions = []
                if data['mpasi']['count'] == 0:
                    actions.append("'catat mpasi'")
                if data['milk']['count'] == 0:
                    actions.append("'catat susu'")
                
                if actions:
                    lines.append(f"\n\n💡 Belum: {', '.join(actions)}")
            
            return "\n".join(lines)
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_format_daily_summary'})
            return f"❌ Error summary untuk {summary_date}"  # OPTIMIZED: Shorter
    
    def _generate_daily_recommendations(self, data: dict, is_today: bool) -> str:
        """Generate recommendations based on daily data"""
        recommendations = []
        
        # Feeding recommendations
        if data['total_calories'] < 300:
            recommendations.append("Pertimbangkan tambah asupan kalori")
        elif data['total_calories'] > 1000:
            recommendations.append("Asupan kalori tinggi - monitor pertumbuhan")
        
        # Sleep recommendations
        sleep_hours = data['sleep']['total_minutes'] / 60
        if sleep_hours < 8:
            recommendations.append("Bayi mungkin perlu tidur lebih banyak")
        elif sleep_hours > 18:
            recommendations.append("Total tidur sangat banyak (normal untuk newborn)")
        
        # MPASI recommendations
        if data['mpasi']['count'] == 0 and is_today:
            recommendations.append("Belum ada MPASI hari ini")
        elif data['mpasi']['count'] > 6:
            recommendations.append("Frekuensi MPASI tinggi - sesuaikan porsi")
        
        # Milk recommendations
        if data['milk']['count'] == 0 and is_today:
            recommendations.append("Belum ada catatan minum susu hari ini")
        
        # Health recommendations
        if data['poop']['count'] == 0 and is_today:
            recommendations.append("Belum BAB hari ini - monitor hidrasi")
        elif data['poop']['count'] > 8:
            recommendations.append("Frekuensi BAB tinggi - konsultasi dokter jika perlu")
        
        return "\n".join([f"  • {rec}" for rec in recommendations]) if recommendations else ""
    
    def _get_weekly_summary_data(self, user: str, start_date: date, end_date: date) -> dict:
        """Get weekly summary data"""
        try:
            # Aggregate data for the week
            weekly_data = {
                'date_range': f"{start_date.isoformat()} - {end_date.isoformat()}",
                'daily_summaries': []
            }
            
            # Get data for each day
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_data = self._get_daily_summary_data(user, date_str)
                daily_data['date'] = date_str
                weekly_data['daily_summaries'].append(daily_data)
                current_date += timedelta(days=1)
            
            return weekly_data
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_get_weekly_summary_data'})
            return {'date_range': '', 'daily_summaries': []}
    
    def _format_weekly_summary(self, data: dict, start_date: date, end_date: date, user: str) -> str:
        """Format weekly summary - OPTIMIZED"""
        try:
            if not data['daily_summaries']:
                return f"📊 Belum ada data minggu ini"  # OPTIMIZED: Much shorter
            
            # Calculate weekly totals
            total_mpasi = sum([d['mpasi']['count'] for d in data['daily_summaries']])
            total_milk = sum([d['milk']['count'] for d in data['daily_summaries']])
            total_calories = sum([d['total_calories'] for d in data['daily_summaries']])
            total_sleep = sum([d['sleep']['total_minutes'] for d in data['daily_summaries']]) / 60
            
            # OPTIMIZED: Single consolidated message
            return (
                f"📊 Ringkasan Minggu ({start_date.strftime('%d/%m')}-{end_date.strftime('%d/%m')})\n\n"
                f"• MPASI: {total_mpasi} sesi\n"
                f"• Susu: {total_milk} sesi\n"
                f"• Kalori: {total_calories:.0f} kkal\n"
                f"• Tidur: {total_sleep:.0f} jam\n"
                f"• Rata-rata: {total_calories/7:.0f} kkal/hari\n\n"
                f"💎 Upgrade untuk grafik detail"
            )
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_format_weekly_summary'})
            return f"❌ Error weekly summary"  # OPTIMIZED: Shorter
    
    def _get_monthly_summary_data(self, user: str, start_date: date, end_date: date) -> dict:
        """Get monthly summary data"""
        try:
            monthly_data = {
                'date_range': f"{start_date.isoformat()} - {end_date.isoformat()}",
                'month_name': start_date.strftime('%B %Y'),
                'weekly_summaries': []
            }
            
            # Group by weeks
            current_date = start_date
            while current_date <= end_date:
                week_end = min(current_date + timedelta(days=6), end_date)
                week_data = self._get_weekly_summary_data(user, current_date, week_end)
                weekly_data = {
                    'week_start': current_date.isoformat(),
                    'week_end': week_end.isoformat(),
                    'data': week_data
                }
                monthly_data['weekly_summaries'].append(weekly_data)
                current_date = week_end + timedelta(days=1)
            
            return monthly_data
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_get_monthly_summary_data'})
            return {'date_range': '', 'month_name': '', 'weekly_summaries': []}
    
    def _format_monthly_summary(self, data: dict, start_date: date, end_date: date, user: str) -> str:
        """Format monthly summary message"""
        try:
            if not data['weekly_summaries']:
                return f"📊 **Laporan Bulanan**\n\nBelum ada data untuk {data['month_name']}."
            
            # Calculate monthly totals
            total_days = (end_date - start_date).days + 1
            all_daily_data = []
            for week in data['weekly_summaries']:
                all_daily_data.extend(week['data']['daily_summaries'])
            
            total_mpasi = sum([d['mpasi']['count'] for d in all_daily_data])
            total_milk = sum([d['milk']['count'] for d in all_daily_data])
            total_calories = sum([d['total_calories'] for d in all_daily_data])
            total_pumping = sum([d['pumping']['sessions'] for d in all_daily_data])
            
            # Get growth data for the month
            growth_records = get_timbang_history(user, limit=None)
            month_growth = [r for r in growth_records if start_date <= r[0] <= end_date] if growth_records else []
            
            lines = [
                f"📊 **Laporan Bulanan - {data['month_name']}**\n",
                f"📈 **Ringkasan {total_days} Hari:**",
                f"• Total MPASI: {total_mpasi} sesi",
                f"• Total susu: {total_milk} sesi",
                f"• Total kalori: {total_calories:.0f} kkal",
                f"• Total pumping: {total_pumping} sesi\n",
                
                f"📊 **Rata-rata Harian:**",
                f"• Kalori: {total_calories/total_days:.0f} kkal/hari",
                f"• MPASI: {total_mpasi/total_days:.1f} sesi/hari",
                f"• Susu: {total_milk/total_days:.1f} sesi/hari\n"
            ]
            
            # Add growth information if available
            if month_growth:
                latest_growth = month_growth[0]
                lines.extend([
                    f"📏 **Pertumbuhan Bulan Ini:**",
                    f"• Catatan timbang: {len(month_growth)}x",
                    f"• Berat terbaru: {latest_growth[2]} kg",
                    f"• Tinggi terbaru: {latest_growth[1]} cm\n"
                ])
            
            lines.extend([
                f"💎 **Fitur Premium Tersedia:**",
                f"• Grafik pertumbuhan detail",
                f"• Analisis pola makan & tidur",
                f"• Export PDF laporan lengkap",
                f"• Rekomendasi nutrisi personal"
            ])
            
            return "\n".join(lines)
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_format_monthly_summary'})
            return f"❌ Error formatting monthly summary"
    
    def _get_nutrition_summary_data(self, user: str, date: str) -> dict:
        """Get nutrition-specific summary data"""
        try:
            # Get MPASI calories
            mpasi_rows = get_mpasi_summary(user, date, date) or []
            mpasi_calories = sum([row[5] or 0 for row in mpasi_rows])
            
            # Get milk calories with ASI calculation
            milk_rows = get_milk_intake_summary(user, date, date) or []
            kcal_settings = get_user_calorie_setting(user)
            
            asi_ml = 0
            sufor_calories = 0
            
            for r in milk_rows:
                milk_type = r[0] if len(r) > 0 else 'unknown'
                volume_ml = r[3] if len(r) > 3 else 0
                sufor_cal = r[4] if len(r) > 4 else 0
                
                if milk_type == 'asi':
                    asi_ml += volume_ml or 0
                elif milk_type == 'sufor':
                    sufor_calories += sufor_cal or 0
            
            asi_calories = asi_ml * kcal_settings.get('asi', 0.67)
            total_milk_calories = asi_calories + sufor_calories
            
            return {
                'mpasi_calories': mpasi_calories,
                'asi_ml': asi_ml,
                'asi_calories': asi_calories,
                'sufor_calories': sufor_calories,
                'total_milk_calories': total_milk_calories,
                'total_calories': mpasi_calories + total_milk_calories,
                'mpasi_sessions': len(mpasi_rows),
                'milk_sessions': sum([r[2] or 0 for r in milk_rows])
            }
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_get_nutrition_summary_data'})
            return {
                'mpasi_calories': 0, 'asi_ml': 0, 'asi_calories': 0,
                'sufor_calories': 0, 'total_milk_calories': 0,
                'total_calories': 0, 'mpasi_sessions': 0, 'milk_sessions': 0
            }
    
    def _format_nutrition_summary(self, data: dict, date: str, user: str) -> str:
        """Format nutrition summary - OPTIMIZED"""
        try:
            is_today = date == datetime.now().strftime("%Y-%m-%d")
            date_display = "Hari Ini" if is_today else date
            
            if data['total_calories'] == 0:
                return f"🔥 Belum ada catatan nutrisi.\n\nKetik 'catat mpasi' atau 'catat susu'"  # OPTIMIZED: Shorter
            
            # OPTIMIZED: Compact format
            mpasi_pct = (data['mpasi_calories'] / data['total_calories'] * 100) if data['total_calories'] > 0 else 0
            milk_pct = (data['total_milk_calories'] / data['total_calories'] * 100) if data['total_calories'] > 0 else 0
            
            return (
                f"🔥 Nutrisi {date_display}\n\n"
                f"Total: {data['total_calories']:.0f} kkal\n\n"
                f"• MPASI: {data['mpasi_calories']:.0f} ({mpasi_pct:.0f}%)\n"
                f"• Susu: {data['total_milk_calories']:.0f} ({milk_pct:.0f}%)\n"
                f"  - ASI: {data['asi_ml']}ml\n"
                f"  - Sufor: {data['sufor_calories']:.0f} kkal"
            )
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_format_nutrition_summary'})
            return f"❌ Error nutrition summary"  # OPTIMIZED: Shorter
    
    def _assess_nutrition(self, data: dict, is_today: bool) -> str:
        """Assess nutrition based on intake data"""
        assessments = []
        
        total_cal = data['total_calories']
        
        # Calorie assessment (rough guidelines)
        if total_cal < 200:
            assessments.append("Asupan kalori rendah - pertimbangkan tambah porsi")
        elif total_cal < 400:
            assessments.append("Asupan kalori dalam rentang normal-rendah")
        elif total_cal < 800:
            assessments.append("Asupan kalori dalam rentang normal")
        elif total_cal < 1200:
            assessments.append("Asupan kalori tinggi - baik untuk pertumbuhan")
        else:
            assessments.append("Asupan kalori sangat tinggi - monitor berat badan")
        
        # Balance assessment
        mpasi_pct = (data['mpasi_calories'] / total_cal * 100) if total_cal > 0 else 0
        if mpasi_pct > 70:
            assessments.append("Dominasi MPASI - pastikan cukup cairan")
        elif mpasi_pct < 20 and data['mpasi_sessions'] > 0:
            assessments.append("MPASI porsi kecil - pertimbangkan variasi makanan")
        
        # Session frequency
        if data['milk_sessions'] > 12:
            assessments.append("Frekuensi minum tinggi - normal untuk bayi kecil")
        elif data['milk_sessions'] < 6 and is_today:
            assessments.append("Frekuensi minum rendah - monitor hidrasi")
        
        return "\n".join([f"  • {assess}" for assess in assessments]) if assessments else ""
    
    def _format_growth_summary(self, growth_records: list, user: str) -> str:
        """Format growth summary - OPTIMIZED"""
        try:
            latest_record = growth_records[0] if growth_records else None
            
            if not latest_record:
                return "📈 Belum ada data pertumbuhan.\n\nKetik 'catat timbang'"  # OPTIMIZED: Shorter
            
            # Extract data
            if isinstance(latest_record, dict):
                date_val = latest_record.get('date', '-')
                height = latest_record.get('height_cm', 0)
                weight = latest_record.get('weight_kg', 0)
                head = latest_record.get('head_circum_cm', 0)
            else:
                date_val = latest_record[0] if len(latest_record) > 0 else '-'
                height = latest_record[1] if len(latest_record) > 1 else 0
                weight = latest_record[2] if len(latest_record) > 2 else 0
                head = latest_record[3] if len(latest_record) > 3 else 0
            
            # OPTIMIZED: Compact format
            reply = (
                f"📈 Data Pertumbuhan\n\n"
                f"Terbaru ({date_val}):\n"
                f"• {height}cm, {weight}kg\n"
                f"• Lingkar kepala: {head}cm\n"
            )
            
            # Show trend if available
            if len(growth_records) > 1:
                prev = growth_records[1]
                if isinstance(prev, dict):
                    prev_weight = prev.get('weight_kg', 0)
                    prev_height = prev.get('height_cm', 0)
                else:
                    prev_weight = prev[2] if len(prev) > 2 else 0
                    prev_height = prev[1] if len(prev) > 1 else 0
                
                w_diff = weight - prev_weight
                h_diff = height - prev_height
                
                reply += f"\nTren:\n• Berat: {w_diff:+.1f}kg\n• Tinggi: {h_diff:+.1f}cm"
            
            # OPTIMIZED: Show only 3 recent records
            if len(growth_records) > 1:
                reply += "\n\nRiwayat:"
                for i, r in enumerate(growth_records[:3]):
                    if isinstance(r, dict):
                        r_date = r.get('date', '-')
                        r_weight = r.get('weight_kg', 0)
                        r_height = r.get('height_cm', 0)
                    else:
                        r_date = r[0]
                        r_weight = r[2] if len(r) > 2 else 0
                        r_height = r[1] if len(r) > 1 else 0
                    
                    reply += f"\n{i+1}. {r_date}: {r_weight}kg, {r_height}cm"
                
                if len(growth_records) > 3:
                    reply += f"\n...+{len(growth_records)-3} lagi"
            
            return reply
            
        except Exception as e:
            self.app_logger.log_error(e, context={'function': '_format_growth_summary'})
            return f"❌ Error growth summary"  # OPTIMIZED: Shorter
    
    def _handle_unknown_summary_command(self, user: str, message: str) -> Response:
        """Handle unknown summary commands - OPTIMIZED"""
        resp = MessagingResponse()
        
        # OPTIMIZED: Much shorter help text
        reply = (
            f"❓ Perintah tidak dikenali\n\n"
            f"Coba:\n"
            f"• 'ringkasan hari ini'\n"
            f"• 'growth summary'\n"
            f"• 'nutrition summary'\n\n"
            f"Ketik 'help' untuk lengkap"
        )
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
