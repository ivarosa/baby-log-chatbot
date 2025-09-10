# chart_generator.py
"""
Chart and PDF generation utilities
Handles MPASI/milk charts and PDF report generation
"""
import io
from datetime import datetime, timedelta, date
from fastapi.responses import StreamingResponse
from database.operations import get_mpasi_summary, get_milk_intake_summary, get_user_calorie_setting
from utils.logging_config import get_app_logger
import logging

# Import chart generation modules
try:
    from mpasi_milk_chart import generate_mpasi_milk_chart
    from generate_report import generate_pdf_report
    CHART_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Chart modules not available: {e}")
    CHART_MODULES_AVAILABLE = False

app_logger = get_app_logger()

def normalize_user_phone(user_phone: str) -> str:
    """Normalize user phone number for consistent processing"""
    if user_phone.startswith("whatsapp:"):
        return user_phone
    elif user_phone.startswith("p:"):
        return user_phone
    else:
        # Default to 'whatsapp:'
        return "whatsapp:" + user_phone

def get_mpasi_milk_data(user_phone: str) -> list:
    """
    Get aggregated MPASI and milk data for chart generation
    Returns 7 days of data in the format expected by chart generator
    """
    try:
        user_phone = normalize_user_phone(user_phone)
        
        # Get ASI kcal value for this user (default 0.67 if not found)
        try:
            user_kcal = get_user_calorie_setting(user_phone)
            asi_kcal = user_kcal.get("asi", 0.67)
        except Exception as e:
            app_logger.log_error(e, user_id=user_phone, context={'function': 'get_calorie_setting'})
            asi_kcal = 0.67

        today = date.today()
        days = [(today - timedelta(days=i)).isoformat() for i in reversed(range(7))]
        data = []
        
        for d in days:
            # Aggregate MPASI for this day
            try:
                mpasi_rows = get_mpasi_summary(user_phone, d, d) or []
                mpasi_ml = sum([(row[2] or 0) for row in mpasi_rows])
                mpasi_kcal = sum([(row[5] or 0) for row in mpasi_rows])
            except Exception as e:
                app_logger.log_error(e, user_id=user_phone, context={'function': 'get_mpasi_data', 'date': d})
                mpasi_ml = 0
                mpasi_kcal = 0

            # Aggregate Milk for this day - separate ASI and Sufor
            try:
                milk_rows = get_milk_intake_summary(user_phone, d, d) or []
                milk_ml_asi = 0
                milk_kcal_asi = 0
                milk_ml_sufor = 0
                milk_kcal_sufor = 0

                for row in milk_rows:
                    # row format: [milk_type, asi_method, COUNT(*), SUM(volume_ml), SUM(sufor_calorie)]
                    if len(row) >= 5:
                        milk_type = row[0]
                        volume_ml = row[3] or 0
                        sufor_calorie = row[4] or 0
                        
                        if milk_type == "asi":
                            milk_ml_asi += volume_ml
                            milk_kcal_asi += volume_ml * asi_kcal
                        elif milk_type == "sufor":
                            milk_ml_sufor += volume_ml
                            milk_kcal_sufor += sufor_calorie
            except Exception as e:
                app_logger.log_error(e, user_id=user_phone, context={'function': 'get_milk_data', 'date': d})
                milk_ml_asi = milk_kcal_asi = milk_ml_sufor = milk_kcal_sufor = 0

            milk_ml = milk_ml_asi + milk_ml_sufor
            milk_kcal = milk_kcal_asi + milk_kcal_sufor

            data.append({
                "date": d,
                "mpasi_ml": mpasi_ml,
                "mpasi_kcal": mpasi_kcal,
                "milk_ml": milk_ml,
                "milk_kcal": milk_kcal,
                "milk_ml_asi": milk_ml_asi,
                "milk_kcal_asi": milk_kcal_asi,
                "milk_ml_sufor": milk_ml_sufor,
                "milk_kcal_sufor": milk_kcal_sufor,
            })
        
        app_logger.log_user_action(
            user_id=user_phone,
            action='chart_data_generated',
            success=True,
            details={
                'days_count': len(data),
                'total_mpasi_ml': sum(d['mpasi_ml'] for d in data),
                'total_milk_ml': sum(d['milk_ml'] for d in data)
            }
        )
        
        return data
        
    except Exception as e:
        app_logger.log_error(e, user_id=user_phone, context={'function': 'get_mpasi_milk_data'})
        # Return empty data structure
        return [
            {
                "date": (today - timedelta(days=i)).isoformat(),
                "mpasi_ml": 0, "mpasi_kcal": 0,
                "milk_ml": 0, "milk_kcal": 0,
                "milk_ml_asi": 0, "milk_kcal_asi": 0,
                "milk_ml_sufor": 0, "milk_kcal_sufor": 0,
            }
            for i in reversed(range(7))
        ]

