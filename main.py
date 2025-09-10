# main.py
"""
Fixed main application file for baby tracking chatbot
Resolves import errors and circular dependencies
"""
import os
import sys
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from twilio.twiml.messaging_response import MessagingResponse

# Initialize logging first
from utils.logging_config import setup_logging, get_app_logger
app_logger = setup_logging()

# Initialize database pool
from database_pool import DatabasePool
db_pool = DatabasePool()

# Core modules
from session_manager import SessionManager
from error_handler import WebhookErrorHandler
from constants import WELCOME_MESSAGE, HELP_MESSAGE, PANDUAN_MESSAGE

# Initialize session manager
session_manager = SessionManager(timeout_minutes=30)

# Initialize FastAPI app
app = FastAPI(
    title="Baby Log WhatsApp Chatbot",
    version="2.0.0",
    description="Modular baby tracking chatbot with comprehensive logging"
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        # Log successful request
        app_logger.performance.log_request(
            user_id='system',
            action=f"{request.method} {request.url.path}",
            duration_ms=duration,
            success=True
        )
        
        return response
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        error_id = app_logger.log_error(e, context={'path': request.url.path})
        
        app_logger.performance.log_request(
            user_id='system',
            action=f"{request.method} {request.url.path}",
            duration_ms=duration,
            success=False,
            extra_data={'error_id': error_id}
        )
        
        raise

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection
        with db_pool.get_connection() as conn:
            pass
        
        # Test session manager
        session_stats = session_manager.get_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "sessions": session_stats["total_sessions"],
            "version": "2.0.0"
        }
    except Exception as e:
        app_logger.log_error(e, context={'function': 'health_check'})
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/admin/stats")
async def get_application_stats():
    """Get application statistics"""
    try:
        session_stats = session_manager.get_stats()
        db_stats = db_pool.get_stats()
        
        return {
            "sessions": session_stats,
            "database": db_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        app_logger.log_error(e, context={'function': 'get_stats'})
        return {"error": str(e)}

@app.get("/mpasi-milk-graph/{user_phone}")
async def mpasi_milk_graph(user_phone: str):
    """Generate MPASI & milk intake chart"""
    try:
        app_logger.log_user_action(user_phone, 'chart_request')
        from chart_generator import generate_chart_response
        return await generate_chart_response(user_phone)
    except Exception as e:
        error_id = app_logger.log_error(e, user_id=user_phone, context={'function': 'chart_generation'})
        return {"error": f"Chart generation failed. Error ID: {error_id}"}

@app.get("/report-mpasi-milk/{user_phone}")
async def report_mpasi_milk(user_phone: str):
    """Generate PDF report"""
    try:
        app_logger.log_user_action(user_phone, 'pdf_report_request')
        from chart_generator import generate_pdf_response
        return await generate_pdf_response(user_phone)
    except Exception as e:
        error_id = app_logger.log_error(e, user_id=user_phone, context={'function': 'pdf_generation'})
        return {"error": f"PDF generation failed. Error ID: {error_id}"}

@app.post("/webhook")
@WebhookErrorHandler.handle_webhook_error
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook handler"""
    form = await request.form()
    user = form.get("From")
    message = form.get("Body", "").strip()
    
    # Log the incoming message
    app_logger.log_user_action(user, f'message_received: {message[:50]}')
    
    session = session_manager.get_session(user)
    resp = MessagingResponse()
    
    try:
        # Universal commands (no session state)
        if message.lower() in ["batal", "cancel"]:
            return handle_cancel_command(user, resp)
        
        # Welcome commands
        if message.lower() in ["start", "mulai", "hi", "halo", "assalamualaikum"]:
            app_logger.log_user_action(user, 'welcome_message')
            resp.message(WELCOME_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Help commands
        if message.lower() in ["help", "bantuan"]:
            resp.message(HELP_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        if message.lower() in ["panduan", "guide", "commands", "perintah"]:
            resp.message(PANDUAN_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Status command
        if message.lower() in ["status", "tier", "my status"]:
            from tier_management import format_tier_status_message
            status_msg = format_tier_status_message(user)
            resp.message(status_msg)
            return Response(str(resp), media_type="application/xml")
        
        # Route to appropriate handlers based on current state or command
        response = await route_message_to_handler(user, message, session, background_tasks)
        return response
        
    except Exception as e:
        error_id = app_logger.log_error(e, user_id=user, context={'message': message})
        resp.message(f"😔 Terjadi kesalahan. Kode error: {error_id}")
        return Response(str(resp), media_type="application/xml")

async def route_message_to_handler(user: str, message: str, session: dict, 
                                 background_tasks: BackgroundTasks) -> Response:
    """Route messages to appropriate handlers"""
    
    # Check current session state first
    current_state = session.get("state")
    
    # Child-related commands and states
    if (message.lower() in ["tambah anak", "tampilkan anak"] or 
        current_state and current_state.startswith("ADDCHILD")):
        return handle_child_commands(user, message)
    
    # Growth tracking
    if (message.lower() in ["catat timbang"] or 
        message.lower().startswith("lihat tumbuh kembang") or
        current_state and current_state.startswith("TIMBANG")):
        return handle_growth_tracking(user, message)
    
    # Feeding-related commands
    if (message.lower() in ["catat mpasi", "catat susu", "catat pumping", "hitung kalori susu"] or
        message.lower().startswith("lihat ringkasan") or
        current_state and current_state.startswith(("MPASI", "MILK", "PUMP", "CALC"))):
        return handle_feeding_commands(user, message)
    
    # Sleep tracking
    if (message.lower() in ["catat tidur", "lihat tidur", "riwayat tidur", "batal tidur"] or
        message.lower().startswith("selesai tidur") or
        current_state and current_state.startswith("SLEEP")):
        return handle_sleep_commands(user, message)
    
    # Reminder management
    if (message.lower().startswith(("set reminder", "atur pengingat", "show reminders", "lihat pengingat")) or
        message.lower().startswith(("done ", "snooze ", "skip reminder")) or
        current_state and current_state.startswith("REMINDER")):
        return handle_reminder_commands(user, message, background_tasks)
    
    # Calorie settings
    if (message.lower().startswith("set kalori") or
        current_state and current_state.startswith("SET_KALORI")):
        return handle_calorie_settings(user, message)
    
    # Summary and reports
    if (message.lower().startswith(("summary", "ringkasan")) or
        message.lower() in ["show summary", "daily summary"]):
        return handle_summary_commands(user, message)
    
    # Health tracking (poop, etc.)
    if (message.lower() in ["log poop", "catat bab", "show poop log", "lihat riwayat bab"] or
        current_state and current_state.startswith("POOP")):
        return handle_health_tracking(user, message)
    
    # Default response for unrecognized commands
    return handle_default_response(user, message)

# Handler functions - moved from separate files to avoid circular imports

def handle_cancel_command(user: str, resp: MessagingResponse) -> Response:
    """Handle cancel command"""
    session = session_manager.get_session(user)
    session["state"] = None
    session["data"] = {}
    session_manager.update_session(user, state=None, data={})
    
    app_logger.log_user_action(user, 'cancel_command')
    resp.message("✅ Sesi dibatalkan. Anda bisa mulai kembali dengan perintah baru.")
    return Response(str(resp), media_type="application/xml")

def handle_default_response(user: str, message: str) -> Response:
    """Handle unrecognized commands"""
    resp = MessagingResponse()
    
    # Log unrecognized command for improvement
    app_logger.log_user_action(
        user, 
        'unrecognized_command', 
        success=False, 
        details={'message': message}
    )
    
    # Get user tier for personalized response
    from tier_management import get_tier_limits
    limits = get_tier_limits(user)
    tier = limits.get('tier', 'free')
    
    if tier == 'premium':
        tier_text = "\n💎 Status: Premium User"
    else:
        tier_text = f"\n🆓 Status: Free User"
    
    reply = (
        f"🤖 Perintah tidak dikenali: '{message[:50]}...'{tier_text}\n\n"
        "Ketik 'help' untuk melihat semua perintah yang tersedia.\n\n"
        "Perintah populer:\n"
        "• tambah anak - daftarkan anak\n"
        "• catat mpasi - log makanan\n"
        "• catat susu - log susu/ASI\n"
        "• catat tidur - track tidur\n"
        "• ringkasan hari ini - lihat summary"
    )
    
    resp.message(reply)
    return Response(str(resp), media_type="application/xml")

def handle_child_commands(user: str, message: str) -> Response:
    """Handle child-related commands"""
    from handlers.child_handler import ChildHandler
    handler = ChildHandler(session_manager, app_logger)
    
    if message.lower() == "tambah anak":
        return handler.handle_add_child(user, message)
    elif message.lower() == "tampilkan anak":
        return handler.handle_show_child(user)
    else:
        # Handle session-based child commands
        return handler.handle_add_child(user, message)

def handle_growth_tracking(user: str, message: str) -> Response:
    """Handle growth tracking commands"""
    from handlers.child_handler import ChildHandler
    handler = ChildHandler(session_manager, app_logger)
    return handler.handle_growth_tracking(user, message)

def handle_feeding_commands(user: str, message: str) -> Response:
    """Handle feeding-related commands"""
    from handlers.feeding_handler import FeedingHandler
    handler = FeedingHandler(session_manager, app_logger)
    return handler.handle_feeding_commands(user, message)

def handle_sleep_commands(user: str, message: str) -> Response:
    """Handle sleep tracking commands"""
    from handlers.sleep_handler import SleepHandler
    handler = SleepHandler(session_manager, app_logger)
    return handler.handle_sleep_commands(user, message)

def handle_reminder_commands(user: str, message: str, background_tasks: BackgroundTasks) -> Response:
    """Handle reminder management commands"""
    from handlers.reminder_handler import ReminderHandler
    handler = ReminderHandler(session_manager, app_logger)
    return handler.handle_reminder_commands(user, message, background_tasks)

def handle_calorie_settings(user: str, message: str) -> Response:
    """Handle calorie setting commands"""
    from handlers.feeding_handler import FeedingHandler
    handler = FeedingHandler(session_manager, app_logger)
    return handler.handle_calorie_settings(user, message)

def handle_summary_commands(user: str, message: str) -> Response:
    """Handle summary and reporting commands"""
    from handlers.summary_handler import SummaryHandler
    handler = SummaryHandler(session_manager, app_logger)
    return handler.handle_summary_commands(user, message)

def handle_health_tracking(user: str, message: str) -> Response:
    """Handle health tracking commands"""
    from handlers.feeding_handler import FeedingHandler
    handler = FeedingHandler(session_manager, app_logger)
    return handler.handle_health_tracking(user, message)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        app_logger.app_logger.info("Starting Baby Log application v2.0.0")
        
        # Initialize database
        from database.operations import init_database
        init_database()
        app_logger.app_logger.info("Database initialized successfully")
        
        # Start background services only in production
        if os.environ.get('DATABASE_URL'):
            try:
                from background_services import start_reminder_scheduler
                start_reminder_scheduler()
                app_logger.app_logger.info("Background services started")
            except ImportError as e:
                app_logger.app_logger.warning(f"Background services not available: {e}")
        
        app_logger.app_logger.info("Baby Log application started successfully")
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'startup'})
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        # Close database connections
        db_pool.close_all()
        
        app_logger.app_logger.info("Baby Log application shutdown completed")
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'shutdown'})

# Admin endpoints for monitoring
@app.get("/admin/logs")
async def get_recent_logs():
    """Get recent application logs (admin only)"""
    try:
        return {
            "message": "Log endpoint - implement based on your log storage solution",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        app_logger.log_error(e, context={'function': 'get_logs'})
        return {"error": str(e)}

@app.get("/admin/users/{user_id}/sessions")
async def get_user_sessions(user_id: str):
    """Get user session information (admin only)"""
    try:
        session = session_manager.get_session(user_id)
        return {
            "user_id": user_id,
            "session": session,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        app_logger.log_error(e, context={'function': 'get_user_sessions'})
        return {"error": str(e)}

# For Railway deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
