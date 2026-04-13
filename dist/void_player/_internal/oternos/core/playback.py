"""
playback.py - thin UI-independent adapter around the audio engine.

Phase 1D intentionally keeps this as a small wrapper. The legacy Tkinter app
still owns track selection, UI updates, crossfade, EQ swap, and source-specific
behavior. Future UI shells can begin depending on this controller shape instead
of reaching straight into pygame-backed engine methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AudioEngineLike(Protocol):
    duration: float
    volume: float
    is_playing: bool
    is_paused: bool

    def load(self, path): ...
    def play(self, start_ms=0): ...
    def pause(self): ...
    def unpause(self): ...
    def stop(self): ...
    def seek(self, pos_s): ...
    def get_position(self): ...
    def set_volume(self, vol): ...


@dataclass(frozen=True)
class PlaybackState:
    is_playing: bool
    is_paused: bool
    position: float
    duration: float
    volume: float


class PlaybackController:
    """Small adapter for playback commands and state snapshots."""

    def __init__(self, engine: AudioEngineLike):
        self.engine = engine

    def load(self, path) -> bool:
        return bool(self.engine.load(path))

    def play(self, start_ms: int = 0) -> bool:
        return bool(self.engine.play(start_ms=start_ms))

    def pause(self) -> None:
        self.engine.pause()

    def resume(self) -> None:
        self.engine.unpause()

    def stop(self) -> None:
        self.engine.stop()

    def seek(self, pos_s: float) -> None:
        self.engine.seek(pos_s)

    def set_volume(self, vol: float) -> None:
        self.engine.set_volume(vol)

    def state(self) -> PlaybackState:
        return PlaybackState(
            is_playing=bool(self.engine.is_playing),
            is_paused=bool(self.engine.is_paused),
            position=float(self.engine.get_position()),
            duration=float(self.engine.duration),
            volume=float(self.engine.volume),
        )

