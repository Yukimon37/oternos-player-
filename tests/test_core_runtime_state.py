import tempfile
import time
import unittest
from pathlib import Path

from oternos.core.runtime_state import (
    load_runtime_snapshot,
    runtime_file_marker,
    write_runtime_snapshot,
)


class RuntimeStateTests(unittest.TestCase):
    def test_missing_runtime_file_returns_offline_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = load_runtime_snapshot(Path(tmp) / "runtime.json")

        self.assertFalse(snapshot.data_file_exists)
        self.assertFalse(snapshot.is_live)
        self.assertEqual(snapshot.source, "none")
        self.assertIsNone(snapshot.track)

    def test_write_and_load_live_runtime_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "runtime.json"
            write_runtime_snapshot(
                {
                    "source": "library",
                    "status": "PLAYING",
                    "is_playing": True,
                    "is_paused": False,
                    "position": 42,
                    "duration": 180,
                    "volume": 0.75,
                    "track": {
                        "title": "Nocturne Drive",
                        "artist": "Ikari",
                        "album": "Void Tape",
                        "source": "Local Library",
                        "path": "C:/music/nocturne.mp3",
                        "art_path": "C:/covers/nocturne.png",
                        "art_url": "",
                    },
                    "queue_count": 3,
                    "manual_queue_count": 1,
                    "queue_position": 1,
                    "queue_paths": [
                        "C:/music/nocturne.mp3",
                        "C:/music/glass.mp3",
                    ],
                    "visualizer_bars": [0.0, 0.25, 1.5, "bad"],
                    "source_status": {
                        "source": "youtube",
                        "query": "night drive",
                        "result_count": 12,
                        "status": "12 results  --  double-click to play",
                    },
                    "source_results": [
                        {
                            "title": "Night Drive Mix",
                            "artist": "Ikari Channel",
                            "source": "YouTube",
                            "duration": "4:12",
                            "art_url": "https://example.test/night.jpg",
                        }
                    ],
                    "queue_preview": [
                        {
                            "position": 1,
                            "is_current": True,
                            "title": "Nocturne Drive",
                            "artist": "Ikari",
                            "album": "Void Tape",
                            "source": "Local Library",
                            "path": "C:/music/nocturne.mp3",
                            "art_path": "C:/covers/nocturne.png",
                        },
                        {
                            "position": 2,
                            "is_current": False,
                            "title": "Glass City Rain",
                            "artist": "Local",
                            "source": "Local Library",
                            "art_url": "https://example.test/glass.jpg",
                        },
                    ],
                    "last_command": {
                        "id": "cmd-1",
                        "action": "play_library_path",
                        "ok": True,
                        "message": "PLAY HANDLED",
                        "handled_at": time.time(),
                    },
                },
                data_path,
            )

            snapshot = load_runtime_snapshot(data_path)

        self.assertTrue(snapshot.data_file_exists)
        self.assertTrue(snapshot.is_live)
        self.assertTrue(snapshot.is_playing)
        self.assertEqual(snapshot.position, 42)
        self.assertEqual(snapshot.duration, 180)
        self.assertEqual(snapshot.volume, 0.75)
        self.assertEqual(snapshot.track.title, "Nocturne Drive")
        self.assertEqual(snapshot.track.art_path, "C:/covers/nocturne.png")
        self.assertEqual(snapshot.queue_count, 3)
        self.assertEqual(snapshot.manual_queue_count, 1)
        self.assertEqual(snapshot.queue_position, 1)
        self.assertEqual(snapshot.queue_paths, ("C:/music/nocturne.mp3", "C:/music/glass.mp3"))
        self.assertEqual(snapshot.visualizer_bars, (0.0, 0.25, 1.0))
        self.assertIsNotNone(snapshot.source_status)
        self.assertEqual(snapshot.source_status.source, "youtube")
        self.assertEqual(snapshot.source_status.query, "night drive")
        self.assertEqual(snapshot.source_status.result_count, 12)
        self.assertEqual(snapshot.source_status.status, "12 results  --  double-click to play")
        self.assertEqual(len(snapshot.source_results), 1)
        self.assertEqual(snapshot.source_results[0].title, "Night Drive Mix")
        self.assertEqual(snapshot.source_results[0].artist, "Ikari Channel")
        self.assertEqual(snapshot.source_results[0].source, "YouTube")
        self.assertEqual(snapshot.source_results[0].duration, "4:12")
        self.assertEqual(snapshot.source_results[0].art_url, "https://example.test/night.jpg")
        self.assertEqual(len(snapshot.queue_preview), 2)
        self.assertTrue(snapshot.queue_preview[0].is_current)
        self.assertEqual(snapshot.queue_preview[0].track.art_path, "C:/covers/nocturne.png")
        self.assertEqual(snapshot.queue_preview[1].track.title, "Glass City Rain")
        self.assertEqual(snapshot.queue_preview[1].track.art_url, "https://example.test/glass.jpg")
        self.assertIsNotNone(snapshot.last_command)
        self.assertEqual(snapshot.last_command.command_id, "cmd-1")
        self.assertEqual(snapshot.last_command.action, "play_library_path")
        self.assertTrue(snapshot.last_command.ok)
        self.assertEqual(snapshot.last_command.message, "PLAY HANDLED")

    def test_old_runtime_snapshot_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "runtime.json"
            write_runtime_snapshot(
                {
                    "updated_at": time.time() - 60,
                    "source": "library",
                    "track": {"title": "Old Signal"},
                },
                data_path,
            )

            snapshot = load_runtime_snapshot(data_path, max_age_s=1)

        self.assertTrue(snapshot.data_file_exists)
        self.assertFalse(snapshot.is_live)
        self.assertEqual(snapshot.track.title, "Old Signal")

    def test_runtime_file_marker_reports_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "runtime.json"

            self.assertEqual(runtime_file_marker(data_path), (False, 0))
            write_runtime_snapshot({"source": "library"}, data_path)
            exists, marker = runtime_file_marker(data_path)

        self.assertTrue(exists)
        self.assertGreater(marker, 0)


if __name__ == "__main__":
    unittest.main()
