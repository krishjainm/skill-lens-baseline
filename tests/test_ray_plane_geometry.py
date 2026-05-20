"""Unit tests for ray_plane_geometry helpers."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import ray_plane_geometry as rpg


class TestDirectHitInside(unittest.TestCase):
    def test_hit_center(self) -> None:
        r = rpg.intersect_gaze_with_video_plane(
            ray_origin=[0, 0, 0],
            ray_direction=[0, 0, 1],
            plane_center=[0, 0, 1],
            plane_normal=[0, 0, -1],
            width=2,
            height=2,
        )
        self.assertTrue(r["hit"])
        self.assertTrue(r["in_out"])
        self.assertEqual(r["reason"], "inside")
        np.testing.assert_allclose([r["hit_x"], r["hit_y"], r["hit_z"]], [0, 0, 1], atol=1e-9)


class TestHitOutside(unittest.TestCase):
    def test_outside(self) -> None:
        r = rpg.intersect_gaze_with_video_plane(
            ray_origin=[0, 0, 0],
            ray_direction=rpg.normalize([2, 0, 1]),
            plane_center=[0, 0, 1],
            plane_normal=[0, 0, -1],
            width=2,
            height=2,
        )
        self.assertTrue(r["hit"])
        self.assertFalse(r["in_out"])
        self.assertEqual(r["reason"], "outside")


class TestParallelRay(unittest.TestCase):
    def test_parallel(self) -> None:
        r = rpg.intersect_gaze_with_video_plane(
            ray_origin=[0, 0, 0],
            ray_direction=[1, 0, 0],
            plane_center=[0, 0, 1],
            plane_normal=[0, 0, 1],
            width=2,
            height=2,
        )
        self.assertFalse(r["hit"])
        self.assertEqual(r["reason"], "parallel")


class TestBehindRay(unittest.TestCase):
    def test_behind(self) -> None:
        r = rpg.intersect_gaze_with_video_plane(
            ray_origin=[0, 0, 0],
            ray_direction=[0, 0, 1],
            plane_center=[0, 0, -1],
            plane_normal=[0, 0, -1],
            width=2,
            height=2,
        )
        self.assertFalse(r["hit"])
        self.assertEqual(r["reason"], "behind_ray")


class TestPlaneAxes(unittest.TestCase):
    def test_orthonormal(self) -> None:
        for normal in ([0, 0, 1], [1, 0, 0], [0, 1, 0], [1, 1, 1]):
            n = rpg.normalize(normal)
            u, v = rpg.make_plane_axes(n)
            self.assertAlmostEqual(np.linalg.norm(u), 1.0, places=9)
            self.assertAlmostEqual(np.linalg.norm(v), 1.0, places=9)
            self.assertAlmostEqual(abs(np.dot(u, n)), 0.0, places=9)
            self.assertAlmostEqual(abs(np.dot(v, n)), 0.0, places=9)
            self.assertAlmostEqual(abs(np.dot(u, v)), 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