async def generate_chart_response(user_phone: str) -> StreamingResponse:
    """
    Generate chart response for MPASI & milk intake
    Returns PNG chart as streaming response
    """
    try:
        if not CHART_MODULES_AVAILABLE:
            # Return error response if chart modules not available
            error_message = "Chart generation modules not available. Please install matplotlib."
            app_logger.log_error(
                Exception(error_message), 
                user_id=user_phone, 
                context={'function': 'generate_chart_response'}
            )
            return StreamingResponse(
                io.BytesIO(error_message.encode()), 
                media_type='text/plain'
            )
        
        user_phone = normalize_user_phone(user_phone)
        
        # Log chart generation start
        app_logger.performance.log_request(
            user_id=user_phone,
            action='chart_generation_start',
            duration_ms=0,
            success=True
        )
        
        start_time = datetime.now()
        
        # Get aggregated data
        data = get_mpasi_milk_data(user_phone)
        
        # Generate chart
        chart_buf = generate_mpasi_milk_chart(data, user_phone)
        
        # Log performance
        duration = (datetime.now() - start_time).total_seconds() * 1000
        app_logger.performance.log_request(
            user_id=user_phone,
            action='chart_generation_completed',
            duration_ms=duration,
            success=True,
            extra_data={'data_points': len(data)}
        )
        
        # Return as streaming response
        chart_buf.seek(0)
        return StreamingResponse(chart_buf, media_type='image/png')
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000 if 'start_time' in locals() else 0
        app_logger.performance.log_request(
            user_id=user_phone,
            action='chart_generation_failed',
            duration_ms=duration,
            success=False,
            extra_data={'error_type': type(e).__name__}
        )
        
        error_id = app_logger.log_error(e, user_id=user_phone, context={'function': 'generate_chart_response'})
        
        # Return error as text response
        error_message = f"Chart generation failed. Error ID: {error_id}"
        return StreamingResponse(
            io.BytesIO(error_message.encode()), 
            media_type='text/plain'
        )

async def generate_pdf_response(user_phone: str) -> StreamingResponse:
    """
    Generate PDF report response for MPASI & milk intake
    Returns PDF report as streaming response
    """
    try:
        if not CHART_MODULES_AVAILABLE:
            # Return error response if modules not available
            error_message = "PDF generation modules not available. Please install reportlab and matplotlib."
            app_logger.log_error(
                Exception(error_message), 
                user_id=user_phone, 
                context={'function': 'generate_pdf_response'}
            )
            return StreamingResponse(
                io.BytesIO(error_message.encode()), 
                media_type='text/plain'
            )
        
        user_phone = normalize_user_phone(user_phone)
        
        # Check if user can access PDF reports
        from tier_management import can_access_feature
        if not can_access_feature(user_phone, "pdf_reports"):
            error_message = (
                "PDF reports are a premium feature. "
                "Upgrade to premium to access comprehensive PDF reports with charts and analytics."
            )
            app_logger.log_user_action(
                user_id=user_phone,
                action='pdf_generation_blocked',
                success=False,
                details={'reason': 'premium_feature_required'}
            )
            return StreamingResponse(
                io.BytesIO(error_message.encode()), 
                media_type='text/plain'
            )
        
        # Log PDF generation start
        app_logger.performance.log_request(
            user_id=user_phone,
            action='pdf_generation_start',
            duration_ms=0,
            success=True
        )
        
        start_time = datetime.now()
        
        # Get aggregated data
        data = get_mpasi_milk_data(user_phone)
        
        # Generate chart first
        chart_buf = generate_mpasi_milk_chart(data, user_phone)
        
        # Generate PDF report
        pdf_buf = generate_pdf_report(data, chart_buf, user_phone)
        
        # Log performance
        duration = (datetime.now() - start_time).total_seconds() * 1000
        app_logger.performance.log_request(
            user_id=user_phone,
            action='pdf_generation_completed',
            duration_ms=duration,
            success=True,
            extra_data={
                'data_points': len(data),
                'has_chart': bool(chart_buf),
                'pdf_size_bytes': pdf_buf.getbuffer().nbytes if hasattr(pdf_buf, 'getbuffer') else 0
            }
        )
        
        # Return as downloadable PDF
        pdf_buf.seek(0)
        return StreamingResponse(
            pdf_buf,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename=baby_report_{user_phone.replace(':', '_')}.pdf"
            }
        )
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000 if 'start_time' in locals() else 0
        app_logger.performance.log_request(
            user_id=user_phone,
            action='pdf_generation_failed',
            duration_ms=duration,
            success=False,
            extra_data={'error_type': type(e).__name__}
        )
        
        error_id = app_logger.log_error(e, user_id=user_phone, context={'function': 'generate_pdf_response'})
        
        # Return error as text response
        error_message = f"PDF generation failed. Error ID: {error_id}"
        return StreamingResponse(
            io.BytesIO(error_message.encode()), 
            media_type='text/plain'
        )

