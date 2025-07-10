import os
from twilio.rest import Client
import logging

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

def send_twilio_message(to_number: str, message: str):
    """
    Sends a WhatsApp message using the Twilio API.

    Args:
        to_number (str): Recipient's WhatsApp number (e.g. 'whatsapp:+628123456789')
        message (str): Message content

    Returns:
        The sent message SID if successful, None otherwise.
    """
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER):
        logging.error("Twilio credentials are not set in environment variables.")
        return None

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            body=message,
            to=to_number
        )
        logging.info(f"Sent WhatsApp message to {to_number}: {message}")
        return msg.sid
    except Exception as e:
        logging.exception(f"Failed to send WhatsApp message to {to_number}: {e}")
        return None
