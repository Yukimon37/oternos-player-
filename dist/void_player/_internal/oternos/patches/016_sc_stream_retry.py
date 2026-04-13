"""
016_sc_stream_retry.py — NO-OP.

Retry logic is now handled directly inside 004_fix_sc_stream.py.
This patch is kept so the filename slot is occupied and no old version
of this file can accidentally load and re-wrap _sc_stream.
"""


def apply(app):
    pass  # retry is built into 004_fix_sc_stream
