# main.py - PRODUCTION READY VERSION
"""
Baby Log WhatsApp Chatbot - Production Ready
Version: 2.1.0
"""
import os
import sys
import asyncio
import signal
import json
import logging
import logging.handlers  # Fix: Explicitly import handlers module
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from twilio.twiml.messaging_response import MessagingResponse

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            'babylog.log',
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
    ]
)
logger = logging.getLogger(__name__)

# Import core modules with error handling
try:
    from database_pool import DatabasePool
    from session_manager import SessionManager
    from error_handler import ErrorHandler, WebhookErrorHandler
    from constants import WELCOME_MESSAGE, HELP_MESSAGE, PANDUAN_MESSAGE
    
    # Initialize core components
    db_pool = DatabasePool()
    session_manager = SessionManager(timeout_minutes=30)
    
    logger.info("Core components initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize core components: {e}")
    sys.exit(1)

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    try:
        logger.info("Starting Baby Log application...")
        
        # Initialize database
        await initialize_database()
        
        # Initialize handlers
        await initialize_handlers()
        
        # Start background services
        start_background_services()
        
        logger.info("Baby Log application started successfully")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down Baby Log application...")
        
        # Stop background services
        stop_background_services()
        
        # Close database connections
        if db_pool:
            db_pool.close_all()
        
        # Clean up sessions
        session_manager.cleanup_expired_sessions()
        
        logger.info("Baby Log application shutdown completed")

