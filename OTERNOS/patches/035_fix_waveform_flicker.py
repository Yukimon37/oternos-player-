"""
035_fix_waveform_flicker.py — Hide waveform scope until data is loaded.
Shows a clean empty state instead of flickering during the 5s decode delay.
"""
import types


def apply(app):
    # Wrap _do_load_track to hide scope immediately on track click
    _orig = app._do_load_track

    def _patched(track, user_initiated=False):
        try:
            app._waveform_scope.pack_forget()
        except Exception:
            pass
        _orig(track, user_initiated=user_initiated)

    app._do_load_track = _patched

    # Poll to show scope when data is ready
    def _check():
        try:
            wf_data = getattr(app, '_waveform_data', None)
            if wf_data is not None:
                try:
                    app._waveform_scope.pack(fill='x', pady=(0, 2))
                except Exception:
                    pass
        except Exception:
            pass
        app.root.after(200, _check)

    app.root.after(200, _check)
