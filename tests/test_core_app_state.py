import json
import tempfile
import unittest
from pathlib import Path

from oternos.core.app_state import load_app_snapshot, snapshot_file_marker


class AppStateTests(unittest.TestCase):
    def test_missing_file_returns_empty_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = load_app_snapshot(Path(tmp) / "missing.json")

        self.assertFalse(snapshot.data_file_exists)
        self.assertEqual(snapshot.library_count, 0)
        self.assertIsNone(snapshot.now_track)
        self.assertEqual(snapshot.repeat_mode, "off")

    def test_loads_saved_counts_recent_track_and_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            track_path = Path(tmp) / "track.mp3"
            track_path.write_bytes(b"fake")
            data_path = Path(tmp) / "state.json"
            data_path.write_text(
                json.dumps(
                    {
                        "library": [
                            {
                                "path": str(track_path),
                                "title": "Signal Bloom",
                                "artist": "Ikari",
                                "album": "Void Tape",
                                "duration": "3:05",
                                "art_path": str(Path(tmp) / "cover.png"),
                            },
                            {
                                "path": str(Path(tmp) / "missing.mp3"),
                                "title": "Missing",
                            },
                        ],
                        "playlists": {"Night": [0]},
                        "history": [
                            {
                                "title": "Nocturne Drive",
                                "artist": "Local",
                                "source": "History",
                                "duration": 222,
                            }
                        ],
                        "settings": {"active_theme": "void", "flow_mode": True},
                        "shuffle": True,
                        "repeat_mode": "all",
                    }
                ),
                encoding="utf-8",
            )

            snapshot = load_app_snapshot(data_path)

        self.assertTrue(snapshot.data_file_exists)
        self.assertEqual(snapshot.library_count, 1)
        self.assertEqual(snapshot.playlist_count, 1)
        self.assertEqual(snapshot.now_track.title, "Nocturne Drive")
        self.assertEqual(snapshot.now_track.duration, "3:42")
        self.assertEqual(snapshot.queue_preview[0].title, "Signal Bloom")
        self.assertEqual(snapshot.queue_preview[0].duration, "3:05")
        self.assertEqual(snapshot.queue_preview[0].art_path, str(Path(tmp) / "cover.png"))
        self.assertEqual(snapshot.library_preview[0].title, "Signal Bloom")
        self.assertEqual(snapshot.playlist_names, ("Night",))
        self.assertEqual(snapshot.playlist_previews[0].name, "Night")
        self.assertEqual(snapshot.playlist_previews[0].count, 1)
        self.assertEqual(snapshot.playlist_previews[0].tracks[0].title, "Signal Bloom")
        self.assertEqual(snapshot.repeat_mode, "all")
        self.assertTrue(snapshot.shuffle)
        self.assertTrue(snapshot.flow_mode)
        self.assertEqual(snapshot.sources[0].state, "1 TRACK")
        self.assertEqual(snapshot.sources[0].view_key, "library")
        self.assertEqual(snapshot.sources[1].view_key, "soundcloud")
        self.assertIn("Legacy", snapshot.sources[2].detail)

    def test_malformed_json_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "state.json"
            data_path.write_text("{not valid", encoding="utf-8")

            snapshot = load_app_snapshot(data_path)

        self.assertTrue(snapshot.data_file_exists)
        self.assertTrue(snapshot.error)
        self.assertEqual(snapshot.library_count, 0)
        self.assertEqual(snapshot.sources[3].view_key, "archive")

    def test_history_entries_resolve_to_matching_library_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            track_path = Path(tmp) / "match.mp3"
            cover_path = Path(tmp) / "match.png"
            track_path.write_bytes(b"fake")
            data_path = Path(tmp) / "state.json"
            data_path.write_text(
                json.dumps(
                    {
                        "library": [
                            {
                                "path": str(track_path),
                                "title": "Glass City Rain",
                                "artist": "Ikari",
                                "album": "Void Tape",
                                "duration": 180,
                                "art_path": str(cover_path),
                            }
                        ],
                        "history": [
                            {
                                "title": "Glass City Rain",
                                "artist": "Ikari",
                                "source": "History",
                                "duration": 222,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = load_app_snapshot(data_path)

        self.assertEqual(snapshot.now_track.title, "Glass City Rain")
        self.assertEqual(snapshot.now_track.path, str(track_path))
        self.assertEqual(snapshot.now_track.art_path, str(cover_path))
        self.assertEqual(snapshot.now_track.duration, "3:42")

    def test_snapshot_file_marker_changes_when_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "state.json"

            self.assertEqual(snapshot_file_marker(data_path), (False, 0))

            data_path.write_text("{}", encoding="utf-8")
            exists, marker = snapshot_file_marker(data_path)

        self.assertTrue(exists)
        self.assertGreater(marker, 0)


if __name__ == "__main__":
    unittest.main()
