"""Background tasks scheduler placeholders."""

_running = False


def start_scheduler() -> None:
    global _running
    _running = True


def stop_scheduler() -> None:
    global _running
    _running = False
