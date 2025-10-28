# utils/message_optimizer.py
"""
Message batching and optimization to reduce Twilio costs
"""
from datetime import datetime, timedelta
from typing import List, Dict
import logging

class MessageOptimizer:
    """Optimize outgoing messages to reduce costs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pending_messages = {}  # {user: [messages]}
        self.batch_window = 5  # seconds to wait for batching
    
    def should_batch_message(self, user: str, message: str) -> bool:
        """Determine if message should be batched or sent immediately"""
        # Immediate send for critical messages
        critical_keywords = ["error", "❌", "gagal", "failed"]
        if any(keyword in message.lower() for keyword in critical_keywords):
            return False
        
        # Batch informational messages
        return True
    
    def consolidate_messages(self, messages: List[str]) -> str:
        """Combine multiple messages into one"""
        if len(messages) == 1:
            return messages[0]
        
        # Remove duplicate sections
        unique_sections = []
        seen_content = set()
        
        for msg in messages:
            # Extract main content (remove emojis/formatting for dedup)
            clean_content = ''.join(c for c in msg if c.isalnum() or c.isspace())
            if clean_content not in seen_content:
                unique_sections.append(msg)
                seen_content.add(clean_content)
        
        # Combine with separators
        return "\n\n---\n\n".join(unique_sections)
    
    def optimize_summary_messages(self, data: Dict) -> str:
        """Create concise summary messages"""
        # Instead of multiple messages, create ONE comprehensive message
        lines = ["📊 **Ringkasan Lengkap**\n"]
        
        if data.get('mpasi', {}).get('count', 0) > 0:
            lines.append(f"🍽️ MPASI: {data['mpasi']['count']}x, {data['mpasi']['total_ml']}ml")
        
        if data.get('milk', {}).get('count', 0) > 0:
            lines.append(f"🍼 Susu: {data['milk']['count']}x, {data['milk']['total_ml']}ml")
        
        if data.get('sleep', {}).get('sessions', 0) > 0:
            hours, mins = divmod(int(data['sleep']['total_minutes']), 60)
            lines.append(f"😴 Tidur: {data['sleep']['sessions']}x, {hours}j{mins}m")
        
        # Single consolidated message instead of 3-4 separate messages
        return "\n".join(lines)


class ReminderBatcher:
    """Batch multiple reminders into single messages"""
    
    def __init__(self):
        self.pending_reminders = {}  # {user: [(reminder_name, time)]}
    
    def add_reminder(self, user: str, reminder_name: str, time: str):
        """Add reminder to batch"""
        if user not in self.pending_reminders:
            self.pending_reminders[user] = []
        self.pending_reminders[user].append((reminder_name, time))
    
    def get_batched_message(self, user: str) -> str:
        """Get single message for all pending reminders"""
        reminders = self.pending_reminders.get(user, [])
        if not reminders:
            return None
        
        if len(reminders) == 1:
            name, time = reminders[0]
            return f"🔔 **Pengingat:** {name}\n⏰ {time}"
        
        # Multiple reminders in ONE message
        msg = "🔔 **Pengingat-pengingat Anda:**\n\n"
        for i, (name, time) in enumerate(reminders, 1):
            msg += f"{i}. {name} - {time}\n"
        
        msg += "\n💡 Ketik 'done' untuk tandai selesai"
        
        # Clear batch after creating message
        self.pending_reminders[user] = []
        
        return msg


class ResponseOptimizer:
    """Optimize responses to be more concise"""
    
    @staticmethod
    def shorten_confirmations(message: str) -> str:
        """Make confirmations shorter"""
        # Remove excessive formatting and redundant info
        replacements = {
            "✅ **Konfirmasi Data Anak:**\n\n": "✅ ",
            "Apakah data sudah benar? (ya/ulang/batal)": "(ya/ulang/batal)",
            "**Contoh:**\n": "",
            "💡 **Tips:**\n": "💡 ",
        }
        
        for old, new in replacements.items():
            message = message.replace(old, new)
        
        return message
    
    @staticmethod
    def remove_redundant_help(message: str) -> str:
        """Remove help text that's repeated too often"""
        # Don't send full help on every error
        if "Ketik 'help' untuk bantuan lengkap." in message:
            # Only keep if it's a genuinely unknown command
            return message
        
        return message


# Integration example
class OptimizedMessageSender:
    """Wrapper for sending optimized messages"""
    
    def __init__(self):
        self.optimizer = MessageOptimizer()
        self.response_optimizer = ResponseOptimizer()
    
    def prepare_message(self, user: str, message: str, message_type: str = "normal") -> str:
        """Prepare message for sending with optimizations"""
        
        # Step 1: Shorten confirmations
        message = self.response_optimizer.shorten_confirmations(message)
        
        # Step 2: Remove redundant help text
        message = self.response_optimizer.remove_redundant_help(message)
        
        # Step 3: Consolidate if batching
        if self.optimizer.should_batch_message(user, message):
            # Add to batch and return None (will send later)
            if user not in self.optimizer.pending_messages:
                self.optimizer.pending_messages[user] = []
            self.optimizer.pending_messages[user].append(message)
            return None  # Don't send yet
        
        return message
    
    def get_cost_savings_estimate(self, original_msg_count: int, optimized_msg_count: int) -> Dict:
        """Calculate cost savings"""
        cost_per_msg = 0.005  # $0.005 per Twilio message
        
        original_cost = original_msg_count * cost_per_msg
        optimized_cost = optimized_msg_count * cost_per_msg
        savings = original_cost - optimized_cost
        savings_percent = (savings / original_cost * 100) if original_cost > 0 else 0
        
        return {
            "original_messages": original_msg_count,
            "optimized_messages": optimized_msg_count,
            "messages_saved": original_msg_count - optimized_msg_count,
            "original_cost": f"${original_cost:.2f}",
            "optimized_cost": f"${optimized_cost:.2f}",
            "savings": f"${savings:.2f}",
            "savings_percent": f"{savings_percent:.1f}%"
        }


# Usage in your handlers:
"""
# In main.py or handlers:
message_optimizer = OptimizedMessageSender()

# Before sending:
optimized_message = message_optimizer.prepare_message(user, reply, "confirmation")

if optimized_message:  # Only send if not batched
    resp.message(optimized_message)
"""