# Initialize FastAPI with lifecycle
app = FastAPI(
    title="Baby Log WhatsApp Chatbot",
    version="2.1.0",
    description="Production-ready baby tracking chatbot",
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your domain
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    error_id = ErrorHandler.log_error(exc, context={'path': request.url.path})
    logger.error(f"Unhandled exception: {exc}, Error ID: {error_id}")
    
    return Response(
        content=f"Internal server error. Reference: {error_id}",
        status_code=500
    )

# Rate limiting decorator
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

rate_limit_storage = defaultdict(list)

def rate_limit(max_calls: int = 10, window_seconds: int = 60):
    """Rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get client identifier
            client_id = request.client.host if request.client else "unknown"
            
            # Clean old entries
            now = datetime.now()
            cutoff = now - timedelta(seconds=window_seconds)
            rate_limit_storage[client_id] = [
                t for t in rate_limit_storage[client_id] if t > cutoff
            ]
            
            # Check rate limit
            if len(rate_limit_storage[client_id]) >= max_calls:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            # Record this call
            rate_limit_storage[client_id].append(now)
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# Initialize database with retry logic
async def initialize_database(max_retries: int = 3):
    """Initialize database with retry logic"""
    for attempt in range(max_retries):
        try:
            from database.operations import init_database
            init_database()
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            logger.error(f"Database initialization attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

# Initialize handlers with fallback
async def initialize_handlers():
    """Initialize all handlers with fallback mechanisms"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    try:
        logger.info("Starting handler initialization...")
        
        from handlers.child_handler import ChildHandler
        logger.info("ChildHandler imported successfully")
        
        from handlers.feeding_handler import FeedingHandler
        logger.info("FeedingHandler imported successfully")
        
        from handlers.sleep_handler import SleepHandler
        logger.info("SleepHandler imported successfully")
        
        from handlers.reminder_handler import ReminderHandler
        logger.info("ReminderHandler imported successfully")
        
        from handlers.summary_handler import SummaryHandler
        logger.info("SummaryHandler imported successfully")
        
        child_handler = ChildHandler(session_manager, logger)
        logger.info("ChildHandler initialized")
        
        feeding_handler = FeedingHandler(session_manager, logger)
        logger.info("FeedingHandler initialized")
        
        sleep_handler = SleepHandler(session_manager, logger)
        logger.info("SleepHandler initialized")
        
        reminder_handler = ReminderHandler(session_manager, logger)
        logger.info("ReminderHandler initialized")
        
        summary_handler = SummaryHandler(session_manager, logger)
        logger.info("SummaryHandler initialized")
        
        logger.info("All handlers initialized successfully")
        
    except ImportError as e:
        logger.error(f"Handler import failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        create_fallback_handlers()
    except Exception as e:
        logger.error(f"Handler initialization failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        create_fallback_handlers()
        
def create_fallback_handlers():
    """Create minimal fallback handlers"""
    global child_handler, feeding_handler, sleep_handler, reminder_handler, summary_handler
    
    class FallbackHandler:
        def __init__(self, name):
            self.name = name
        
        # Add all the expected method names    
        def handle_feeding_commands(self, user, message):
            return self.handle_commands(user, message)
        
        def handle_sleep_commands(self, user, message):
            return self.handle_commands(user, message)
            
        def handle_reminder_commands(self, user, message, background_tasks=None):
            return self.handle_commands(user, message)
            
        def handle_summary_commands(self, user, message):
            return self.handle_commands(user, message)
            
        def handle_add_child(self, user, message):
            return self.handle_commands(user, message)
            
        def handle_show_child(self, user):
            return self.handle_commands(user, "")
            
        def handle_growth_tracking(self, user, message):
            return self.handle_commands(user, message)
            
        def handle_commands(self, user, message):
            resp = MessagingResponse()
            resp.message(f"Fitur {self.name} sedang maintenance. Silakan coba beberapa saat lagi.")
            return Response(str(resp), media_type="application/xml")
    
    child_handler = FallbackHandler("data anak")
    feeding_handler = FallbackHandler("makan/minum")
    sleep_handler = FallbackHandler("tidur")
    reminder_handler = FallbackHandler("pengingat")
    summary_handler = FallbackHandler("ringkasan")
    
    logger.warning("Using fallback handlers")

# Background services management
background_services = {}

def start_background_services():
    """Start all background services"""
    try:
        from background_services import start_all_background_services
        start_all_background_services()
        logger.info("Background services started")
    except Exception as e:
        logger.error(f"Failed to start background services: {e}")

def stop_background_services():
    """Stop all background services"""
    try:
        from background_services import stop_all_background_services
        stop_all_background_services()
        logger.info("Background services stopped")
    except Exception as e:
        logger.error(f"Failed to stop background services: {e}")

# Health check endpoint with detailed status
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
        "environment": os.getenv("ENVIRONMENT", "production")
    }
    
    # Check database
    try:
        with db_pool.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1")
            health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check session manager
    try:
        stats = session_manager.get_stats()
        if stats is None:
            raise ValueError("Session stats unavailable (None)")
        health_status["sessions"] = {
            "active": stats.get("total_sessions", 0),
            "timeout_minutes": stats.get("timeout_minutes", None)
        }
    except Exception as e:
        health_status["sessions"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check handlers
    health_status["handlers"] = {
        "child": child_handler is not None,
        "feeding": feeding_handler is not None,
        "sleep": sleep_handler is not None,
        "reminder": reminder_handler is not None,
        "summary": summary_handler is not None
    }
    
    # Set appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return Response(
        content=json.dumps(health_status),
        status_code=status_code,
        media_type="application/json"
    )
    
# Main webhook endpoint with comprehensive error handling
@app.post("/webhook")
@rate_limit(max_calls=30, window_seconds=60)  # 30 requests per minute per IP
@WebhookErrorHandler.handle_webhook_error
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook handler with production-grade error handling"""
    
    # Extract and validate request
    try:
        form = await request.form()
        user = form.get("From")
        message = form.get("Body", "").strip()
        
        if not user or not message:
            logger.warning(f"Invalid webhook request: user={user}, message_length={len(message)}")
            resp = MessagingResponse()
            resp.message("Invalid request")
            return Response(str(resp), media_type="application/xml")
        
        # Sanitize inputs
        from validators import InputValidator
        user = InputValidator.sanitize_text_input(user, 100)
        message = InputValidator.sanitize_text_input(message, 1000)
        
        logger.info(f"Processing webhook: user={user[:20]}..., message={message[:50]}...")
        
    except Exception as e:
        logger.error(f"Request parsing error: {e}")
        resp = MessagingResponse()
        resp.message("Error processing request")
        return Response(str(resp), media_type="application/xml")
    
    # Process message with timeout
    try:
        result = await asyncio.wait_for(
            process_message(user, message, background_tasks),
            timeout=25.0  # 25 second timeout
        )
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Message processing timeout for user {user}")
        resp = MessagingResponse()
        resp.message("⏱️ Request timeout. Silakan coba lagi.")
        return Response(str(resp), media_type="application/xml")

async def process_message(user: str, message: str, background_tasks: BackgroundTasks) -> Response:
    """Process user message with proper routing"""
    resp = MessagingResponse()
    
    # Get session
    session = session_manager.get_session(user)
    current_state = session.get("state")
    
    # Universal commands
    if message.lower() in ["batal", "cancel"]:
        session_manager.clear_session(user)
        resp.message("✅ Sesi dibatalkan. Silakan mulai dengan perintah baru.")
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
    
    # Override commands that should start new sessions even if there's an active session
    override_commands = ["catat tidur", "catat susu", "catat mpasi", "catat pumping", "catat bab", 
                         "tambah anak", "tampilkan anak", "catat timbang"]
    
    if message.lower() in override_commands:
        session_manager.clear_session(user)
        logger.info(f"Override command detected: '{message}' - cleared existing session")
        return await route_new_command(user, message, background_tasks)
    
    # Route to appropriate handler
    try:
        # Session-based routing
        if current_state:
            return await route_session_command(user, message, current_state, background_tasks)
        
        # New command routing
        return await route_new_command(user, message, background_tasks)
        
    except Exception as e:
        logger.error(f"Message routing error: {e}")
        session_manager.clear_session(user)
        resp.message("❌ Terjadi kesalahan. Silakan coba lagi.")
        return Response(str(resp), media_type="application/xml")

async def route_session_command(user: str, message: str, state: str, background_tasks: BackgroundTasks) -> Response:
    """Route commands based on session state"""
    
    # Child/growth commands
    if state.startswith(("ADDCHILD", "TIMBANG")):
        if hasattr(child_handler, 'handle_add_child'):
            return child_handler.handle_add_child(user, message)
        return child_handler.handle_commands(user, message)
    
    # Feeding commands
    elif state.startswith(("MPASI", "MILK", "PUMP", "CALC", "SET_KALORI", "POOP")):
        if hasattr(feeding_handler, 'handle_feeding_commands'):
            return feeding_handler.handle_feeding_commands(user, message)
        return feeding_handler.handle_commands(user, message)
    
    # Sleep commands
    elif state.startswith("SLEEP"):
        if hasattr(sleep_handler, 'handle_sleep_commands'):
            return sleep_handler.handle_sleep_commands(user, message)
        return sleep_handler.handle_commands(user, message)
    
    # Reminder commands
    elif state.startswith("REMINDER"):
        if hasattr(reminder_handler, 'handle_reminder_commands'):
            return reminder_handler.handle_reminder_commands(user, message, background_tasks)
        return reminder_handler.handle_commands(user, message)
    
    # Unknown state
    else:
        session_manager.clear_session(user)
        resp = MessagingResponse()
        resp.message("Sesi tidak valid. Silakan mulai dengan perintah baru.")
        return Response(str(resp), media_type="application/xml")

async def route_new_command(user: str, message: str, background_tasks: BackgroundTasks) -> Response:
    """Route new commands to appropriate handlers"""
    message_lower = message.lower()
    
    # Child commands
    if message_lower in ["tambah anak", "tampilkan anak", "catat timbang"] or \
       message_lower.startswith("lihat tumbuh kembang"):
        if child_handler:
            if message_lower == "tambah anak":
                return child_handler.handle_add_child(user, message)
            elif message_lower == "tampilkan anak":
                return child_handler.handle_show_child(user)
            else:
                return child_handler.handle_growth_tracking(user, message)
    
    # Feeding commands
    elif message_lower in ["catat mpasi", "catat susu", "catat pumping", "hitung kalori susu", 
                          "catat bab", "log poop", "lihat riwayat bab", "show poop log"] or \
         message_lower.startswith(("set kalori", "lihat kalori", "lihat ringkasan")):
        if feeding_handler and hasattr(feeding_handler, 'handle_feeding_commands'):
            return feeding_handler.handle_feeding_commands(user, message)
    
    # Sleep commands
    elif message_lower in ["catat tidur", "batal tidur", "lihat tidur", "riwayat tidur"] or \
         message_lower.startswith("selesai tidur"):
        if sleep_handler and hasattr(sleep_handler, 'handle_sleep_commands'):
            return sleep_handler.handle_sleep_commands(user, message)
    
    # Reminder commands
    elif message_lower in ["set reminder susu", "show reminders", "skip reminder"] or \
         message_lower.startswith(("done ", "snooze ", "stop reminder", "delete reminder")):
        if reminder_handler and hasattr(reminder_handler, 'handle_reminder_commands'):
            return reminder_handler.handle_reminder_commands(user, message, background_tasks)
    
    # Summary commands
    elif any(cmd in message_lower for cmd in ["summary", "ringkasan"]):
        if summary_handler and hasattr(summary_handler, 'handle_summary_commands'):
            return summary_handler.handle_summary_commands(user, message)
    
    # Unknown command
    resp = MessagingResponse()
    resp.message(
        f"❓ Perintah tidak dikenali: '{message[:30]}...'\n\n"
        f"Perintah utama:\n"
        f"• `tambah anak`\n"
        f"• `catat mpasi`\n"
        f"• `catat susu`\n"
        f"• `catat tidur`\n"
        f"• `ringkasan hari ini`\n\n"
        f"Ketik `help` untuk bantuan."
    )
    return Response(str(resp), media_type="application/xml")

# Chart generation endpoints (optional features)
@app.get("/mpasi-milk-graph/{user_phone}")
@rate_limit(max_calls=10, window_seconds=60)
async def mpasi_milk_graph(user_phone: str):
    """Generate MPASI/milk chart with error handling"""
    try:
        from chart_generator import generate_chart_response, normalize_user_phone
        user_phone = normalize_user_phone(user_phone)
        return await generate_chart_response(user_phone)
    except ImportError:
        raise HTTPException(status_code=503, detail="Chart generation not available")
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        raise HTTPException(status_code=500, detail="Chart generation failed")

@app.get("/report-mpasi-milk/{user_phone}")
@rate_limit(max_calls=5, window_seconds=60)
async def report_mpasi_milk(user_phone: str):
    """Generate PDF report with error handling"""
    try:
        from chart_generator import generate_pdf_response, normalize_user_phone
        user_phone = normalize_user_phone(user_phone)
        return await generate_pdf_response(user_phone)
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF generation not available")
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

# Admin endpoints (protected)
@app.get("/admin/stats")
async def admin_stats(api_key: str = None):
    """Get application statistics"""
    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    stats = {
        "sessions": session_manager.get_stats(),
        "database": db_pool.get_stats() if db_pool else {},
        "timestamp": datetime.now().isoformat()
    }
    
    return stats

# Graceful shutdown handler
def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Production configuration
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    workers = int(os.getenv("WORKERS", 4))
    
    logger.info(f"Starting server on {host}:{port} with {workers} workers")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        loop="uvloop",  # Better performance
        access_log=True,
        log_level="info",
        reload=False  # Never use reload in production
    )
