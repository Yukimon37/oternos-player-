import unittest

from oternos.core.queue import (
    activate_manual_item,
    add_manual_item,
    adjust_position_after_reorder,
    choose_next_position,
    choose_previous_position,
    clear_all,
    clear_manual,
    promote_manual_next,
    remove_auto_item,
    remove_manual_item,
    reorder_items,
)


class QueueTests(unittest.TestCase):
    def test_promote_manual_next_inserts_after_current(self):
        queue = [10, 20]
        manual = [30, 40]

        pos = promote_manual_next(queue, manual, 0)

        self.assertEqual(pos, 1)
        self.assertEqual(queue, [10, 30, 20])
        self.assertEqual(manual, [40])

    def test_choose_next_position_wraps_and_shuffles(self):
        self.assertEqual(choose_next_position(3, 2), 0)
        self.assertEqual(
            choose_next_position(3, 1, shuffle=True, chooser=lambda choices: choices[-1]),
            2,
        )
        self.assertIsNone(choose_next_position(0, -1))

    def test_choose_previous_position_wraps(self):
        self.assertEqual(choose_previous_position(3, 0), 2)
        self.assertIsNone(choose_previous_position(0, -1))

    def test_clear_helpers(self):
        queue = [1, 2]
        manual = [3]

        self.assertEqual(clear_all(queue, manual), -1)
        self.assertEqual(queue, [])
        self.assertEqual(manual, [])

        manual.extend([4, 5])
        clear_manual(manual)
        self.assertEqual(manual, [])

    def test_reorder_and_position_adjustment(self):
        items = ["a", "b", "c", "d"]
        changed, to_idx = reorder_items(items, 1, 3)

        self.assertTrue(changed)
        self.assertEqual(to_idx, 3)
        self.assertEqual(items, ["a", "c", "d", "b"])
        self.assertEqual(adjust_position_after_reorder(2, 1, 3), 1)
        self.assertEqual(adjust_position_after_reorder(1, 1, 3), 3)

    def test_activate_and_remove_items(self):
        queue = [10, 20]
        manual = [30, 40]

        pos = activate_manual_item(queue, manual, 1, 0)
        self.assertEqual(pos, 1)
        self.assertEqual(queue, [10, 40, 20])
        self.assertEqual(manual, [30])

        self.assertTrue(remove_manual_item(manual, 0))
        self.assertFalse(remove_manual_item(manual, 0))

        removed, queue_pos = remove_auto_item(queue, 1, 2)
        self.assertTrue(removed)
        self.assertEqual(queue_pos, 1)
        self.assertEqual(queue, [10, 20])

        removed, queue_pos = remove_auto_item(queue, 0, 0)
        self.assertTrue(removed)
        self.assertEqual(queue_pos, 0)

        removed, queue_pos = remove_auto_item(queue, 0, 0)
        self.assertTrue(removed)
        self.assertEqual(queue_pos, -1)
        self.assertEqual(queue, [])

    def test_add_manual_item_reports_when_to_start(self):
        manual = []

        should_start = add_manual_item(manual, 42, -1, is_playing=False)

        self.assertTrue(should_start)
        self.assertEqual(manual, [42])
        self.assertFalse(add_manual_item(manual, 43, 0, is_playing=False))


if __name__ == "__main__":
    unittest.main()

