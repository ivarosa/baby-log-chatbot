from twilio.twiml.messaging_response import MessagingResponse
from fastapi import Response
import logging
import re

logger = logging.getLogger(__name__)

# Normalize common dash characters to simple hyphen
_DASH_NORMALIZER = re.compile(r"[–—‑\u2011]")

class GroupHandler:
    """Handle simple textual 'join <group>' commands via WhatsApp/Twilio."""

    def __init__(self, session_manager=None, logger_obj=None):
        self.session_manager = session_manager
        if logger_obj:
            self.logger = logger_obj
        else:
            self.logger = logger

    def _normalize_group_name(self, raw: str) -> str:
        if not raw:
            return ""
        s = raw.strip()
        s = _DASH_NORMALIZER.sub("-", s)
        # collapse multiple spaces
        s = re.sub(r"\s+", " ", s)
        return s

    def handle_join(self, user: str, group_name: str) -> Response:
        resp = MessagingResponse()
        try:
            normalized = self._normalize_group_name(group_name)
            if not normalized:
                resp.message("❌ Nama grup tidak ditemukan. Contoh: 'join shallow-arrow'")
                return Response(str(resp), media_type="application/xml")

            # Log the join request (temporary behavior)
            self.logger.info(f"Join requested: user={user}, group={normalized}")

            # Acknowledge in Indonesian
            resp.message(f"✅ Permintaan bergabung ke '{normalized}' telah diterima. Terima kasih.")
            return Response(str(resp), media_type="application/xml")
        except Exception as e:
            self.logger.exception("Error handling join command")
            resp.message("❌ Terjadi kesalahan saat memproses permintaan bergabung.")
            return Response(str(resp), media_type="application/xml")
