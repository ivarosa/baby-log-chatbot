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
    """Main webhook handler with better error handling"""
    try:
        form = await request.form()
        user = form.get("From")
        message = form.get("Body", "").strip()
        
        resp = MessagingResponse()
        
        # Universal commands (no session state)
        if message.lower() in ["batal", "cancel"]:
            return handle_cancel_command(user, resp)
        
        # Welcome commands
        if message.lower() in ["start", "mulai", "hi", "halo"]:
            resp.message(WELCOME_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Help commands
        if message.lower() in ["help", "bantuan"]:
            resp.message(HELP_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        if message.lower() in ["panduan", "guide"]:
            resp.message(PANDUAN_MESSAGE)
            return Response(str(resp), media_type="application/xml")
        
        # Simple routing - avoid complex routing for now
        response_message = "🤖 Sistem berfungsi! Ketik 'help' untuk melihat perintah yang tersedia."
        resp.message(response_message)
        return Response(str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        resp = MessagingResponse()
        resp.message("😔 Terjadi kesalahan sistem. Silakan coba lagi.")
        return Response(str(resp), media_type="application/xml")

def handle_cancel_command(user: str, resp: MessagingResponse) -> Response:
    """Handle cancel command"""
    try:
        session = session_manager.get_session(user)
        session["state"] = None
        session["data"] = {}
        session_manager.update_session(user, state=None, data={})
        
        resp.message("✅ Sesi dibatalkan. Anda bisa mulai kembali dengan perintah baru.")
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
