"""Info/help command."""

from app.api import send_message


def run_info(update: dict) -> None:
    chat_id = str(update.get("chat_id", "0"))
    send_message(chat_id, "MoewieCop v0.1.0")
