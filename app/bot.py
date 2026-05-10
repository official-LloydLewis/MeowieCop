"""Main bot loop and update routing."""

from app.lifecycle import startup, shutdown
from handlers.message_handler import handle_update


def run_bot() -> None:
    """Start bot lifecycle and process updates."""
    startup()
    try:
        # TODO: replace with Bale update polling loop.
        sample_update = {"type": "message", "text": "/info"}
        handle_update(sample_update)
    finally:
        shutdown()
