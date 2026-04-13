"""
diagnostics.py — OTERNOS PLAYER
Compatibility shim: diagnostics.py was merged into utils.py.
All existing `from oternos.diagnostics import ...` imports continue to work.
"""

from .utils import (  # noqa: F401  (re-exported on purpose)
    get_logger,
    get_log_path,
    set_debug,
    log_exception,
    safe_call,
)
