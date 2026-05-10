"""Startup/shutdown hooks."""

from app.logger import setup_logger
from core.scheduler import start_scheduler, stop_scheduler

logger = setup_logger()


def startup() -> None:
    logger.info("Starting MoewieCop")
    start_scheduler()


def shutdown() -> None:
    logger.info("Stopping MoewieCop")
    stop_scheduler()
