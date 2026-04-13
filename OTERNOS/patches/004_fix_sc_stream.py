"""
004_fix_sc_stream.py — NO-OP.

SoundCloud streaming is now handled in the main source module
`oternos.mixins.soundcloud_mixin`. This patch used to replace `_sc_stream()`
at runtime, but that override now conflicts with newer fixes and can leave the
UI stuck on stale buffering text / stale track metadata.
"""


def apply(app):
    pass
