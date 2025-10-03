"""
Medication & Vitamin Reminder Feature

Implements medication/vitamin reminder management, logging, and user interaction flow for a chatbot.
Intended for integration with session management, background scheduler, and database.

Author: ivarosa
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Constants (can be moved to constants.py)
MEDICATION_TYPES = {
    'vitamin': '💊 Vitamin/Suplemen',
    'medicine': '🏥 Obat',
    'supplement': '🌿 Suplemen Herbal'
}

FREQUENCY_TYPES = {
    'daily': 'Setiap hari',
    'weekly': 'Mingguan',
    'custom': 'Interval khusus',
    'prn': 'Bila perlu'
}

MEDICATION_HELP_MESSAGE = """
🏥 **Pengingat Obat & Vitamin**

**Setup Pengingat:**
• `set reminder obat` - Atur pengingat obat
• `set reminder vitamin` - Atur pengingat vitamin

**Respons Cepat:**
• `taken [nama]` - Sudah diminum
• `skip medication` - Lewati kali ini
• `snooze [menit]` - Tunda

**Riwayat:**
• `lihat obat` - Daftar obat aktif
• `riwayat obat` - Riwayat 7 hari

**Kelola:**
• `stop medication [nama]` - Nonaktifkan
• `delete medication [nama]` - Hapus
"""

class MedicationHandler:
    """Handles medication and vitamin reminders, logging, and user flows."""
    
    def __init__(self, session_manager, logger, db_ops, scheduler):
        self.session_manager = session_manager
        self.logger = logger
        self.db_ops = db_ops
        self.scheduler = scheduler

    def handle_medication_commands(self, user: str, message: str, background_tasks) -> str:
        """Main router for medication-related commands."""
        msg = message.lower().strip()
        if msg in ["set reminder obat", "atur pengingat obat"]:
            return self.handle_medication_setup(user)
        elif msg in ["set reminder vitamin", "atur pengingat vitamin"]:
            return self.handle_vitamin_setup(user)
        elif msg in ["show medication", "lihat obat"]:
            return self.handle_show_medications(user)
        elif msg.startswith("taken "):
            return self.handle_medication_taken(user, msg)
        elif msg.startswith("skip medication"):
            return self.handle_medication_skip(user, msg)
        elif msg in ["riwayat obat", "medication history"]:
            return self.handle_medication_history(user)
        else:
            return self._handle_unknown_medication_command(user, msg)

    def handle_medication_setup(self, user: str) -> str:
        """
        Starts medication reminder setup flow.
        States: MED_NAME -> MED_TYPE -> MED_DOSAGE -> MED_FREQUENCY -> MED_TIMES -> MED_START -> MED_DURATION -> MED_CONFIRM
        """
        # Example implementation: In practice, use session state to manage multi-turn
        return (
            "🏥 Setup Pengingat Obat\n\n"
            "Nama obat?\n(contoh: Paracetamol)"
        )

    def handle_vitamin_setup(self, user: str) -> str:
        """Starts vitamin reminder setup flow."""
        return (
            "💊 Setup Pengingat Vitamin\n\n"
            "Nama vitamin/suplemen?\n(contoh: Vitamin D)"
        )

    def handle_show_medications(self, user: str) -> str:
        """Displays current active medication/vitamin reminders."""
        reminders = self.db_ops.get_medication_reminders(user)
        if not reminders:
            return "Tidak ada pengingat obat/vitamin aktif."
        lines = ["💊 Pengingat Obat/Vitamin Aktif:"]
        for r in reminders:
            lines.append(
                f"- {r['medication_name']} ({r['medication_type']}), {r['dosage']}, {r['frequency']}, {', '.join(r.get('specific_times', []))}, Mulai: {r['start_date']}"
            )
        return "\n".join(lines)

    def handle_medication_taken(self, user: str, msg: str) -> str:
        """
        Handles 'taken [medication_name]' quick response.
        Logs intake, updates next reminder time.
        """
        parts = msg.split(" ", 1)
        if len(parts) < 2:
            return "Format salah. Gunakan: `taken [nama obat/vitamin]`"
        medication_name = parts[1]
        reminder = self.db_ops.get_medication_reminder_by_name(user, medication_name)
        if not reminder:
            return f"Tidak ditemukan pengingat untuk '{medication_name}'."
        now = datetime.now()
        log_data = {
            "user": user,
            "reminder_id": reminder['id'],
            "medication_name": medication_name,
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
            "dosage": reminder['dosage'],
            "taken": True,
            "notes": ""
        }
        self.db_ops.log_medication_intake(user, log_data)
        # Update reminder's next_due (simple: +interval or next time)
        self.db_ops.update_next_due(reminder['id'])
        return f"✅ Dicatat: {medication_name} sudah diminum."

    def handle_medication_skip(self, user: str, msg: str) -> str:
        """Handles 'skip medication' quick response."""
        # Optionally parse medication name
        reminder = self.db_ops.get_next_due_medication(user)
        if not reminder:
            return "Tidak ada pengingat obat/vitamin yang harus diminum saat ini."
        now = datetime.now()
        log_data = {
            "user": user,
            "reminder_id": reminder['id'],
            "medication_name": reminder['medication_name'],
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
            "dosage": reminder['dosage'],
            "taken": False,
            "notes": "Lewati"
        }
        self.db_ops.log_medication_intake(user, log_data)
        self.db_ops.update_next_due(reminder['id'])
        return f"⏭️ Dicatat: {reminder['medication_name']} dilewati kali ini."

    def handle_medication_history(self, user: str, days: int = 7) -> str:
        """Shows medication/vitamin intake history, adherence summary."""
        history = self.db_ops.get_medication_history(user, days)
        if not history:
            return "Belum ada riwayat obat/vitamin."
        adherence = self.db_ops.calculate_adherence_rate(user, days)
        lines = ["📊 Riwayat Obat/Vitamin (7 hari terakhir)"]
        for med_name, stats in adherence.items():
            lines.append(
                f"💊 {med_name}\n"
                f"• Total dijadwalkan: {stats['total_scheduled']}\n"
                f"• Diminum: {stats['total_taken']}\n"
                f"• Dilewati: {stats['total_skipped']}\n"
                f"• Tingkat kepatuhan: {stats['adherence_rate']}%\n"
            )
        return "\n".join(lines)

    def _handle_unknown_medication_command(self, user: str, msg: str) -> str:
        """Handles unknown medication commands."""
        return (
            "Perintah tidak dikenali.\n\n"
            + MEDICATION_HELP_MESSAGE
        )


# Example DB Operations interface (to be implemented elsewhere)
class MedicationDBOps:
    def get_medication_reminders(self, user: str) -> List[Dict[str, Any]]:
        pass
    def get_medication_reminder_by_name(self, user: str, name: str) -> Optional[Dict[str, Any]]:
        pass
    def log_medication_intake(self, user: str, data: Dict[str, Any]) -> None:
        pass
    def update_next_due(self, reminder_id: int) -> None:
        pass
    def get_next_due_medication(self, user: str) -> Optional[Dict[str, Any]]:
        pass
    def get_medication_history(self, user: str, days: int = 7) -> List[Dict[str, Any]]:
        pass
    def calculate_adherence_rate(self, user: str, days: int = 7) -> Dict[str, Dict[str, Any]]:
        pass

# This file is ready for integration with your main routing, session, and background scheduler.
# You can expand states, flows, and add new features (e.g. refill alerts, smart warnings) as needed.
