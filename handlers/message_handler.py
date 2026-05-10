"""Primary update dispatcher."""

from handlers.command_handler import handle_command


def handle_update(update: dict) -> None:
    text = update.get("text", "")
    if text.startswith("/"):
        handle_command(update)
