import unittest

from oternos.core.settings import DEFAULT_SETTINGS, build_default_settings, merge_settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_mutable_copies(self):
        a = build_default_settings()
        b = build_default_settings()

        a["watch_dirs"].append("C:/Music")
        a["hotkeys"]["play_pause"] = "space"

        self.assertEqual(b["watch_dirs"], [])
        self.assertEqual(b["hotkeys"], {})
        self.assertEqual(DEFAULT_SETTINGS["watch_dirs"], [])

    def test_merge_preserves_defaults_and_saved_overrides(self):
        merged = merge_settings({"boot_enabled": False, "custom_future_key": "kept"})

        self.assertFalse(merged["boot_enabled"])
        self.assertEqual(merged["eq_preset"], "flat")
        self.assertEqual(merged["custom_future_key"], "kept")

    def test_merge_ignores_non_dict_saved_data(self):
        merged = merge_settings(None)

        self.assertEqual(merged["active_theme"], "void")
        self.assertTrue(merged["autoplay"])


if __name__ == "__main__":
    unittest.main()

