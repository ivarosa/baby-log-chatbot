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
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database pool
try:
    from database_pool import DatabasePool
    db_pool = DatabasePool()
    logger.info("Database pool initialized")
except Exception as e:
    logger.error(f"Database pool initialization failed: {e}")
    db_pool = None

# Core modules
from session_manager import SessionManager
from constants import WELCOME_MESSAGE, HELP_MESSAGE, PANDUAN_MESSAGE

# Initialize session manager
session_manager = SessionManager(timeout_minutes=30)

# Global handler variables - will be initialized after startup
child_handler = None
feeding_handler = None
sleep_handler = None
reminder_handler = None
summary_handler = None

# Initialize FastAPI app
app = FastAPI(
    title="Baby Log WhatsApp Chatbot",
    version="2.0.0",
    description="Modular baby tracking chatbot with comprehensive logging"
)

def initialize_handlers():
    """Initialize all handlers after startup"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    try:
        # Import handlers locally to avoid circular imports
        from handlers.child_handler import ChildHandler
        from handlers.feeding_handler import FeedingHandler  
        from handlers.sleep_handler import SleepHandler
        from handlers.reminder_handler import ReminderHandler
        from handlers.summary_handler import SummaryHandler
        
        # Use simple logger instead of complex app_logger
        child_handler = ChildHandler(session_manager, logger)
        feeding_handler = FeedingHandler(session_manager, logger)
        sleep_handler = SleepHandler(session_manager, logger)
        reminder_handler = ReminderHandler(session_manager, logger)
        summary_handler = SummaryHandler(session_manager, logger)
        
        logger.info("All handlers initialized successfully")
        return True
        
    except ImportError as e:
        logger.error(f"Handler import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Handler initialization failed: {e}")
        return False

@app.get("/health")
async def health_check():
    """Simple health check"""
    try:
        # Test database connection if available
        if db_pool:
            with db_pool.get_connection() as conn:
                pass
        
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
            "database": "connected" if db_pool else "not_available",
            "handlers": handlers_status,
            "version": "2.0.0"
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
    """Main webhook handler with complete command routing"""
    try:
        form = await request.form()
        user = form.get("From")
        message = form.get("Body", "").strip()
        
        # Log incoming message
        logger.info(f"Message from {user}: {message}")
        
        resp = MessagingResponse()
        
        # Check if handlers are initialized
        if not all([child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler]):
            resp.message("🔧 Sistem sedang dalam pemeliharaan. Silakan coba lagi dalam beberapa saat.")
            return Response(str(resp), media_type="application/xml")
        
        # Universal cancel command (highest priority)
        if message.lower() in ["batal", "cancel"]:
            return handle_cancel_command(user, resp)
        
        # Welcome commands
        if message.lower() in ["start", "mulai", "hi", "halo", "hello"]:
            session_manager.clear_session(user)  # Clear any existing session
            resp.message(WELCOME_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Help commands
        if message.lower() in ["help", "bantuan"]:
            resp.message(HELP_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        if message.lower() in ["panduan", "guide"]:
            resp.message(PANDUAN_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Get current session to check for ongoing flows
        session = session_manager.get_session(user)
        current_state = session.get("state")
        
        # Route based on current session state first (ongoing conversations)
        if current_state:
            try:
                if current_state.startswith("ADDCHILD") or current_state.startswith("TIMBANG"):
                    return child_handler.handle_add_child(user, message)
                elif current_state.startswith("MPASI"):
                    return feeding_handler.handle_mpasi_logging(user, message)
                elif current_state.startswith("MILK"):
                    return feeding_handler.handle_milk_logging(user, message)
                elif current_state.startswith("PUMP"):
                    return feeding_handler.handle_pumping_logging(user, message)
                elif current_state.startswith("CALC"):
                    return feeding_handler.handle_calorie_calculation(user, message)
                elif current_state.startswith("SET_KALORI"):
                    return feeding_handler.handle_calorie_settings(user, message)
                elif current_state.startswith("POOP"):
                    return feeding_handler.handle_health_tracking(user, message)
                elif current_state.startswith("REMINDER"):
                    return reminder_handler.handle_reminder_setup(user, message)
                elif current_state.startswith("SLEEP"):
                    return sleep_handler.handle_sleep_commands(user, message)
                else:
                    # Unknown state, clear it
                    session_manager.clear_session(user)
            except Exception as e:
                logger.error(f"Error in session state handler: {e}")
                session_manager.clear_session(user)
                resp.message("❌ Terjadi kesalahan. Sesi telah direset. Silakan mulai lagi.")
                return Response(str(resp), media_type="application/xml")
        
        # Route new commands based on content
        message_lower = message.lower()
        
        try:
            # === CHILD/GROWTH COMMANDS ===
            if (message_lower == "tambah anak" or 
                message_lower == "tampilkan anak" or
                message_lower == "catat timbang" or
                message_lower.startswith("lihat tumbuh kembang")):
                
                if message_lower == "tambah anak":
                    return child_handler.handle_add_child(user, message)
                elif message_lower == "tampilkan anak":
                    return child_handler.handle_show_child(user)
                else:
                    return child_handler.handle_growth_tracking(user, message)
            
            # === FEEDING COMMANDS ===
            elif (message_lower == "catat mpasi" or
                  message_lower == "catat susu" or
                  message_lower == "catat pumping" or
                  message_lower == "hitung kalori susu" or
                  message_lower.startswith("set kalori") or
                  message_lower == "lihat kalori" or
                  message_lower.startswith("lihat ringkasan") or
                  message_lower in ["log poop", "catat bab", "show poop log", "lihat riwayat bab"]):
                
                return feeding_handler.handle_feeding_commands(user, message)
            
            # === SLEEP COMMANDS ===
            elif (message_lower == "catat tidur" or
                  message_lower.startswith("selesai tidur") or
                  message_lower == "batal tidur" or
                  message_lower in ["lihat tidur", "tidur hari ini"] or
                  message_lower in ["riwayat tidur", "sleep history"]):
                
                return sleep_handler.handle_sleep_commands(user, message)
            
            # === REMINDER COMMANDS ===
            elif (message_lower in ["set reminder susu", "atur pengingat susu"] or
                  message_lower in ["show reminders", "lihat pengingat"] or
                  message_lower.startswith("done ") or
                  message_lower.startswith("snooze ") or
                  message_lower == "skip reminder" or
                  message_lower.startswith("stop reminder") or
                  message_lower.startswith("delete reminder")):
                
                return reminder_handler.handle_reminder_commands(user, message, background_tasks)
            
            # === SUMMARY COMMANDS ===
            elif (any(cmd in message_lower for cmd in ["summary", "ringkasan"]) or
                  message_lower in ["growth summary", "ringkasan tumbuh kembang", "summary pertumbuhan"] or
                  message_lower in ["nutrition summary", "ringkasan nutrisi", "summary gizi"]):
                
                return summary_handler.handle_summary_commands(user, message)
            
            # === UNKNOWN COMMAND ===
            else:
                logger.info(f"Unknown command from {user}: {message}")
                reply = (
                    f"🤖 **Perintah tidak dikenali:** '{message[:30]}...'\n\n"
                    f"**Perintah utama:**\n"
                    f"• `tambah anak` - Setup data anak\n"
                    f"• `catat mpasi` - Log makanan\n"
                    f"• `catat susu` - Log ASI/sufor\n"
                    f"• `catat tidur` - Track tidur\n"
                    f"• `summary today` - Ringkasan hari ini\n\n"
                    f"Ketik `help` untuk bantuan lengkap."
                )
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
        
        except Exception as e:
            logger.error(f"Error routing command '{message}' from {user}: {e}")
            resp.message("❌ Terjadi kesalahan saat memproses perintah. Silakan coba lagi.")
            return Response(str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        resp = MessagingResponse()
        resp.message("😔 Terjadi kesalahan sistem. Silakan coba lagi dalam beberapa saat.")
        return Response(str(resp), media_type="application/xml")

def handle_cancel_command(user: str, resp: MessagingResponse) -> Response:
    """Handle cancel command"""
    try:
        session = session_manager.get_session(user)
        current_state = session.get("state")
        
        if current_state:
            session_manager.clear_session(user)
            resp.message("✅ Sesi dibatalkan. Anda bisa mulai kembali dengan perintah baru.")
        else:
            resp.message("ℹ️ Tidak ada sesi aktif untuk dibatalkan. Ketik 'help' untuk melihat perintah yang tersedia.")
        
        return Response(str(resp), media_type="application/xml")
    except Exception as e:
        logger.error(f"Cancel command error: {e}")
        resp.message("❌ Terjadi kesalahan.")
        return Response(str(resp), media_type="application/xml")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        logger.info("Starting Baby Log application v2.0.0")
        
        # Initialize database first
        if db_pool:
            try:
                from database.operations import init_database
                init_database()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
        
        # Initialize handlers
        handlers_initialized = initialize_handlers()
        if not handlers_initialized:
            logger.warning("Handlers initialization failed, but continuing")
        
        logger.info("Baby Log application started successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
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

# For Railway deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
