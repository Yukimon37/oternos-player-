import unittest

from oternos.core.playback import PlaybackController, PlaybackState


class FakeEngine:
    def __init__(self):
        self.duration = 123.0
        self.volume = 0.5
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self.calls = []

    def load(self, path):
        self.calls.append(("load", path))
        return True

    def play(self, start_ms=0):
        self.calls.append(("play", start_ms))
        self.is_playing = True
        self.is_paused = False
        self.position = start_ms / 1000.0
        return True

    def pause(self):
        self.calls.append(("pause",))
        self.is_playing = False
        self.is_paused = True

    def unpause(self):
        self.calls.append(("unpause",))
        self.is_playing = True
        self.is_paused = False

    def stop(self):
        self.calls.append(("stop",))
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0

    def seek(self, pos_s):
        self.calls.append(("seek", pos_s))
        self.position = pos_s

    def get_position(self):
        return self.position

    def set_volume(self, vol):
        self.calls.append(("set_volume", vol))
        self.volume = vol


class PlaybackTests(unittest.TestCase):
    def test_controller_delegates_commands(self):
        engine = FakeEngine()
        playback = PlaybackController(engine)

        self.assertTrue(playback.load("song.mp3"))
        self.assertTrue(playback.play(start_ms=5000))
        playback.pause()
        playback.resume()
        playback.seek(12.5)
        playback.set_volume(0.75)
        playback.stop()

        self.assertEqual(
            engine.calls,
            [
                ("load", "song.mp3"),
                ("play", 5000),
                ("pause",),
                ("unpause",),
                ("seek", 12.5),
                ("set_volume", 0.75),
                ("stop",),
            ],
        )

    def test_state_snapshot(self):
        engine = FakeEngine()
        playback = PlaybackController(engine)
        playback.play(start_ms=7000)
        playback.set_volume(0.25)

        state = playback.state()

        self.assertIsInstance(state, PlaybackState)
        self.assertTrue(state.is_playing)
        self.assertFalse(state.is_paused)
        self.assertEqual(state.position, 7.0)
        self.assertEqual(state.duration, 123.0)
        self.assertEqual(state.volume, 0.25)


if __name__ == "__main__":
    unittest.main()

