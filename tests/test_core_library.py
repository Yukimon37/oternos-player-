import tempfile
import unittest
from pathlib import Path

from oternos.core.library import (
    adjust_queue_pos_after_library_removal,
    add_index_to_playlist,
    filter_existing_tracks,
    remap_indices_after_library_removal,
    remap_playlists_after_library_removal,
)


class LibraryTests(unittest.TestCase):
    def test_filter_existing_tracks_keeps_only_valid_existing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "track.mp3"
            existing.write_bytes(b"fake")

            tracks = [
                {"path": str(existing), "title": "A"},
                {"path": str(Path(tmp) / "missing.mp3"), "title": "B"},
                {"title": "No path"},
                "bad",
            ]

            self.assertEqual(filter_existing_tracks(tracks), [tracks[0]])

        self.assertEqual(filter_existing_tracks(None), [])

    def test_remap_indices_after_library_removal(self):
        self.assertEqual(
            remap_indices_after_library_removal([0, 1, 2, 4], 2),
            [0, 1, 3],
        )

    def test_remap_playlists_after_library_removal(self):
        playlists = {"A": [0, 2, 3], "B": [1, 2]}

        self.assertEqual(
            remap_playlists_after_library_removal(playlists, 2),
            {"A": [0, 2], "B": [1]},
        )

    def test_adjust_queue_pos_after_library_removal(self):
        self.assertEqual(adjust_queue_pos_after_library_removal(5, 3), 2)
        self.assertEqual(adjust_queue_pos_after_library_removal(1, 3), 1)
        self.assertEqual(adjust_queue_pos_after_library_removal(0, 0), -1)

    def test_add_index_to_playlist(self):
        playlists = {"Night": [1], "Broken": "bad"}

        self.assertEqual(add_index_to_playlist(playlists, "Night", 2), "added")
        self.assertEqual(playlists["Night"], [1, 2])
        self.assertEqual(add_index_to_playlist(playlists, "Night", 2), "existing")
        self.assertEqual(playlists["Night"], [1, 2])
        self.assertEqual(add_index_to_playlist(playlists, "Broken", 3), "added")
        self.assertEqual(playlists["Broken"], [3])
        self.assertEqual(add_index_to_playlist(playlists, "Missing", 4), "missing")


if __name__ == "__main__":
    unittest.main()
