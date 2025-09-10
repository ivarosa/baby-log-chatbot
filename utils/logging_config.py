# utils/logging_config.py
"""
Advanced logging configuration for baby log application
Includes structured logging, performance monitoring, and error tracking
"""
import os
import sys
import logging
import logging.handlers
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import traceback

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'action'):
            log_data['action'] = record.action
        if hasattr(record, 'duration'):
            log_data['duration_ms'] = record.duration
        if hasattr(record, 'error_id'):
            log_data['error_id'] = record.error_id
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)

class PerformanceLogger:
    """Logger for performance monitoring"""
    
    def __init__(self, logger_name: str = 'performance'):
        self.logger = logging.getLogger(logger_name)
    
    def log_request(self, user_id: str, action: str, duration_ms: float, 
                   success: bool = True, extra_data: Dict[str, Any] = None):
        """Log request performance"""
        self.logger.info(
            f"Request completed: {action}",
            extra={
                'user_id': user_id,
                'action': action,
                'duration': duration_ms,
                'success': success,
                'extra_data': extra_data or {}
            }
        )
    
    def log_database_query(self, query_type: str, duration_ms: float, 
                          table_name: str = None, row_count: int = None):
        """Log database query performance"""
        self.logger.info(
            f"Database query: {query_type}",
            extra={
                'action': 'database_query',
                'query_type': query_type,
                'duration': duration_ms,
                'table_name': table_name,
                'row_count': row_count
            }
        )
    
    def log_external_api(self, service: str, endpoint: str, duration_ms: float,
                        status_code: int = None, success: bool = True):
        """Log external API call performance"""
        self.logger.info(
            f"External API call: {service}/{endpoint}",
            extra={
                'action': 'external_api',
                'service': service,
                'endpoint': endpoint,
                'duration': duration_ms,
                'status_code': status_code,
                'success': success
            }
        )

class SecurityLogger:
    """Logger for security events"""
    
    def __init__(self, logger_name: str = 'security'):
        self.logger = logging.getLogger(logger_name)
    
    def log_authentication_attempt(self, user_id: str, success: bool, 
                                  ip_address: str = None, user_agent: str = None):
        """Log authentication attempts"""
        self.logger.info(
            f"Authentication attempt: {'success' if success else 'failed'}",
            extra={
                'user_id': user_id,
                'action': 'authentication',
                'success': success,
                'ip_address': ip_address,
                'user_agent': user_agent
            }
        )
    
    def log_suspicious_activity(self, user_id: str, activity_type: str, 
                              details: Dict[str, Any] = None):
        """Log suspicious activities"""
        self.logger.warning(
            f"Suspicious activity detected: {activity_type}",
            extra={
                'user_id': user_id,
                'action': 'suspicious_activity',
                'activity_type': activity_type,
                'details': details or {}
            }
        )
    
    def log_rate_limit_exceeded(self, user_id: str, endpoint: str, 
                               current_count: int, limit: int):
        """Log rate limit violations"""
        self.logger.warning(
            f"Rate limit exceeded: {endpoint}",
            extra={
                'user_id': user_id,
                'action': 'rate_limit_exceeded',
                'endpoint': endpoint,
                'current_count': current_count,
                'limit': limit
            }
        )

class ApplicationLogger:
    """Main application logger configuration"""
    
    def __init__(self):
        self.performance = PerformanceLogger()
        self.security = SecurityLogger()
        self.app_logger = logging.getLogger('app')
    
    def log_user_action(self, user_id: str, action: str, success: bool = True,
                       details: Dict[str, Any] = None):
        """Log user actions"""
        self.app_logger.info(
            f"User action: {action}",
            extra={
                'user_id': user_id,
                'action': action,
                'success': success,
                'details': details or {}
            }
        )
    
    def log_error(self, error: Exception, user_id: str = None, 
                 context: Dict[str, Any] = None) -> str:
        """Log errors with context"""
        error_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        self.app_logger.error(
            f"Application error: {str(error)}",
            extra={
                'error_id': error_id,
                'user_id': user_id,
                'action': 'error',
                'context': context or {},
                'error_type': type(error).__name__
            },
            exc_info=True
        )
        
        return error_id
    
    def log_business_event(self, event_type: str, user_id: str = None,
                          data: Dict[str, Any] = None):
        """Log business events (subscriptions, feature usage, etc.)"""
        self.app_logger.info(
            f"Business event: {event_type}",
            extra={
                'user_id': user_id,
                'action': 'business_event',
                'event_type': event_type,
                'data': data or {}
            }
        )

