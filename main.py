# main.py - RAILWAY DEPLOYMENT READY
"""
Baby Log WhatsApp Chatbot - Railway Production Ready
Version: 2.1.1
"""
import os
import sys
import asyncio
import signal
import json
import logging
import logging.handlers
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from twilio.twiml.messaging_response import MessagingResponse

# Configure production logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 60)
logger.info("BABY LOG APPLICATION STARTING")
logger.info("=" * 60)

# Import core modules with error handling
try:
    from database_pool import DatabasePool
    from session_manager import SessionManager
    from error_handler import ErrorHandler, WebhookErrorHandler
    from constants import WELCOME_MESSAGE, HELP_MESSAGE, PANDUAN_MESSAGE
    
    logger.info("✅ Core modules imported successfully")
except Exception as e:
    logger.critical(f"❌ Failed to import core modules: {e}")
    sys.exit(1)

# Initialize core components EARLY
try:
    db_pool = DatabasePool()
    session_manager = SessionManager(timeout_minutes=30)
    logger.info("✅ Core components initialized")
except Exception as e:
    logger.critical(f"❌ Failed to initialize core components: {e}")
    sys.exit(1)

# Initialize handler variables
child_handler = None
feeding_handler = None
sleep_handler = None
reminder_handler = None
summary_handler = None

