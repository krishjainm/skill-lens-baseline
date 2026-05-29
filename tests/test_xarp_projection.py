"""Unit tests for project_xarp_eye_to_plane (no headset / XARP runtime needed)."""
import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import project_xarp_eye_to_plane as proj  # noqa: E402


class TestQuaternionRotation(unittest.TestCase):
    def test_identity_rotation(self) -> None:
        # Identity quaternion (0,0,0,1) should leave any vector unchanged.
        r = proj.quaternion_to_rotation_matrix(0.0, 0.0, 0.0, 1.0)
        np.testing.assert_allclose(r, np.eye(3), atol=1e-12)

        for v in ([1, 0, 0], [0, 1, 0], [0, 0, -1], [0.3, -0.4, 0.5]):
            out = proj.rotate_vector_by_quaternion(v, 0.0, 0.0, 0.0, 1.0)
            np.testing.assert_allclose(out, np.asarray(v, dtype=float), atol=1e-12)

    def test_180_about_y(self) -> None:
        # 180 deg about Y maps [0,0,-1] -> [0,0,1].
        out = proj.rotate_vector_by_quaternion([0, 0, -1], 0.0, 1.0, 0.0, 0.0)
        np.testing.assert_allclose(out, [0, 0, 1], atol=1e-9)

    def test_unnormalized_quaternion(self) -> None:
        # A scaled identity quaternion still yields identity after normalization.
        r = proj.quaternion_to_rotation_matrix(0.0, 0.0, 0.0, 5.0)
        np.testing.assert_allclose(r, np.eye(3), atol=1e-12)


class TestProjectionOnTinyCsv(unittest.TestCase):
    def _write_csv(self, path: Path) -> None:
        # One valid row (identity orientation -> forward [0,0,-1] hits the plane
        # at z=-1), plus one row with a missing orientation that must be dropped.
        header = [
            "timestamp_unix_seconds", "time_ms", "frame_index",
            "available_keys", "eye_key_used", "eye_available",
            "eye_position_x", "eye_position_y", "eye_position_z",
            "eye_orientation_x", "eye_orientation_y", "eye_orientation_z",
            "eye_orientation_w",
            "head_position_x", "head_position_y", "head_position_z",
            "head_orientation_x", "head_orientation_y", "head_orientation_z",
            "head_orientation_w",
        ]
        valid = [
            "1780011696.24", "78.9", "0", "eye", "eye", "True",
            "0.0", "0.0", "0.0",
            "0.0", "0.0", "0.0", "1.0",
            "", "", "", "", "", "", "",
        ]
        missing = [
            "1780011696.42", "257.5", "1", "eye", "eye", "False",
            "0.0", "0.0", "0.0",
            "", "", "", "",
            "", "", "", "", "", "", "",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow(valid)
            w.writerow(missing)

    def test_process_tiny_csv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            in_path = Path(d) / "xarp_eye_log_20260101_000000.csv"
            out_path = Path(d) / "projection.csv"
            self._write_csv(in_path)

            summary = proj.process(in_path, out_path)

            self.assertEqual(summary["rows_read"], 2)
            self.assertEqual(summary["valid_pose"], 1)
            self.assertEqual(summary["hits"], 1)

            self.assertTrue(out_path.is_file())
            with out_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                fieldnames = reader.fieldnames

            # Required projection columns are present.
            for col in proj.OUTPUT_COLUMNS:
                self.assertIn(col, fieldnames)

            # Only the valid row survived.
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["hit"], "True")
            # Identity orientation -> forward [0,0,-1] hits plane at z=-1, center.
            self.assertAlmostEqual(float(row["hit_z"]), -1.0, places=6)
            self.assertAlmostEqual(float(row["gaze_dir_z"]), -1.0, places=6)
            self.assertEqual(row["in_out"], "True")


if __name__ == "__main__":
    unittest.main()
