"""
Logging utilities for the agent.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(
    name: str = "lis-agent",
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """
    Set up logging with Rich formatting.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional file to write logs to

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Rich handler for console
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger
_logger = setup_logging()


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(name)
    return _logger


def log_thought(step: str, content: str) -> None:
    """Log an agent thought step (for debugging/analysis)."""
    _logger.debug(f"[{step}] {content}")


def log_action(action_type: str, description: str, result: str | None = None) -> None:
    """Log an agent action."""
    msg = f"[ACTION] {action_type}: {description}"
    if result:
        msg += f" → {result}"
    _logger.info(msg)


def log_memory_update(file_type: str, operation: str, content_preview: str) -> None:
    """Log a memory update operation."""
    _logger.info(
        f"[MEMORY] {file_type}.{operation}: "
        f"{content_preview[:50]}{'...' if len(content_preview) > 50 else ''}"
    )
