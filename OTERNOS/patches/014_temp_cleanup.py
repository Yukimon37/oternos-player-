"""
014_temp_cleanup.py — Clean up SC stream temp files on startup.
Deletes any tmp*.mp3 files in the system temp dir older than 1 hour.
"""
import os
import time
import tempfile
from pathlib import Path


def apply(app):
    try:
        tmp_dir = Path(tempfile.gettempdir())
        cutoff  = time.time() - 3600
        removed = 0
        for f in tmp_dir.glob("tmp*.mp3"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except Exception:
                pass
        if removed:
            try:
                from oternos.diagnostics import get_logger
                get_logger().info(f"Cleaned {removed} SC temp files")
            except Exception:
                pass
    except Exception:
        pass
