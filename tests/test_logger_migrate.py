import csv
import importlib
import os
import sys
import tempfile
import unittest
import warnings
# Project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestLoggerMigration(unittest.TestCase):
    def setUp(self) -> None:
        import logger as lg

        self._mod = importlib.reload(lg)
        self._mod._migrated_etag.clear()

    def test_two_column_migrates(self) -> None:
        d = tempfile.mkdtemp()
        p = os.path.join(d, "v.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "video_name"])
            w.writerow(["a", "b.mp4"])
        self._mod._migrated_etag.clear()
        self._mod._migrate_log_to_four_columns(
            p, default_event_when_two_data_cols="video_selected"
        )
        with open(p, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], list(self._mod._CSV_HEADER))
        self.assertIn("b.mp4", rows[1][1])

    def test_unrecognized_warns(self) -> None:
        d = tempfile.mkdtemp()
        p = os.path.join(d, "u.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("weird,cols\n1,2\n")
        self._mod._migrated_etag.clear()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self._mod._migrate_log_to_four_columns(
                p, default_event_when_two_data_cols="v"
            )
        self.assertTrue(
            any("Unrecognized" in str(x.message) for x in w), [str(x.message) for x in w]
        )

    def test_first_wins_duplicate_header(self) -> None:
        r = self._mod._row_dict_first_wins(
            ["t", "t", "x"],
            ["1", "2", "3"],
        )
        self.assertEqual(r, {"t": "1", "x": "3"})

    def test_five_plus_column_trims_to_four(self) -> None:
        d = tempfile.mkdtemp()
        p = os.path.join(d, "f.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "timestamp",
                    "video_name",
                    "event",
                    "session_id",
                    "extra",
                ]
            )
            w.writerow(["1", "v.mp4", "e", "sid", "drop"])
        self._mod._migrated_etag.clear()
        self._mod._migrate_log_to_four_columns(
            p, default_event_when_two_data_cols="video_selected"
        )
        with open(p, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows[0]), 4)
        self.assertEqual(rows[0], list(self._mod._CSV_HEADER))
        self.assertEqual(rows[1][-1], "sid")


if __name__ == "__main__":
    unittest.main()
