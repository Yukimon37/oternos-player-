"""
999_fix_freeze.py — Fix library track freeze.

The _decode_waveform thread inside _do_load_track reads the entire audio
file while pygame is also reading it — disk I/O collision causes the freeze.

Simplest safe fix: after _do_load_track runs, sleep 5 seconds in a background
thread then manually set _waveform_data by re-running the decode.
We prevent the original decode from setting data by clearing _waveform_data
immediately after _do_load_track returns, then set it ourselves after 5s.
"""
import threading
import time


def apply(app):
    _orig = app._do_load_track

    def _patched(track, user_initiated=False):
        path = track.get('path', '')

        _orig(track, user_initiated=user_initiated)

        # Clear whatever _waveform_data the decode thread may have set
        # (it runs async so may not have set it yet — that's fine too)
        app._waveform_data = None

        # Re-decode after 5 seconds in background
        def _delayed_decode(p=path):
            time.sleep(5)
            # Only decode if this track is still playing
            if getattr(app, '_current_play_path', '') != p:
                return
            try:
                import wave, struct
                with wave.open(p, 'rb') as wf:
                    n_frames = wf.getnframes()
                    n_ch = wf.getnchannels()
                    sw = wf.getsampwidth()
                    raw = wf.readframes(n_frames)
                fmt = {1:'b', 2:'h', 4:'i'}.get(sw, 'h')
                samples = struct.unpack(f'{len(raw)//sw}{fmt}', raw)
                if n_ch > 1:
                    samples = samples[::n_ch]
                N = 300
                chunk = max(1, len(samples)//N)
                peak = max(abs(s) for s in samples) or 1
                pts = [max(abs(s) for s in samples[i*chunk:(i+1)*chunk])/peak
                       for i in range(N) if samples[i*chunk:(i+1)*chunk]]
                if getattr(app, '_current_play_path', '') == p:
                    app.root.after(0, lambda d=pts: setattr(app, '_waveform_data', d))
            except Exception:
                try:
                    import soundfile as _sf
                    data, sr = _sf.read(p, always_2d=True)
                    mono = data[:,0]; N=300
                    chunk = max(1, len(mono)//N)
                    peak = max(abs(mono)) or 1.0
                    pts = [float(max(abs(mono[i*chunk:(i+1)*chunk]))/peak) for i in range(N)]
                    if getattr(app, '_current_play_path', '') == p:
                        app.root.after(0, lambda d=pts: setattr(app, '_waveform_data', d))
                except Exception:
                    pass

        threading.Thread(target=_delayed_decode, daemon=True).start()

    app._do_load_track = _patched
