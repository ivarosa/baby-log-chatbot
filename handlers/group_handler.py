# handlers/group_handler.py
"""
GroupHandler - Handle group chat interactions for WhatsApp
Provides minimal functionality to handle 'join' commands in group contexts
"""

from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import save_group_user


class GroupHandler:
    """Handle group-related operations with minimal functionality"""

    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger

    def is_group_message(self, user: str) -> bool:
        """
        Check if the message is from a group chat.
        WhatsApp group messages typically have a different format.
        """
        # Group messages from WhatsApp via Twilio have identifiers that contain 'g.us'
        return 'g.us' in user if user else False

    def handle_join_command(self, user: str, message: str) -> Response:
        """
        Handle 'join' command from group chats.
        Allows users to opt-in to the service from group contexts.
        """
        resp = MessagingResponse()

        try:
            msg = message.lower().strip()

            # Check if this is a join command
            if msg not in ["join", "gabung", "/join"]:
                resp.message("❓ Gunakan 'join' untuk mendaftar dari grup.")
                return Response(str(resp), media_type="application/xml")

            # Check if it's from a group
            if not self.is_group_message(user):
                resp.message("ℹ️ Perintah 'join' hanya untuk grup WhatsApp. Ketik 'start' untuk memulai.")
                return Response(str(resp), media_type="application/xml")

            # Register the user from group context
            success = self._register_group_user(user)

            if success:
                reply = (
                    "✅ Selamat datang di Baby Log!\n\n"
                    "Untuk privasi, saya akan balas di chat pribadi.\n"
                    "Silakan chat saya langsung untuk mulai mencatat aktivitas bayi Anda.\n\n"
                    "Ketik 'start' di chat pribadi untuk memulai!"
                )
            else:
                reply = "✅ Anda sudah terdaftar! Chat saya di pribadi untuk menggunakan layanan."

            resp.message(reply)
            self.logger.info(f"Group join handled for {user[:30]}...")

        except Exception as e:
            self.logger.error(f"Error handling join command: {e}", exc_info=True)
            resp.message("❌ Terjadi kesalahan. Silakan coba lagi.")

        return Response(str(resp), media_type="application/xml")

    def _register_group_user(self, user: str) -> bool:
        """
        Register a user who joined from a group.
        Returns True if newly registered, False if already exists.
        """
        try:
            # Save to database that this user joined from a group
            result = save_group_user(user)
            return result
        except Exception as e:
            self.logger.error(f"Failed to register group user: {e}")
            return False

    def handle_group_message(self, user: str, message: str) -> Response:
        """
        Handle general messages from group chats.
        Redirects users to use private chat for privacy.
        """
        resp = MessagingResponse()

        try:
            # For any other message from group, inform them to use private chat
            reply = (
                "👋 Halo! Untuk privasi data bayi Anda, "
                "silakan chat saya secara pribadi.\n\n"
                "Ketik 'join' untuk mendaftar, "
                "lalu chat saya di pribadi untuk mulai mencatat."
            )
            resp.message(reply)
            self.logger.info(f"Group message redirected for {user[:30]}...")

        except Exception as e:
            self.logger.error(f"Error handling group message: {e}", exc_info=True)
            resp.message("Silakan chat saya secara pribadi untuk menggunakan layanan.")

        return Response(str(resp), media_type="application/xml")