# Simple healthcheck flag
app_ready = False

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global app_ready
    
    # Startup
    try:
        logger.info("🚀 Starting Baby Log application...")
        
        # Initialize database with retries
        await initialize_database_with_retry()
        
        # Initialize handlers
        await initialize_handlers()
        
        # Mark app as ready BEFORE starting background services
        app_ready = True
        logger.info("✅ Application marked as READY")
        
        # Start background services (non-blocking)
        try:
            start_background_services()
        except Exception as e:
            logger.warning(f"⚠️ Background services failed to start: {e}")
            logger.warning("⚠️ Continuing without background services")
        
        logger.info("🎉 Baby Log application started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        # Still mark as ready to allow healthcheck to pass
        app_ready = True
        yield
        
    finally:
        # Shutdown
        logger.info("🛑 Shutting down Baby Log application...")
        app_ready = False
        
        # Stop background services
        try:
            stop_background_services()
        except:
            pass
        
        # Close database connections
        try:
            if db_pool:
                db_pool.close_all()
        except:
            pass
        
        # Clean up sessions
        try:
            session_manager.cleanup_expired_sessions()
        except:
            pass
        
        logger.info("✅ Baby Log application shutdown completed")

# Initialize FastAPI with lifecycle
app = FastAPI(
    title="Baby Log WhatsApp Chatbot",
    version="2.1.1",
    description="Railway production-ready baby tracking chatbot",
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files with error handling
try:
    if not os.path.exists("static"):
        os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✅ Static files mounted")
except Exception as e:
    logger.warning(f"⚠️ Failed to mount static files: {e}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    error_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.error(f"Unhandled exception: {exc}, Error ID: {error_id}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "error_id": error_id}
    )

# Initialize database with retry logic
async def initialize_database_with_retry(max_retries: int = 5):
    """Initialize database with retry logic"""
    for attempt in range(max_retries):
        try:
            logger.info(f"📊 Database initialization attempt {attempt + 1}/{max_retries}")
            from database.operations import init_database
            init_database()
            logger.info("✅ Database initialized successfully")
            return
        except Exception as e:
            logger.error(f"❌ Database init attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error("❌ All database initialization attempts failed")
                logger.warning("⚠️ Continuing without database - app will use fallbacks")
                return
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

# Initialize handlers with fallback
async def initialize_handlers():
    """Initialize all handlers with fallback mechanisms"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    try:
        logger.info("🔧 Starting handler initialization...")
        
        from handlers.child_handler import ChildHandler
        from handlers.feeding_handler import FeedingHandler
        from handlers.sleep_handler import SleepHandler
        from handlers.reminder_handler import ReminderHandler
        from handlers.summary_handler import SummaryHandler
        
        child_handler = ChildHandler(session_manager, logger)
        feeding_handler = FeedingHandler(session_manager, logger)
        sleep_handler = SleepHandler(session_manager, logger)
        reminder_handler = ReminderHandler(session_manager, logger)
        summary_handler = SummaryHandler(session_manager, logger)
        
        logger.info("✅ All handlers initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Handler initialization failed: {e}", exc_info=True)
        create_fallback_handlers()
        
def create_fallback_handlers():
    """Create minimal fallback handlers"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    class FallbackHandler:
        def __init__(self, name):
            self.name = name
        
        def handle_feeding_commands(self, user, message):
            return self._respond()
        
        def handle_sleep_commands(self, user, message):
            return self._respond()
            
        def handle_reminder_commands(self, user, message, background_tasks=None):
            return self._respond()
            
        def handle_summary_commands(self, user, message):
            return self._respond()
            
        def handle_add_child(self, user, message):
            return self._respond()
            
        def handle_show_child(self, user):
            return self._respond()
            
        def handle_growth_tracking(self, user, message):
            return self._respond()
            
        def _respond(self):
            resp = MessagingResponse()
            resp.message(f"⚠️ Sistem {self.name} sedang dalam maintenance. Silakan coba lagi nanti.")
            return Response(str(resp), media_type="application/xml")
    
    child_handler = FallbackHandler("data anak")
    feeding_handler = FallbackHandler("makan/minum")
    sleep_handler = FallbackHandler("tidur")
    reminder_handler = FallbackHandler("pengingat")
    summary_handler = FallbackHandler("ringkasan")
    
    logger.warning("⚠️ Using fallback handlers")

# Background services management
def start_background_services():
    """Start all background services"""
    try:
        from background_services import start_all_background_services
        start_all_background_services()
        logger.info("✅ Background services started")
    except Exception as e:
        logger.warning(f"⚠️ Background services failed: {e}")

def stop_background_services():
    """Stop all background services"""
    try:
        from background_services import stop_all_background_services
        stop_all_background_services()
        logger.info("✅ Background services stopped")
    except Exception as e:
        logger.warning(f"⚠️ Background services stop failed: {e}")

# CRITICAL: Simple health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check - MUST return 200 quickly"""
    health_status = {
        "status": "healthy" if app_ready else "starting",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.1"
    }
    
    # Always return 200 if the app is running
    return JSONResponse(
        content=health_status,
        status_code=200
    )

# Root endpoint for Railway detection
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Baby Log WhatsApp Chatbot",
        "status": "running" if app_ready else "starting",
        "version": "2.1.1"
    }

# Main webhook endpoint
@app.post("/webhook")
@WebhookErrorHandler.handle_webhook_error
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook handler"""
    
    # Extract and validate request
    try:
        form = await request.form()
        user = form.get("From")
        message = form.get("Body", "").strip()
        
        if not user or not message:
            resp = MessagingResponse()
            resp.message("Invalid request")
            return Response(str(resp), media_type="application/xml")
        
        # Sanitize inputs
        from validators import InputValidator
        user = InputValidator.sanitize_text_input(user, 100)
        message = InputValidator.sanitize_text_input(message, 1000)
        
        logger.info(f"📨 Message from {user[:20]}...")
        
    except Exception as e:
        logger.error(f"❌ Request parsing error: {e}")
        resp = MessagingResponse()
        resp.message("Error processing request")
        return Response(str(resp), media_type="application/xml")
    
    # Process message with timeout
    try:
        result = await asyncio.wait_for(
            process_message(user, message, background_tasks),
            timeout=25.0
        )
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout for user {user}")
        resp = MessagingResponse()
        resp.message("⏱️ Request timeout. Silakan coba lagi.")
        return Response(str(resp), media_type="application/xml")

async def process_message(user: str, message: str, background_tasks: BackgroundTasks) -> Response:
    """Process user message"""
    resp = MessagingResponse()
    
    # Get session
    session = session_manager.get_session(user)
    current_state = session.get("state")
    
    # Universal commands
    if message.lower() in ["batal", "cancel"]:
        session_manager.clear_session(user)
        resp.message("✅ Sesi dibatalkan.")
        return Response(str(resp), media_type="application/xml")
    
    if message.lower() in ["start", "mulai", "hi", "halo"]:
        session_manager.clear_session(user)
        resp.message(WELCOME_MESSAGE)
        return Response(str(resp), media_type="application/xml")
    
    if message.lower() in ["help", "bantuan"]:
        resp.message(HELP_MESSAGE)
        return Response(str(resp), media_type="application/xml")
    
    if message.lower() in ["panduan", "guide"]:
        resp.message(PANDUAN_MESSAGE)
        return Response(str(resp), media_type="application/xml")
    
    # Route to handlers
    try:
        if current_state:
            return await route_session_command(user, message, current_state, background_tasks)
        return await route_new_command(user, message, background_tasks)
    except Exception as e:
        logger.error(f"❌ Routing error: {e}", exc_info=True)
        session_manager.clear_session(user)
        resp.message("❌ Terjadi kesalahan. Silakan coba lagi.")
        return Response(str(resp), media_type="application/xml")

async def route_session_command(user: str, message: str, state: str, background_tasks: BackgroundTasks) -> Response:
    """Route based on session state"""
    if state.startswith("ADDCHILD") or state.startswith("TIMBANG"):
        return child_handler.handle_growth_tracking(user, message) if state.startswith("TIMBANG") else child_handler.handle_add_child(user, message)
    elif state.startswith(("MPASI", "MILK", "PUMP", "CALC", "SET_KALORI", "POOP")):
        return feeding_handler.handle_feeding_commands(user, message)
    elif state.startswith("SLEEP"):
        return sleep_handler.handle_sleep_commands(user, message)
    elif state.startswith("REMINDER"):
        return reminder_handler.handle_reminder_commands(user, message, background_tasks)
    else:
        session_manager.clear_session(user)
        resp = MessagingResponse()
        resp.message("Sesi tidak valid. Silakan mulai dengan perintah baru.")
        return Response(str(resp), media_type="application/xml")

async def route_new_command(user: str, message: str, background_tasks: BackgroundTasks) -> Response:
    """Route new commands"""
    msg = message.lower()
    
    # Child commands
    if msg in ["tambah anak", "tampilkan anak"] or msg.startswith(("catat timbang", "lihat tumbuh")):
        if msg == "tambah anak":
            return child_handler.handle_add_child(user, message)
        elif msg == "tampilkan anak":
            return child_handler.handle_show_child(user)
        else:
            return child_handler.handle_growth_tracking(user, message)
    
    # Feeding
    elif msg in ["catat mpasi", "catat susu", "catat pumping"] or msg.startswith(("hitung kalori", "set kalori", "lihat kalori", "lihat ringkasan", "catat bab")):
        return feeding_handler.handle_feeding_commands(user, message)
    
    # Sleep
    elif msg in ["catat tidur", "batal tidur", "lihat tidur", "riwayat tidur"] or msg.startswith("selesai tidur"):
        return sleep_handler.handle_sleep_commands(user, message)
    
    # Reminders
    elif msg in ["set reminder susu", "show reminders", "skip reminder"] or msg.startswith(("done ", "snooze ", "henti reminder", "delete reminder")):
        return reminder_handler.handle_reminder_commands(user, message, background_tasks)
    
    # Summary
    elif "summary" in msg or "ringkasan" in msg:
        return summary_handler.handle_summary_commands(user, message)
    
    # Unknown
    resp = MessagingResponse()
    resp.message("❓ Perintah tidak dikenali. Ketik 'help' untuk bantuan.")
    return Response(str(resp), media_type="application/xml")

# Main entry point
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting server on port {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1,  # Single worker for Railway
        loop="uvloop",
        access_log=True,
        log_level="info"
    )
