"""
diagnostics.py — lightweight logging + safe-call helpers.

Goal: replace silent failures with a rotating log file and optional UI notifications.
Must remain stdlib-only and PyInstaller-safe.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import traceback
from typing import Any, Callable, Optional


_LOGGER: Optional[logging.Logger] = None


def get_log_path() -> Path:
    return Path.home() / ".voidplayer.log"


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("oternos")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers when modules reload.
    if not logger.handlers:
        log_path = get_log_path()
        handler = RotatingFileHandler(
            log_path,
            maxBytes=512 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    _LOGGER = logger
    return logger


def set_debug(enabled: bool) -> None:
    logger = get_logger()
    logger.setLevel(logging.DEBUG if enabled else logging.INFO)


def log_exception(context: str, exc: BaseException) -> None:
    logger = get_logger()
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("%s\n%s", context, tb)


def safe_call(
    context: str,
    fn: Callable[[], Any],
    *,
    on_error: Optional[Callable[[str], None]] = None,
    default: Any = None,
) -> Any:
    """
    Run fn; on exception, log and optionally report to UI via on_error(msg).
    Returns default on failure.
    """
    try:
        return fn()
    except Exception as exc:
        log_exception(context, exc)
        if on_error is not None:
            try:
                on_error(context)
            except Exception:
                # Last resort: avoid cascading failures from UI error reporting.
                pass
        return default