def validate_chart_data(data: list) -> tuple[bool, str]:
    """
    Validate chart data before generation
    Returns (is_valid, error_message)
    """
    try:
        if not data:
            return False, "No data available for chart generation"
        
        if not isinstance(data, list):
            return False, "Data must be a list"
        
        if len(data) == 0:
            return False, "Data list is empty"
        
        # Check required fields in data
        required_fields = ['date', 'mpasi_ml', 'mpasi_kcal', 'milk_ml', 'milk_kcal']
        for item in data:
            if not isinstance(item, dict):
                return False, "Data items must be dictionaries"
            
            for field in required_fields:
                if field not in item:
                    return False, f"Missing required field: {field}"
                
                # Validate numeric fields
                if field != 'date':
                    value = item[field]
                    if not isinstance(value, (int, float)) or value < 0:
                        return False, f"Invalid value for {field}: {value}"
        
        return True, ""
        
    except Exception as e:
        return False, f"Data validation error: {str(e)}"

def generate_summary_statistics(data: list) -> dict:
    """
    Generate summary statistics from chart data
    Used for PDF reports and analytics
    """
    try:
        if not data:
            return {}
        
        stats = {
            'total_days': len(data),
            'total_mpasi_ml': sum(d.get('mpasi_ml', 0) for d in data),
            'total_mpasi_kcal': sum(d.get('mpasi_kcal', 0) for d in data),
            'total_milk_ml': sum(d.get('milk_ml', 0) for d in data),
            'total_milk_kcal': sum(d.get('milk_kcal', 0) for d in data),
            'total_calories': sum(d.get('mpasi_kcal', 0) + d.get('milk_kcal', 0) for d in data),
            'avg_mpasi_per_day': 0,
            'avg_milk_per_day': 0,
            'avg_calories_per_day': 0,
            'days_with_mpasi': 0,
            'days_with_milk': 0
        }
        
        # Calculate averages
        if stats['total_days'] > 0:
            stats['avg_mpasi_per_day'] = stats['total_mpasi_ml'] / stats['total_days']
            stats['avg_milk_per_day'] = stats['total_milk_ml'] / stats['total_days']
            stats['avg_calories_per_day'] = stats['total_calories'] / stats['total_days']
        
        # Count active days
        stats['days_with_mpasi'] = sum(1 for d in data if d.get('mpasi_ml', 0) > 0)
        stats['days_with_milk'] = sum(1 for d in data if d.get('milk_ml', 0) > 0)
        
        # Calculate trends (simple linear trend)
        if len(data) >= 2:
            # Simple trend calculation for calories
            first_half = data[:len(data)//2]
            second_half = data[len(data)//2:]
            
            first_avg = sum(d.get('mpasi_kcal', 0) + d.get('milk_kcal', 0) for d in first_half) / len(first_half) if first_half else 0
            second_avg = sum(d.get('mpasi_kcal', 0) + d.get('milk_kcal', 0) for d in second_half) / len(second_half) if second_half else 0
            
            stats['calorie_trend'] = 'increasing' if second_avg > first_avg else 'decreasing' if second_avg < first_avg else 'stable'
            stats['trend_magnitude'] = abs(second_avg - first_avg)
        else:
            stats['calorie_trend'] = 'insufficient_data'
            stats['trend_magnitude'] = 0
        
        return stats
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'generate_summary_statistics'})
        return {}

