"""Dispatch parsed commands to command modules."""

from commands.info import run_info


def handle_command(update: dict) -> None:
    text = update.get("text", "")
    if text.startswith("/info"):
        run_info(update)
