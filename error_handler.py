import logging
import traceback
from typing import Optional, Dict, Any
from functools import wraps
from datetime import datetime

class BabyLogError(Exception):
    """Base exception for BabyLog"""
    pass

class ValidationError(BabyLogError):
    """Input validation error"""
    pass

class DatabaseError(BabyLogError):
    """Database operation error"""
    pass

class ExternalAPIError(BabyLogError):
    """External API error (Twilio, OpenAI)"""
    pass

class SessionError(BabyLogError):
    """Session management error"""
    pass

class ErrorHandler:
    """Centralized error handling"""
    
    # User-friendly error messages
    ERROR_MESSAGES = {
        'database': "Maaf, terjadi kesalahan database. Silakan coba lagi.",
        'validation': "Data yang Anda masukkan tidak valid. {}",
        'api': "Layanan sedang tidak tersedia. Silakan coba lagi nanti.",
        'session': "Sesi Anda telah berakhir. Silakan mulai lagi.",
        'generic': "Maaf, terjadi kesalahan. Silakan coba lagi.",
        'timeout': "Waktu habis. Silakan coba lagi.",
        'permission': "Anda tidak memiliki akses untuk fitur ini.",
        'limit': "Anda telah mencapai batas penggunaan. Upgrade ke premium untuk melanjutkan."
    }
    
    @staticmethod
    def get_user_message(error_type: str, details: str = "") -> str:
        """Get user-friendly error message"""
        base_message = ErrorHandler.ERROR_MESSAGES.get(error_type, ErrorHandler.ERROR_MESSAGES['generic'])
        
        if '{}' in base_message and details:
            return base_message.format(details)
        elif details and error_type == 'validation':
            return f"{base_message} {details}"
        
        return base_message
    
    @staticmethod
    def log_error(error: Exception, user_id: str = None, context: Dict[str, Any] = None):
        """Log error with context"""
        error_id = datetime.now().strftime("%Y%m%d%H%M%S")
        
        log_data = {
            'error_id': error_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'user_id': user_id,
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        logging.error(f"Error ID {error_id}: {log_data}")
        
        return error_id
    
    @staticmethod
    def handle_database_error(func):
        """Decorator for database operations"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the actual error
                error_id = ErrorHandler.log_error(e, context={'function': func.__name__})
                
                # Raise user-friendly error
                raise DatabaseError(f"Database operation failed. Error ID: {error_id}")
        
        return wrapper
    
    @staticmethod
    def handle_validation_error(func):
        """Decorator for validation operations"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError:
                raise  # Re-raise validation errors as-is
            except Exception as e:
                error_id = ErrorHandler.log_error(e, context={'function': func.__name__})
                raise ValidationError(f"Validation failed. Error ID: {error_id}")
        
        return wrapper
    
    @staticmethod
    def safe_execute(func, *args, default=None, error_message=None, **kwargs):
        """Safely execute a function with fallback"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ErrorHandler.log_error(e, context={'function': func.__name__})
            
            if error_message:
                logging.warning(error_message)
            
            return default

# Enhanced error handling for webhook
class WebhookErrorHandler:
    """Error handling specifically for webhook endpoints"""
    
    @staticmethod
    def handle_webhook_error(func):
        """Decorator for webhook handlers"""
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            from twilio.twiml.messaging_response import MessagingResponse
            from fastapi.responses import Response
            
            user = None
            try:
                # Extract user from request
                form = await request.form()
                user = form.get("From")
                
                return await func(request, *args, **kwargs)
                
            except ValidationError as e:
                # Send validation error to user
                resp = MessagingResponse()
                resp.message(f"❌ {str(e)}")
                return Response(str(resp), media_type="application/xml")
                
            except DatabaseError as e:
                # Database error
                error_id = ErrorHandler.log_error(e, user_id=user)
                resp = MessagingResponse()
                resp.message(f"⚠️ Terjadi kesalahan database. Kode error: {error_id}")
                return Response(str(resp), media_type="application/xml")
                
            except Exception as e:
                # Generic error
                error_id = ErrorHandler.log_error(e, user_id=user)
                resp = MessagingResponse()
                resp.message(f"😔 Maaf, terjadi kesalahan. Kode error: {error_id}\nSilakan coba lagi atau hubungi support.")
                return Response(str(resp), media_type="application/xml")
        
        return wrapper
