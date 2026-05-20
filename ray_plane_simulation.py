"""Generate a synthetic CSV demonstrating gaze-ray / video-plane intersection at varying distances."""
from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from ray_plane_geometry import intersect_gaze_with_video_plane, normalize

_ROOT = Path(__file__).resolve().parent
_OUT_DIR = _ROOT / "output"

CASES = [
    {"case_name": "close_plane", "z_distance": 0.5},
    {"case_name": "medium_plane", "z_distance": 2.0},
    {"case_name": "far_plane", "z_distance": 5.0},
]

N_STEPS = 300
CYCLES = 3.0
AMPLITUDE = 0.3

PLANE_WIDTH = 1.0
PLANE_HEIGHT = 0.6

FIELDNAMES = [
    "case_name",
    "time_ms",
    "eye_x", "eye_y", "eye_z",
    "gaze_x", "gaze_y", "gaze_z",
    "plane_center_x", "plane_center_y", "plane_center_z",
    "plane_normal_x", "plane_normal_y", "plane_normal_z",
    "plane_width", "plane_height",
    "hit", "in_out",
    "hit_x", "hit_y", "hit_z",
    "plane_u", "plane_v",
    "distance_intersection_minus_gaze_xy0",
    "reason",
]


def _gaze_direction(i: int, n: int) -> np.ndarray:
    angle = 2 * math.pi * CYCLES * i / n
    return normalize([
        AMPLITUDE * math.cos(angle),
        AMPLITUDE * math.sin(angle),
        1.0,
    ])


def _distance(hit_x, hit_y, hit_z, gaze_x, gaze_y):
    return math.sqrt(
        (hit_x - gaze_x) ** 2 + (hit_y - gaze_y) ** 2 + hit_z ** 2
    )


def generate_rows():
    eye = np.array([0.0, 0.0, 0.0])
    plane_normal = np.array([0.0, 0.0, -1.0])
    rows = []
    for case in CASES:
        z_d = case["z_distance"]
        plane_center = np.array([0.0, 0.0, z_d])
        for i in range(N_STEPS):
            gaze_dir = _gaze_direction(i, N_STEPS)
            result = intersect_gaze_with_video_plane(
                eye, gaze_dir, plane_center, plane_normal, PLANE_WIDTH, PLANE_HEIGHT,
            )
            time_ms = i
            gx, gy, gz = gaze_dir

            if result["hit"]:
                dist = _distance(result["hit_x"], result["hit_y"], result["hit_z"], gx, gy)
            else:
                dist = float("nan")

            rows.append({
                "case_name": case["case_name"],
                "time_ms": time_ms,
                "eye_x": eye[0], "eye_y": eye[1], "eye_z": eye[2],
                "gaze_x": f"{gx:.8f}", "gaze_y": f"{gy:.8f}", "gaze_z": f"{gz:.8f}",
                "plane_center_x": plane_center[0],
                "plane_center_y": plane_center[1],
                "plane_center_z": plane_center[2],
                "plane_normal_x": plane_normal[0],
                "plane_normal_y": plane_normal[1],
                "plane_normal_z": plane_normal[2],
                "plane_width": PLANE_WIDTH,
                "plane_height": PLANE_HEIGHT,
                "hit": result["hit"],
                "in_out": result["in_out"],
                "hit_x": result["hit_x"],
                "hit_y": result["hit_y"],
                "hit_z": result["hit_z"],
                "plane_u": result["plane_u"],
                "plane_v": result["plane_v"],
                "distance_intersection_minus_gaze_xy0": dist,
                "reason": result["reason"],
            })
    return rows


def _print_summary(rows):
    by_case: dict[str, list[dict]] = {}
    for r in rows:
        by_case.setdefault(r["case_name"], []).append(r)

    for name, group in by_case.items():
        hits = sum(1 for r in group if r["hit"] is True)
        ins = sum(1 for r in group if r["in_out"] is True)
        reasons = Counter(r["reason"] for r in group)
        dists = [
            r["distance_intersection_minus_gaze_xy0"]
            for r in group
            if isinstance(r["distance_intersection_minus_gaze_xy0"], float)
            and not math.isnan(r["distance_intersection_minus_gaze_xy0"])
        ]
        mean_d = sum(dists) / len(dists) if dists else float("nan")
        print(f"\n--- {name} ---")
        print(f"  rows:   {len(group)}")
        print(f"  hits:   {hits}")
        print(f"  in_out: {ins}")
        print(f"  reasons: {dict(reasons)}")
        print(f"  mean distance: {mean_d:.6f}")


def main() -> int:
    rows = generate_rows()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / "ray_plane_simulation.csv"

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    _print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