def setup_logging(log_level: str = None, log_file: str = None, 
                 enable_json: bool = None) -> ApplicationLogger:
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (optional)
        enable_json: Whether to use JSON formatting
    
    Returns:
        ApplicationLogger instance
    """
    # Get configuration from environment or defaults
    log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    log_file = log_file or os.getenv('LOG_FILE')
    enable_json = enable_json if enable_json is not None else os.getenv('LOG_JSON', 'false').lower() == 'true'
    
    # Set root logger level
    logging.root.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Choose formatter
    if enable_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)
    
    # Configure specific loggers
    configure_logger_levels()
    
    return ApplicationLogger()

def configure_logger_levels():
    """Configure specific logger levels"""
    # Set levels for external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('twilio').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    
    # Set levels for database
    logging.getLogger('psycopg').setLevel(logging.WARNING)
    logging.getLogger('sqlite3').setLevel(logging.WARNING)
    
    # Application loggers
    logging.getLogger('app').setLevel(logging.INFO)
    logging.getLogger('performance').setLevel(logging.INFO)
    logging.getLogger('security').setLevel(logging.WARNING)

class LoggingMiddleware:
    """Middleware for automatic request logging"""
    
    def __init__(self, app_logger: ApplicationLogger):
        self.app_logger = app_logger
    
    async def log_request(self, request, call_next):
        """Log incoming requests"""
        start_time = datetime.now()
        
        # Extract user info from request if available
        user_id = None
        if hasattr(request, 'form'):
            form_data = await request.form()
            user_id = form_data.get('From')
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log successful request
            self.app_logger.performance.log_request(
                user_id=user_id or 'unknown',
                action=f"{request.method} {request.url.path}",
                duration_ms=duration,
                success=True,
                extra_data={
                    'status_code': response.status_code,
                    'method': request.method,
                    'path': request.url.path
                }
            )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log failed request
            error_id = self.app_logger.log_error(
                error=e,
                user_id=user_id,
                context={
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': duration
                }
            )
            
            self.app_logger.performance.log_request(
                user_id=user_id or 'unknown',
                action=f"{request.method} {request.url.path}",
                duration_ms=duration,
                success=False,
                extra_data={
                    'error_id': error_id,
                    'error_type': type(e).__name__
                }
            )
            
            raise

# Decorators for automatic logging
def log_performance(action_name: str = None):
    """Decorator to log function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            app_logger = ApplicationLogger()
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                app_logger.performance.log_request(
                    user_id=kwargs.get('user_id', 'system'),
                    action=action_name or func.__name__,
                    duration_ms=duration,
                    success=True
                )
                
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                
                error_id = app_logger.log_error(
                    error=e,
                    user_id=kwargs.get('user_id'),
                    context={
                        'function': func.__name__,
                        'duration_ms': duration
                    }
                )
                
                app_logger.performance.log_request(
                    user_id=kwargs.get('user_id', 'system'),
                    action=action_name or func.__name__,
                    duration_ms=duration,
                    success=False,
                    extra_data={'error_id': error_id}
                )
                
                raise
                
        return wrapper
    return decorator

def log_user_action(action_name: str):
    """Decorator to log user actions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            app_logger = ApplicationLogger()
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            
            try:
                result = func(*args, **kwargs)
                
                app_logger.log_user_action(
                    user_id=user_id,
                    action=action_name,
                    success=True,
                    details={'function': func.__name__}
                )
                
                return result
                
            except Exception as e:
                app_logger.log_user_action(
                    user_id=user_id,
                    action=action_name,
                    success=False,
                    details={
                        'function': func.__name__,
                        'error': str(e),
                        'error_type': type(e).__name__
                    }
                )
                
                raise
                
        return wrapper
    return decorator

# Example usage functions
def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name or 'app')

def get_app_logger() -> ApplicationLogger:
    """Get the main application logger"""
    return ApplicationLogger()

# Health check for logging
def test_logging():
    """Test all logging components"""
    try:
        app_logger = setup_logging(log_level='DEBUG', enable_json=False)
        
        # Test basic logging
        app_logger.app_logger.info("Testing basic logging")
        
        # Test performance logging
        app_logger.performance.log_request(
            user_id='test_user',
            action='test_action',
            duration_ms=123.45,
            success=True
        )
        
        # Test security logging
        app_logger.security.log_authentication_attempt(
            user_id='test_user',
            success=True,
            ip_address='127.0.0.1'
        )
        
        # Test error logging
        try:
            raise ValueError("Test error")
        except Exception as e:
            error_id = app_logger.log_error(e, user_id='test_user')
            print(f"Error logged with ID: {error_id}")
        
        print("✅ All logging tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False

if __name__ == "__main__":
    test_logging()
