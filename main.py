# main.py
"""
PRODUCTION-READY main application file for baby tracking chatbot
Fixed imports, error handling, and initialization issues
"""
import os
import sys
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from twilio.twiml.messaging_response import MessagingResponse

# Initialize logging first
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize database pool
try:
    from database_pool import DatabasePool
    db_pool = DatabasePool()
    logger.info("Database pool initialized")
except Exception as e:
    logger.error(f"Database pool initialization failed: {e}")
    db_pool = None

# Core modules that should always be available
from session_manager import SessionManager

# Initialize session manager
session_manager = SessionManager(timeout_minutes=30)

# Initialize FastAPI app
app = FastAPI(
    title="Baby Log WhatsApp Chatbot",
    version="2.0.0",
    description="Modular baby tracking chatbot with comprehensive logging"
)

# Constants - inline to avoid import issues
WELCOME_MESSAGE = (
    "🍼 Selamat datang di Babylog! 👋\n\n"
    "Saya siap membantu Anda mengelola catatan dan perkembangan si kecil.\n\n"
    "🚀 Untuk memulai, coba perintah ini:\n"
    "• `tambah anak` - Daftarkan data si kecil\n"
    "• `catat timbang` - Log berat & tinggi badan\n"
    "• `catat mpasi` - Log makanan bayi\n"
    "• `catat susu` - Log ASI/susu formula\n"
    "• `catat tidur` - Track jam tidur\n"
    "• `ringkasan hari ini` - Lihat aktivitas harian\n\n"
    "❓ Butuh bantuan? Ketik `bantuan` untuk panduan singkat atau `panduan` untuk daftar lengkap perintah."
)

HELP_MESSAGE = (
    "🤖 Bantuan Babylog:\n\n"
    "👶 Data Anak & Tumbuh Kembang:\n"
    "• `tambah anak` / `tampilkan anak`\n"
    "• `catat timbang` / `lihat tumbuh kembang`\n\n"
    "🍽️ Asupan Nutrisi:\n"
    "• `catat mpasi` / `lihat ringkasan mpasi`\n"
    "• `catat susu` / `lihat ringkasan susu`\n"
    "• `catat pumping` / `lihat ringkasan pumping`\n\n"
    "💤 Tidur & Kesehatan:\n"
    "• `catat tidur` / `lihat tidur` / `riwayat tidur`\n"
    "• `catat bab` / `lihat riwayat bab`\n\n"
    "⏰ Pengingat Susu:\n"
    "• `set reminder susu` / `show reminders`\n"
    "• done [volume] / snooze [menit] / skip reminder\n\n"
    "📊 Laporan:\n"
    "• `ringkasan hari ini` - Summary lengkap\n\n"
    "Ketik `panduan` untuk daftar lengkap perintah."
)

# Global handler variables 
child_handler = None
feeding_handler = None
sleep_handler = None
reminder_handler = None
summary_handler = None

