import tempfile
import unittest
from pathlib import Path

from oternos.core.runtime_commands import (
    load_runtime_command,
    runtime_command_file_marker,
    write_runtime_command,
)


class RuntimeCommandTests(unittest.TestCase):
    def test_missing_command_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = load_runtime_command(Path(tmp) / "missing.json")

        self.assertIsNone(command)

    def test_write_and_load_allowed_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "play_queue_position",
                {"position": 2},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "play_queue_position")
        self.assertEqual(loaded.payload["position"], 2)

    def test_write_and_load_remove_queue_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "remove_queue_position",
                {"position": 4},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "remove_queue_position")
        self.assertEqual(loaded.payload["position"], 4)

    def test_write_and_load_play_library_path_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "play_library_path",
                {"path": "C:/music/nocturne.mp3"},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "play_library_path")
        self.assertEqual(loaded.payload["path"], "C:/music/nocturne.mp3")

    def test_write_and_load_add_library_path_to_queue_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "add_library_path_to_queue",
                {"path": "C:/music/nocturne.mp3"},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "add_library_path_to_queue")
        self.assertEqual(loaded.payload["path"], "C:/music/nocturne.mp3")

    def test_write_and_load_add_library_path_to_playlist_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "add_library_path_to_playlist",
                {"path": "C:/music/nocturne.mp3", "playlist": "Night"},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "add_library_path_to_playlist")
        self.assertEqual(loaded.payload["path"], "C:/music/nocturne.mp3")
        self.assertEqual(loaded.payload["playlist"], "Night")

    def test_write_and_load_play_playlist_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "play_playlist",
                {"playlist": "Night"},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "play_playlist")
        self.assertEqual(loaded.payload["playlist"], "Night")

    def test_write_and_load_open_legacy_view_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "open_legacy_view",
                {"view": "soundcloud"},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "open_legacy_view")
        self.assertEqual(loaded.payload["view"], "soundcloud")

    def test_write_and_load_source_search_handoff_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "open_legacy_view",
                {"view": "youtube", "query": "night drive", "search": True},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "open_legacy_view")
        self.assertEqual(loaded.payload["view"], "youtube")
        self.assertEqual(loaded.payload["query"], "night drive")
        self.assertTrue(loaded.payload["search"])

    def test_write_and_load_play_source_result_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"
            written = write_runtime_command(
                "play_source_result",
                {"source": "youtube", "index": 1},
                data_path,
            )
            loaded = load_runtime_command(data_path)

        self.assertEqual(loaded.command_id, written.command_id)
        self.assertEqual(loaded.action, "play_source_result")
        self.assertEqual(loaded.payload["source"], "youtube")
        self.assertEqual(loaded.payload["index"], 1)

    def test_rejects_unknown_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"

            with self.assertRaises(ValueError):
                write_runtime_command("delete_library", {}, data_path)

    def test_command_file_marker_reports_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "command.json"

            self.assertEqual(runtime_command_file_marker(data_path), (False, 0))
            write_runtime_command("toggle_play", {}, data_path)
            exists, marker = runtime_command_file_marker(data_path)

        self.assertTrue(exists)
        self.assertGreater(marker, 0)


if __name__ == "__main__":
    unittest.main()
