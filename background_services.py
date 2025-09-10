# background_services.py
"""
Background services for the baby log application
Handles reminder scheduling, cleanup tasks, and periodic maintenance
"""
import os
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database.operations import db_pool
from database_security import DatabaseSecurity
from tier_management import get_user_tier, increment_message_count
from send_twilio_message import send_twilio_message
from utils.logging_config import get_app_logger

app_logger = get_app_logger()

class ReminderScheduler:
    """Background scheduler for reminder notifications"""
    
    def __init__(self):
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.check_interval = 1800  # 30 minutes
        
    def start(self):
        """Start the reminder scheduler"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        app_logger.app_logger.info("Reminder scheduler started")
    
    def stop(self):
        """Stop the reminder scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        app_logger.app_logger.info("Reminder scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                self._check_and_send_reminders()
                time.sleep(self.check_interval)
            except Exception as e:
                app_logger.log_error(e, context={'function': 'scheduler_loop'})
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _check_and_send_reminders(self):
        """Check for due reminders and send notifications"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            user_col = DatabaseSecurity.get_user_column(database_url)
            reminder_table = DatabaseSecurity.validate_table_name('milk_reminders')
            
            # Get current time for comparison
            now = datetime.now()
            
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                
                # Get due reminders
                if database_url:
                    c.execute(f'''
                        SELECT * FROM {reminder_table} 
                        WHERE is_active=TRUE AND next_due <= %s
                        ORDER BY next_due ASC
                    ''', (now,))
                else:
                    c.execute(f'''
                        SELECT * FROM {reminder_table} 
                        WHERE is_active=1 AND next_due <= ?
                        ORDER BY next_due ASC
                    ''', (now,))
                
                due_reminders = c.fetchall()
            
            app_logger.app_logger.info(f"Found {len(due_reminders)} due reminders")
            
            for reminder in due_reminders:
                try:
                    self._process_reminder(reminder)
                except Exception as e:
                    app_logger.log_error(e, context={'function': 'process_reminder', 'reminder_id': reminder[0] if reminder else None})
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': '_check_and_send_reminders'})
    
    def _process_reminder(self, reminder):
        """Process a single reminder"""
        database_url = os.environ.get('DATABASE_URL')
        user_col = DatabaseSecurity.get_user_column(database_url)
        reminder_table = DatabaseSecurity.validate_table_name('milk_reminders')
        
        # Extract reminder data
        if database_url:
            user = reminder[user_col]
            reminder_id = reminder['id']
            reminder_name = reminder['reminder_name']
            interval = reminder['interval_hours']
            start_str = reminder['start_time']
            end_str = reminder['end_time']
            next_due = reminder['next_due']
        else:
            user = reminder[1]
            reminder_id = reminder[0]
            reminder_name = reminder[2]
            interval = reminder[3]
            start_str = reminder[4]
            end_str = reminder[5]
            next_due = reminder[8]
        
        # Check user's tier and message limits
        user_info = get_user_tier(user)
        
        # Check if within allowed time window
        current_time = datetime.now()
        if not self._time_in_range(start_str, end_str, current_time):
            send_this = False
            reason = "outside_time_window"
        elif user_info['tier'] == 'free' and user_info['messages_today'] >= 2:
            send_this = False
            reason = "daily_limit_reached"
        else:
            send_this = True
            reason = "sent"
        
        # Create reminder message
        remaining = 2 - user_info['messages_today'] if user_info['tier'] == 'free' else 'unlimited'
        
        message = f"""🍼 **Pengingat: {reminder_name}**

⏰ Waktunya minum susu!

🚀 **Respons cepat:**
• `done 120` - Catat 120ml
• `snooze 30` - Tunda 30 menit  
• `skip reminder` - Lewati

📊 Sisa pengingat hari ini: {remaining}"""

        if send_this:
            success = send_twilio_message(user, message)
            if success:
                app_logger.log_user_action(
                    user_id=user,
                    action='reminder_sent',
                    success=True,
                    details={
                        'reminder_id': reminder_id,
                        'reminder_name': reminder_name,
                        'time': current_time.strftime('%H:%M')
                    }
                )
                # Increment message count after successful send
                increment_message_count(user)
            else:
                app_logger.log_user_action(
                    user_id=user,
                    action='reminder_send_failed',
                    success=False,
                    details={
                        'reminder_id': reminder_id,
                        'reminder_name': reminder_name
                    }
                )
        else:
            app_logger.log_user_action(
                user_id=user,
                action='reminder_skipped',
                success=True,
                details={
                    'reminder_id': reminder_id,
                    'reason': reason,
                    'time': current_time.strftime('%H:%M')
                }
            )
        
        # Calculate next reminder time
        new_next_due = current_time + timedelta(hours=interval)
        
        # Check if new time is outside allowed window
        if not self._time_in_range(start_str, end_str, new_next_due):
            # Move to next day's start time
            next_start = (new_next_due + timedelta(days=1)).replace(
                hour=int(start_str[:2]), 
                minute=int(start_str[3:5]), 
                second=0, 
                microsecond=0
            )
            new_next_due = next_start
        
        # Update reminder in database
        try:
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                if database_url:
                    c.execute(f'''
                        UPDATE {reminder_table} 
                        SET next_due=%s, last_sent=%s 
                        WHERE id=%s
                    ''', (new_next_due, current_time, reminder_id))
                else:
                    c.execute(f'''
                        UPDATE {reminder_table} 
                        SET next_due=?, last_sent=? 
                        WHERE id=?
                    ''', (new_next_due, current_time, reminder_id))
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': 'update_reminder', 'reminder_id': reminder_id})
    
    def _time_in_range(self, start_str: str, end_str: str, check_time: datetime) -> bool:
        """Check if check_time is within start and end time range"""
        try:
            start_hour, start_minute = map(int, start_str.split(":"))
            end_hour, end_minute = map(int, end_str.split(":"))
            
            start_time = check_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            end_time = check_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            
            if start_time <= end_time:
                # Same day range
                return start_time <= check_time <= end_time
            else:
                # Over midnight range
                return check_time >= start_time or check_time <= end_time
                
        except Exception as e:
            app_logger.log_error(e, context={'function': '_time_in_range'})
            return True  # Default to allowing reminder if parsing fails

class CleanupService:
    """Background service for database and session cleanup"""
    
    def __init__(self):
        self.running = False
        self.cleanup_thread: Optional[threading.Thread] = None
        self.check_interval = 3600  # 1 hour
        
    def start(self):
        """Start the cleanup service"""
        if self.running:
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        app_logger.app_logger.info("Cleanup service started")
    
    def stop(self):
        """Stop the cleanup service"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        app_logger.app_logger.info("Cleanup service stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.running:
            try:
                self._perform_cleanup()
                time.sleep(self.check_interval)
            except Exception as e:
                app_logger.log_error(e, context={'function': 'cleanup_loop'})
                time.sleep(1800)  # Wait 30 minutes before retrying
    
    def _perform_cleanup(self):
        """Perform various cleanup tasks"""
        try:
            # Clean up expired sessions (handled by SessionManager)
            
            # Clean up old reminder logs (keep last 30 days)
            self._cleanup_old_reminder_logs()
            
            # Reset daily message counts if needed
            self._reset_daily_counts()
            
            # Clean up old incomplete sleep sessions (older than 24 hours)
            self._cleanup_incomplete_sleep_sessions()
            
            # Perform database maintenance
            self._database_maintenance()
            
            app_logger.app_logger.info("Cleanup tasks completed successfully")
            
        except Exception as e:
            app_logger.log_error(e, context={'function': '_perform_cleanup'})
    
    def _cleanup_old_reminder_logs(self):
        """Clean up old reminder logs"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            reminder_logs_table = DatabaseSecurity.validate_table_name('reminder_logs')
            cutoff_date = datetime.now() - timedelta(days=30)
            
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                if database_url:
                    c.execute(f'DELETE FROM {reminder_logs_table} WHERE timestamp < %s', (cutoff_date,))
                    deleted_count = c.rowcount
                else:
                    c.execute(f'DELETE FROM {reminder_logs_table} WHERE timestamp < ?', (cutoff_date,))
                    deleted_count = c.rowcount
                
                if deleted_count > 0:
                    app_logger.app_logger.info(f"Cleaned up {deleted_count} old reminder logs")
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': '_cleanup_old_reminder_logs'})
    
    def _reset_daily_counts(self):
        """Reset daily message counts for users if needed"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            user_col = DatabaseSecurity.get_user_column(database_url)
            user_tiers_table = DatabaseSecurity.validate_table_name('user_tiers')
            today = datetime.now().date()
            
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                if database_url:
                    c.execute(f'''
                        UPDATE {user_tiers_table} 
                        SET messages_today=0, last_reset=%s 
                        WHERE last_reset < %s
                    ''', (today, today))
                    updated_count = c.rowcount
                else:
                    c.execute(f'''
                        UPDATE {user_tiers_table} 
                        SET messages_today=0, last_reset=? 
                        WHERE last_reset < ?
                    ''', (today, today))
                    updated_count = c.rowcount
                
                if updated_count > 0:
                    app_logger.app_logger.info(f"Reset daily counts for {updated_count} users")
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': '_reset_daily_counts'})
    
    def _cleanup_incomplete_sleep_sessions(self):
        """Clean up old incomplete sleep sessions"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            sleep_table = DatabaseSecurity.validate_table_name('sleep_log')
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                if database_url:
                    c.execute(f'''
                        DELETE FROM {sleep_table} 
                        WHERE is_complete=FALSE AND created_at < %s
                    ''', (cutoff_time,))
                    deleted_count = c.rowcount
                else:
                    c.execute(f'''
                        DELETE FROM {sleep_table} 
                        WHERE is_complete=0 AND created_at < ?
                    ''', (cutoff_time,))
                    deleted_count = c.rowcount
                
                if deleted_count > 0:
                    app_logger.app_logger.info(f"Cleaned up {deleted_count} incomplete sleep sessions")
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': '_cleanup_incomplete_sleep_sessions'})
    
    def _database_maintenance(self):
        """Perform database maintenance tasks"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                # PostgreSQL maintenance
                with db_pool.get_connection() as conn:
                    c = conn.cursor()
                    # Update table statistics
                    c.execute('ANALYZE;')
                    app_logger.app_logger.info("PostgreSQL ANALYZE completed")
            else:
                # SQLite maintenance
                with db_pool.get_connection() as conn:
                    c = conn.cursor()
                    # Optimize database
                    c.execute('VACUUM;')
                    c.execute('ANALYZE;')
                    app_logger.app_logger.info("SQLite VACUUM and ANALYZE completed")
                    
        except Exception as e:
            app_logger.log_error(e, context={'function': '_database_maintenance'})

class HealthCheckService:
    """Background service for system health monitoring"""
    
    def __init__(self):
        self.running = False
        self.health_thread: Optional[threading.Thread] = None
        self.check_interval = 900  # 15 minutes
        
    def start(self):
        """Start the health check service"""
        if self.running:
            return
        
        self.running = True
        self.health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self.health_thread.start()
        
        app_logger.app_logger.info("Health check service started")
    
    def stop(self):
        """Stop the health check service"""
        self.running = False
        if self.health_thread:
            self.health_thread.join(timeout=5)
        
        app_logger.app_logger.info("Health check service stopped")
    
    def _health_loop(self):
        """Main health check loop"""
        while self.running:
            try:
                self._perform_health_checks()
                time.sleep(self.check_interval)
            except Exception as e:
                app_logger.log_error(e, context={'function': 'health_loop'})
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _perform_health_checks(self):
        """Perform system health checks"""
        try:
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'database': self._check_database_health(),
                'memory': self._check_memory_usage(),
                'disk': self._check_disk_usage(),
                'services': self._check_services_health()
            }
            
            # Log health status
            app_logger.app_logger.info(f"System health check: {health_status}")
            
            # Alert if critical issues found
            critical_issues = []
            if not health_status['database']['healthy']:
                critical_issues.append('Database connectivity issues')
            
            if health_status['memory']['usage_percent'] > 90:
                critical_issues.append('High memory usage')
            
            if health_status['disk']['usage_percent'] > 95:
                critical_issues.append('High disk usage')
            
            if critical_issues:
                app_logger.app_logger.error(f"Critical system issues detected: {critical_issues}")
                
        except Exception as e:
            app_logger.log_error(e, context={'function': '_perform_health_checks'})
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connection health"""
        try:
            start_time = datetime.now()
            
            with db_pool.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT 1')
                c.fetchone()
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'healthy': True,
                'response_time_ms': response_time,
                'pool_stats': db_pool.get_stats()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'response_time_ms': None
            }
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        """Check system memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            
            return {
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'usage_percent': memory.percent,
                'healthy': memory.percent < 85
            }
            
        except ImportError:
            return {
                'error': 'psutil not available',
                'healthy': True  # Assume healthy if can't check
            }
        except Exception as e:
            return {
                'error': str(e),
                'healthy': False
            }
    
    def _check_disk_usage(self) -> Dict[str, Any]:
        """Check disk usage"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            
            return {
                'total_gb': round(disk.total / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'usage_percent': round((disk.used / disk.total) * 100, 1),
                'healthy': (disk.used / disk.total) < 0.9
            }
            
        except ImportError:
            return {
                'error': 'psutil not available',
                'healthy': True  # Assume healthy if can't check
            }
        except Exception as e:
            return {
                'error': str(e),
                'healthy': False
            }
    
    def _check_services_health(self) -> Dict[str, Any]:
        """Check health of various services"""
        services = {
            'reminder_scheduler': reminder_scheduler.running if 'reminder_scheduler' in globals() else False,
            'cleanup_service': cleanup_service.running if 'cleanup_service' in globals() else False
        }
        
        # Check external service connectivity
        services.update({
            'twilio_connectivity': self._check_twilio_connectivity(),
            'openai_connectivity': self._check_openai_connectivity()
        })
        
        return {
            'services': services,
            'healthy': all(services.values())
        }
    
    def _check_twilio_connectivity(self) -> bool:
        """Check Twilio service connectivity"""
        try:
            # Simple connectivity check - don't send actual message
            import os
            from twilio.rest import Client
            
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not (account_sid and auth_token):
                return False
            
            client = Client(account_sid, auth_token)
            # Just validate credentials without sending
            account = client.api.accounts(account_sid).fetch()
            return account.status == 'active'
            
        except Exception:
            return False
    
    def _check_openai_connectivity(self) -> bool:
        """Check OpenAI service connectivity"""
        try:
            import os
            import openai
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False
            
            # Simple API test - just check if key is valid
            client = openai.OpenAI(api_key=api_key)
            # This is a minimal call to test connectivity
            models = client.models.list()
            return len(models.data) > 0
            
        except Exception:
            return False

# Global service instances
reminder_scheduler = ReminderScheduler()
cleanup_service = CleanupService()
health_check_service = HealthCheckService()

def start_reminder_scheduler():
    """Start the reminder scheduler service"""
    try:
        reminder_scheduler.start()
        app_logger.app_logger.info("Reminder scheduler service started successfully")
    except Exception as e:
        app_logger.log_error(e, context={'function': 'start_reminder_scheduler'})

def start_cleanup_service():
    """Start the cleanup service"""
    try:
        cleanup_service.start()
        app_logger.app_logger.info("Cleanup service started successfully")
    except Exception as e:
        app_logger.log_error(e, context={'function': 'start_cleanup_service'})

def start_health_check_service():
    """Start the health check service"""
    try:
        health_check_service.start()
        app_logger.app_logger.info("Health check service started successfully")
    except Exception as e:
        app_logger.log_error(e, context={'function': 'start_health_check_service'})

def start_all_background_services():
    """Start all background services"""
    try:
        start_reminder_scheduler()
        start_cleanup_service()
        start_health_check_service()
        
        app_logger.app_logger.info("All background services started successfully")
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'start_all_background_services'})

def stop_all_background_services():
    """Stop all background services"""
    try:
        reminder_scheduler.stop()
        cleanup_service.stop()
        health_check_service.stop()
        
        app_logger.app_logger.info("All background services stopped successfully")
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'stop_all_background_services'})

def get_services_status() -> Dict[str, Any]:
    """Get status of all background services"""
    try:
        return {
            'reminder_scheduler': {
                'running': reminder_scheduler.running,
                'check_interval': reminder_scheduler.check_interval
            },
            'cleanup_service': {
                'running': cleanup_service.running,
                'check_interval': cleanup_service.check_interval
            },
            'health_check_service': {
                'running': health_check_service.running,
                'check_interval': health_check_service.check_interval
            },
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        app_logger.log_error(e, context={'function': 'get_services_status'})
        return {'error': str(e)}

def manual_reminder_check():
    """Manually trigger reminder check (for testing/debugging)"""
    try:
        if reminder_scheduler.running:
            reminder_scheduler._check_and_send_reminders()
            return {'status': 'completed', 'timestamp': datetime.now().isoformat()}
        else:
            return {'status': 'scheduler_not_running'}
    except Exception as e:
        app_logger.log_error(e, context={'function': 'manual_reminder_check'})
        return {'status': 'error', 'error': str(e)}

def manual_cleanup():
    """Manually trigger cleanup tasks (for testing/debugging)"""
    try:
        if cleanup_service.running:
            cleanup_service._perform_cleanup()
            return {'status': 'completed', 'timestamp': datetime.now().isoformat()}
        else:
            return {'status': 'cleanup_service_not_running'}
    except Exception as e:
        app_logger.log_error(e, context={'function': 'manual_cleanup'})
        return {'status': 'error', 'error': str(e)}

def manual_health_check():
    """Manually trigger health check (for testing/debugging)"""
    try:
        if health_check_service.running:
            health_check_service._perform_health_checks()
            return {'status': 'completed', 'timestamp': datetime.now().isoformat()}
        else:
            return {'status': 'health_service_not_running'}
    except Exception as e:
        app_logger.log_error(e, context={'function': 'manual_health_check'})
        return {'status': 'error', 'error': str(e)}

# Service configuration
SERVICE_CONFIG = {
    'reminder_scheduler': {
        'check_interval_seconds': 1800,  # 30 minutes
        'enabled': True,
        'description': 'Checks for due reminders and sends notifications'
    },
    'cleanup_service': {
        'check_interval_seconds': 3600,  # 1 hour
        'enabled': True,
        'description': 'Performs database cleanup and maintenance tasks'
    },
    'health_check_service': {
        'check_interval_seconds': 900,   # 15 minutes
        'enabled': True,
        'description': 'Monitors system health and performance'
    }
}

# Utility function to configure services from environment variables
def configure_services_from_env():
    """Configure services based on environment variables"""
    try:
        # Configure reminder scheduler
        reminder_interval = int(os.getenv('REMINDER_CHECK_INTERVAL', 1800))
        reminder_scheduler.check_interval = reminder_interval
        
        # Configure cleanup service
        cleanup_interval = int(os.getenv('CLEANUP_CHECK_INTERVAL', 3600))
        cleanup_service.check_interval = cleanup_interval
        
        # Configure health check service
        health_interval = int(os.getenv('HEALTH_CHECK_INTERVAL', 900))
        health_check_service.check_interval = health_interval
        
        app_logger.app_logger.info(f"Services configured from environment: reminder={reminder_interval}s, cleanup={cleanup_interval}s, health={health_interval}s")
        
    except Exception as e:
        app_logger.log_error(e, context={'function': 'configure_services_from_env'})

# Initialize configuration on module import
configure_services_from_env()
