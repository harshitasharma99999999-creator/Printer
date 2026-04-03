import os
import requests

from config import get_verbose
from status import warning, success


class WhatsApp:
    """
    WhatsApp Business Cloud API broadcast.
    Free tier: 1,000 conversations/month.
    Recipients must have opted in (saved your number + messaged you first).
    """

    BASE = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        self.access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
        # Comma-separated recipient numbers: +919876543210,+911234567890
        raw = os.environ.get("WHATSAPP_RECIPIENTS", "").strip()
        self.recipients = [n.strip() for n in raw.split(",") if n.strip()]

    def broadcast(self, message: str) -> int:
        """Send text message to all opted-in recipients. Returns count of successful sends."""
        if not self.phone_number_id or not self.access_token:
            if get_verbose():
                warning("WhatsApp: WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN not set — skipping.")
            return 0

        if not self.recipients:
            if get_verbose():
                warning("WhatsApp: WHATSAPP_RECIPIENTS not set — skipping. Add comma-separated numbers.")
            return 0

        sent = 0
        for recipient in self.recipients:
            # Normalize: remove + and spaces
            to = recipient.replace("+", "").replace(" ", "").replace("-", "")
            try:
                r = requests.post(
                    f"{self.BASE}/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "text",
                        "text": {"body": message[:4096]},
                    },
                    timeout=15,
                )
                if r.ok:
                    sent += 1
                    if get_verbose():
                        success(f"WhatsApp: sent to {recipient}")
                else:
                    if get_verbose():
                        warning(f"WhatsApp: failed to {recipient}: {r.status_code} {r.text[:100]}")
            except Exception as e:
                if get_verbose():
                    warning(f"WhatsApp: {e}")

        return sent
