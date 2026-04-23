"""
Smoke tests for small helpers in neon_gaze_recorder, stitch, and paired UI logging
(no Streamlit, no real devices).
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestGazeToRow(unittest.TestCase):
    def test_gaze_to_row(self) -> None:
        import neon_gaze_recorder as ngr

        g = SimpleNamespace(
            timestamp_unix_seconds=1.5,
            x=0.1,
            y=0.2,
            worn=True,
        )
        row = ngr._gaze_to_row(g, "S1", "sess")
        self.assertEqual(row["timestamp_unix_seconds"], 1.5)
        self.assertEqual(row["x"], 0.1)
        self.assertEqual(row["y"], 0.2)
        self.assertIs(row["worn"], True)
        self.assertEqual(row["device_serial"], "S1")
        self.assertEqual(row["session_id"], "sess")


class TestPathutilRemove(unittest.TestCase):
    def test_try_remove_file_missing_ok(self) -> None:
        import pathutil

        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "nope")
            pathutil.try_remove_file(p)
            self.assertFalse(os.path.isfile(p))

    def test_try_remove_file_deletes(self) -> None:
        import pathutil

        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "a.bin")
            Path(p).write_bytes(b"x")
            pathutil.try_remove_file(p)
            self.assertFalse(os.path.isfile(p))


class TestPairedSessionLog(unittest.TestCase):
    def setUp(self) -> None:
        import logger as lg

        self._mod = importlib.reload(lg)
        self._mod._migrated_etag.clear()

    def test_paired_shares_timestamp(self) -> None:
        d = tempfile.mkdtemp()
        a = os.path.join(d, "a.csv")
        b = os.path.join(d, "b.csv")
        with (
            patch.object(self._mod, "LOG_FILE", a),
            patch.object(self._mod, "EYE_STUB_LOG", b),
            patch.object(self._mod, "_ensure_migrations", lambda: None),
        ):
            self._mod.log_session_ui_events_for_video("clip.mov", "sid-9")

        with open(a, encoding="utf-8", newline="") as f:
            ra = f.read()
        with open(b, encoding="utf-8", newline="") as f:
            rb = f.read()
        tsa = ra.strip().split("\n")[-1].split(",")[0]
        tsb = rb.strip().split("\n")[-1].split(",")[0]
        self.assertEqual(tsa, tsb)
        self.assertIn("clip.mov", ra)
        self.assertIn("eye_tracking_started", rb)

    def test_back_compat_delegates_to_paired(self) -> None:
        d = tempfile.mkdtemp()
        a = os.path.join(d, "a2.csv")
        b = os.path.join(d, "b2.csv")
        with (
            patch.object(self._mod, "LOG_FILE", a),
            patch.object(self._mod, "EYE_STUB_LOG", b),
            patch.object(self._mod, "_ensure_migrations", lambda: None),
        ):
            self._mod.log_video_selection("x.mp4", "sid-b")

        with open(b, encoding="utf-8", newline="") as f:
            rb = f.read()
        self.assertIn("eye_tracking_started", rb)


if __name__ == "__main__":
    unittest.main()