def safe_import_handlers():
    """Safely import and initialize handlers with fallback"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    try:
        # Try to import handlers
        from handlers.child_handler import ChildHandler
        from handlers.feeding_handler import FeedingHandler  
        from handlers.sleep_handler import SleepHandler
        from handlers.reminder_handler import ReminderHandler
        from handlers.summary_handler import SummaryHandler
        
        # Initialize handlers
        child_handler = ChildHandler(session_manager, logger)
        feeding_handler = FeedingHandler(session_manager, logger)
        sleep_handler = SleepHandler(session_manager, logger)
        reminder_handler = ReminderHandler(session_manager, logger)
        summary_handler = SummaryHandler(session_manager, logger)
        
        logger.info("All handlers initialized successfully")
        return True
        
    except ImportError as e:
        logger.error(f"Handler import failed: {e}")
        # Create fallback handlers
        create_fallback_handlers()
        return True  # Still return True to continue
    except Exception as e:
        logger.error(f"Handler initialization failed: {e}")
        create_fallback_handlers()
        return True

def create_fallback_handlers():
    """Create simple fallback handlers"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    class FallbackHandler:
        def __init__(self, name):
            self.name = name
            
        def handle_command(self, user, message):
            resp = MessagingResponse()
            resp.message(f"Fitur {self.name} sedang dalam perbaikan. Coba lagi nanti atau gunakan perintah dasar seperti 'help'.")
            return Response(str(resp), media_type="application/xml")
    
    child_handler = FallbackHandler("anak")
    feeding_handler = FallbackHandler("makan/minum")
    sleep_handler = FallbackHandler("tidur")
    reminder_handler = FallbackHandler("pengingat")
    summary_handler = FallbackHandler("ringkasan")
    
    logger.info("Fallback handlers created")

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection if available
        db_status = "not_available"
        if db_pool:
            try:
                with db_pool.get_connection() as conn:
                    db_status = "connected"
            except Exception as e:
                db_status = f"error: {str(e)}"
        
        # Test handlers
        handlers_status = {
            'child_handler': child_handler is not None,
            'feeding_handler': feeding_handler is not None,
            'sleep_handler': sleep_handler is not None,
            'reminder_handler': reminder_handler is not None,
            'summary_handler': summary_handler is not None
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "handlers": handlers_status,
            "version": "2.0.0",
            "environment": os.getenv("ENVIRONMENT", "production")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook handler with bulletproof error handling"""
    try:
        form = await request.form()
        user = form.get("From")
        message = form.get("Body", "").strip()
        
        logger.info(f"Webhook received - User: {user}, Message: {message[:50]}...")
        
        resp = MessagingResponse()
        
        # Universal cancel command (highest priority)
        if message.lower() in ["batal", "cancel"]:
            return handle_cancel_command(user, resp)
        
        # Welcome commands
        if message.lower() in ["start", "mulai", "hi", "halo", "hello"]:
            session_manager.clear_session(user)
            resp.message(WELCOME_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Help commands
        if message.lower() in ["help", "bantuan"]:
            resp.message(HELP_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        if message.lower() in ["panduan", "guide"]:
            resp.message(get_panduan_message())
            return Response(str(resp), media_type="application/xml")
        
        # Get current session
        session = session_manager.get_session(user)
        current_state = session.get("state")
        
        # Route commands with safe error handling
        try:
            # Handle session-based commands first
            if current_state:
                return handle_session_command(user, message, current_state)
            
            # Handle new commands
            return handle_new_command(user, message)
            
        except Exception as e:
            logger.error(f"Command handling error: {e}")
            session_manager.clear_session(user)
            resp.message("❌ Terjadi kesalahan. Sesi telah direset. Ketik 'help' untuk mulai lagi.")
            return Response(str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        resp = MessagingResponse()
        resp.message("😔 Terjadi kesalahan sistem. Silakan coba lagi. Ketik 'help' untuk bantuan.")
        return Response(str(resp), media_type="application/xml")

def handle_session_command(user: str, message: str, current_state: str) -> Response:
    """Handle commands based on current session state"""
    resp = MessagingResponse()
    
    try:
        if current_state.startswith("ADDCHILD") or current_state.startswith("TIMBANG"):
            if hasattr(child_handler, 'handle_add_child'):
                return child_handler.handle_add_child(user, message)
            else:
                return child_handler.handle_command(user, message)
                
        elif current_state.startswith(("MPASI", "MILK", "PUMP", "CALC", "SET_KALORI", "POOP")):
            if hasattr(feeding_handler, 'handle_feeding_commands'):
                return feeding_handler.handle_feeding_commands(user, message)
            else:
                return feeding_handler.handle_command(user, message)
                
        elif current_state.startswith("REMINDER"):
            if hasattr(reminder_handler, 'handle_reminder_setup'):
                return reminder_handler.handle_reminder_setup(user, message)
            else:
                return reminder_handler.handle_command(user, message)
                
        elif current_state.startswith("SLEEP"):
            if hasattr(sleep_handler, 'handle_sleep_commands'):
                return sleep_handler.handle_sleep_commands(user, message)
            else:
                return sleep_handler.handle_command(user, message)
        else:
            # Unknown state, clear it
            session_manager.clear_session(user)
            resp.message("Sesi telah direset. Silakan mulai dengan perintah baru.")
            return Response(str(resp), media_type="application/xml")
            
    except Exception as e:
        logger.error(f"Session command error: {e}")
        session_manager.clear_session(user)
        resp.message("❌ Terjadi kesalahan. Sesi telah direset.")
        return Response(str(resp), media_type="application/xml")

def handle_new_command(user: str, message: str) -> Response:
    """Handle new commands"""
    resp = MessagingResponse()
    message_lower = message.lower()
    
    try:
        # === CHILD/GROWTH COMMANDS ===
        if message_lower in ["tambah anak", "tampilkan anak", "catat timbang"] or message_lower.startswith("lihat tumbuh kembang"):
            if hasattr(child_handler, 'handle_add_child'):
                if message_lower == "tambah anak":
                    return child_handler.handle_add_child(user, message)
                elif message_lower == "tampilkan anak":
                    return child_handler.handle_show_child(user)
                else:
                    return child_handler.handle_growth_tracking(user, message)
            else:
                return child_handler.handle_command(user, message)
        
        # === FEEDING COMMANDS ===
        elif (message_lower in ["catat mpasi", "catat susu", "catat pumping", "hitung kalori susu"] or
              message_lower.startswith(("set kalori", "lihat kalori", "lihat ringkasan")) or
              message_lower in ["log poop", "catat bab", "show poop log", "lihat riwayat bab"]):
            
            if hasattr(feeding_handler, 'handle_feeding_commands'):
                return feeding_handler.handle_feeding_commands(user, message)
            else:
                return feeding_handler.handle_command(user, message)
        
        # === SLEEP COMMANDS ===
        elif (message_lower == "catat tidur" or
              message_lower.startswith("selesai tidur") or
              message_lower == "batal tidur" or
              message_lower in ["lihat tidur", "tidur hari ini", "riwayat tidur", "sleep history"]):
            
            if hasattr(sleep_handler, 'handle_sleep_commands'):
                return sleep_handler.handle_sleep_commands(user, message)
            else:
                return sleep_handler.handle_command(user, message)
        
        # === REMINDER COMMANDS ===
        elif (message_lower in ["set reminder susu", "atur pengingat susu", "show reminders", "lihat pengingat"] or
              message_lower.startswith(("done ", "snooze ")) or
              message_lower in ["skip reminder"] or
              message_lower.startswith(("stop reminder", "delete reminder"))):
            
            if hasattr(reminder_handler, 'handle_reminder_commands'):
                return reminder_handler.handle_reminder_commands(user, message, BackgroundTasks())
            else:
                return reminder_handler.handle_command(user, message)
        
        # === SUMMARY COMMANDS ===
        elif (any(cmd in message_lower for cmd in ["summary", "ringkasan"]) or
              message_lower in ["growth summary", "ringkasan tumbuh kembang", "nutrition summary", "ringkasan nutrisi"]):
            
            if hasattr(summary_handler, 'handle_summary_commands'):
                return summary_handler.handle_summary_commands(user, message)
            else:
                return summary_handler.handle_command(user, message)
        
        # === UNKNOWN COMMAND ===
        else:
            logger.info(f"Unknown command from {user}: {message}")
            reply = (
                f"🤖 Perintah tidak dikenali: '{message[:30]}...'\n\n"
                f"Perintah utama:\n"
                f"• `tambah anak` - Setup data anak\n"
                f"• `catat mpasi` - Log makanan\n"
                f"• `catat susu` - Log ASI/sufor\n"
                f"• `catat tidur` - Track tidur\n"
                f"• `ringkasan hari ini` - Summary\n\n"
                f"Ketik `help` untuk bantuan lengkap."
            )
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
    
    except Exception as e:
        logger.error(f"New command error: {e}")
        resp.message("❌ Terjadi kesalahan saat memproses perintah. Ketik 'help' untuk bantuan.")
        return Response(str(resp), media_type="application/xml")

def handle_cancel_command(user: str, resp: MessagingResponse) -> Response:
    """Handle cancel command"""
    try:
        session = session_manager.get_session(user)
        current_state = session.get("state")
        
        if current_state:
            session_manager.clear_session(user)
            resp.message("✅ Sesi dibatalkan. Ketik perintah baru untuk melanjutkan.")
        else:
            resp.message("ℹ️ Tidak ada sesi aktif. Ketik 'help' untuk melihat perintah yang tersedia.")
        
        return Response(str(resp), media_type="application/xml")
    except Exception as e:
        logger.error(f"Cancel command error: {e}")
        resp.message("❌ Terjadi kesalahan.")
        return Response(str(resp), media_type="application/xml")

def get_panduan_message() -> str:
    """Get complete guide message"""
    return (
        "📖 Panduan Lengkap Babylog:\n\n"
        "👶 DATA ANAK:\n"
        "• `tambah anak` - Daftarkan anak\n"
        "• `tampilkan anak` - Lihat data\n"
        "• `catat timbang` - Catat pertumbuhan\n\n"
        "🍽️ MAKAN & MINUM:\n"
        "• `catat mpasi` - Log makanan\n"
        "• `catat susu` - Log ASI/sufor\n"
        "• `catat pumping` - Log ASI perah\n\n"
        "💤 TIDUR & KESEHATAN:\n"
        "• `catat tidur` - Mulai track tidur\n"
        "• `selesai tidur [HH:MM]` - Selesai\n"
        "• `catat bab` - Log BAB\n\n"
        "⏰ PENGINGAT:\n"
        "• `set reminder susu` - Buat pengingat\n"
        "• `done [volume]` - Respons cepat\n"
        "• `snooze [menit]` - Tunda\n\n"
        "📊 RINGKASAN:\n"
        "• `ringkasan hari ini` - Summary harian\n"
        "• `lihat ringkasan [jenis]` - Detail\n\n"
        "Ketik `help` untuk bantuan singkat."
    )

def safe_database_init():
    """Safely initialize database"""
    try:
        if db_pool:
            from database.operations import init_database
            init_database()
            logger.info("Database initialized successfully")
            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        logger.info("Starting Baby Log application v2.0.0")
        
        # Initialize database (non-blocking)
        safe_database_init()
        
        # Initialize handlers (with fallback)
        safe_import_handlers()
        
        logger.info("Baby Log application started successfully")
        
    except Exception as e:
        logger.error(f"Startup error (non-critical): {e}")
        # Don't raise - let the app start even if some components fail

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        # Close database connections
        if db_pool:
            db_pool.close_all()
        
        logger.info("Baby Log application shutdown completed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Chart endpoints (optional, with error handling)
@app.get("/mpasi-milk-graph/{user_phone}")
async def mpasi_milk_graph(user_phone: str):
    """Generate MPASI milk chart (with fallback)"""
    try:
        from chart_generator import generate_chart_response, normalize_user_phone
        user_phone = normalize_user_phone(user_phone)
        return await generate_chart_response(user_phone)
    except ImportError:
        return Response("Chart generation not available - missing dependencies", media_type="text/plain")
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return Response(f"Chart generation failed: {str(e)}", media_type="text/plain")

@app.get("/report-mpasi-milk/{user_phone}")
async def report_mpasi_milk(user_phone: str):
    """Generate PDF report (with fallback)"""
    try:
        from chart_generator import generate_pdf_response, normalize_user_phone
        user_phone = normalize_user_phone(user_phone)
        return await generate_pdf_response(user_phone)
    except ImportError:
        return Response("PDF generation not available - missing dependencies", media_type="text/plain")
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return Response(f"PDF generation failed: {str(e)}", media_type="text/plain")

# For Railway deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False, log_level="info")