def format_chart_url(user_phone: str, chart_type: str = 'mpasi-milk') -> str:
    """
    Format chart URL for sharing or embedding
    """
    try:
        normalized_phone = normalize_user_phone(user_phone)
        # Remove 'whatsapp:' prefix for URL
        phone_for_url = normalized_phone.replace('whatsapp:', '').replace('+', '%2B')
        
        base_url = "https://your-domain.com"  # Replace with actual domain
        
        if chart_type == 'mpasi-milk':
            return f"{base_url}/mpasi-milk-graph/{phone_for_url}"
        elif chart_type == 'pdf-report':
            return f"{base_url}/report-mpasi-milk/{phone_for_url}"
        else:
            return f"{base_url}/charts/{chart_type}/{phone_for_url}"
            
    except Exception as e:
        app_logger.log_error(e, context={'function': 'format_chart_url'})
        return ""

def get_chart_sharing_message(user_phone: str) -> str:
    """
    Generate sharing message with chart links
    """
    try:
        chart_url = format_chart_url(user_phone, 'mpasi-milk')
        pdf_url = format_chart_url(user_phone, 'pdf-report')
        
        message = (
            f"📊 **Grafik MPASI & Susu Bayi**\n\n"
            f"🔗 **Lihat grafik:** {chart_url}\n"
            f"📄 **Download PDF:** {pdf_url}\n\n"
            f"💡 Grafik menampilkan data 7 hari terakhir untuk:\n"
            f"• Volume MPASI (ml)\n"
            f"• Volume susu/ASI (ml)\n"
            f"• Estimasi kalori\n\n"
            f"📱 Bagikan link ini dengan pasangan atau dokter anak."
        )
        
        return message
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'get_chart_sharing_message'})
        return "❌ Tidak dapat membuat pesan berbagi grafik."

def health_check_chart_system() -> dict:
    """
    Health check for chart generation system
    """
    status = {
        'chart_modules_available': CHART_MODULES_AVAILABLE,
        'matplotlib_available': False,
        'reportlab_available': False,
        'errors': []
    }
    
    try:
        import matplotlib
        status['matplotlib_available'] = True
        status['matplotlib_version'] = matplotlib.__version__
    except ImportError as e:
        status['errors'].append(f"Matplotlib not available: {e}")
    
    try:
        import reportlab
        status['reportlab_available'] = True
        status['reportlab_version'] = reportlab.Version
    except ImportError as e:
        status['errors'].append(f"ReportLab not available: {e}")
    
    # Test data generation
    try:
        test_data = get_mpasi_milk_data("whatsapp:+1234567890")
        status['data_generation_test'] = len(test_data) > 0
    except Exception as e:
        status['data_generation_test'] = False
        status['errors'].append(f"Data generation test failed: {e}")
    
    status['overall_status'] = 'healthy' if len(status['errors']) == 0 else 'degraded'
    
    return status

# Chart configuration constants
CHART_CONFIG = {
    'figure_size': (8, 6),
    'dpi': 100,
    'font_size': 10,
    'title_font_size': 14,
    'colors': {
        'mpasi_ml': '#74b9ff',
        'milk_ml': '#fdcb6e', 
        'mpasi_kcal': '#0984e3',
        'milk_kcal': '#e17055'
    },
    'line_styles': {
        'mpasi_kcal': '--',
        'milk_kcal': '-.'
    },
    'markers': {
        'mpasi_kcal': 'o',
        'milk_kcal': 's'
    }
}

# PDF configuration constants
PDF_CONFIG = {
    'page_size': 'letter',
    'margins': {
        'top': 50,
        'bottom': 50,
        'left': 50,
        'right': 50
    },
    'font_sizes': {
        'title': 16,
        'heading': 14,
        'body': 10,
        'small': 8
    },
    'colors': {
        'title': '#2d3436',
        'heading': '#636e72',
        'body': '#2d3436'
    }
}
