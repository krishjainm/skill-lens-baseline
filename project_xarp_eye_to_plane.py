"""Project a real XARP eye-pose log onto the existing finite video plane.

This is the first bridge from REAL Quest/XARP eye pose data to the synthetic
ray-plane geometry already used by ``ray_plane_simulation.py``. We read a CSV
produced by ``xarp_eye_logger.py``, turn each eye pose into a gaze ray, and
intersect it with a fixed rectangular video plane.

The synthetic pipeline (``ray_plane_simulation.py``) is intentionally left
untouched; this script only reuses ``intersect_gaze_with_video_plane``.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from ray_plane_geometry import intersect_gaze_with_video_plane, normalize

_ROOT = Path(__file__).resolve().parent
_OUT_DIR = _ROOT / "output"

# --- Coordinate assumptions for this first real-data pass -------------------
# ASSUMPTION (validate with Arthur): the XARP eye orientation quaternion maps a
# LOCAL FORWARD vector of [0, 0, -1] (OpenGL/OpenXR convention) into the world
# gaze direction. If the projection later looks sign-inverted, we can try
# [0, 0, 1] instead, but we do NOT silently flip it here.
LOCAL_FORWARD = np.array([0.0, 0.0, -1.0])

# --- Plane assumptions for this first real-data pass ------------------------
# ASSUMPTION (validate with Arthur): fixed synthetic plane in front of origin.
PLANE_CENTER = np.array([0.0, 0.0, -1.0])
PLANE_NORMAL = np.array([0.0, 0.0, 1.0])
PLANE_WIDTH = 1.0
PLANE_HEIGHT = 0.6

OUTPUT_COLUMNS = [
    "timestamp_unix_seconds",
    "time_ms",
    "frame_index",
    "eye_position_x",
    "eye_position_y",
    "eye_position_z",
    "eye_orientation_x",
    "eye_orientation_y",
    "eye_orientation_z",
    "eye_orientation_w",
    "gaze_dir_x",
    "gaze_dir_y",
    "gaze_dir_z",
    "plane_center_x",
    "plane_center_y",
    "plane_center_z",
    "plane_normal_x",
    "plane_normal_y",
    "plane_normal_z",
    "plane_width",
    "plane_height",
    "hit",
    "in_out",
    "reason",
    "t",
    "hit_x",
    "hit_y",
    "hit_z",
    "plane_u",
    "plane_v",
]


def quaternion_to_rotation_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Return the 3x3 rotation matrix for quaternion (qx, qy, qz, qw).

    The quaternion is normalized first so callers do not need to pre-normalize.
    """
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if n < 1e-12:
        raise ValueError("Cannot build a rotation from a near-zero quaternion.")
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n

    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz

    return np.array(
        [
            [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
            [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
            [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
        ],
        dtype=float,
    )


def rotate_vector_by_quaternion(v, qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Rotate 3-vector *v* by quaternion (qx, qy, qz, qw)."""
    r = quaternion_to_rotation_matrix(qx, qy, qz, qw)
    return r @ np.asarray(v, dtype=float)


def _parse_float(value) -> float | None:
    """Parse a CSV cell to float, returning None for blank / non-numeric."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if math.isnan(f):
        return None
    return f


def _default_output_path(input_path: Path) -> Path:
    """Derive output path, preserving the input timestamp when present."""
    m = re.search(r"(\d{8}_\d{6})", input_path.name)
    if m:
        stamp = m.group(1)
    else:
        stamp = input_path.stem
    return _OUT_DIR / f"xarp_eye_plane_projection_{stamp}.csv"


def process(input_path: Path, output_path: Path) -> dict:
    """Read the eye log, project onto the plane, and write the projection CSV.

    Returns a summary dict (also printed by :func:`main`).
    """
    rows_read = 0
    valid_pose = 0
    hits = 0
    in_out_count = 0
    reason_counts: Counter[str] = Counter()

    out_rows: list[dict] = []

    with input_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows_read += 1

            px = _parse_float(raw.get("eye_position_x"))
            py = _parse_float(raw.get("eye_position_y"))
            pz = _parse_float(raw.get("eye_position_z"))
            qx = _parse_float(raw.get("eye_orientation_x"))
            qy = _parse_float(raw.get("eye_orientation_y"))
            qz = _parse_float(raw.get("eye_orientation_z"))
            qw = _parse_float(raw.get("eye_orientation_w"))

            # Drop rows with any missing eye pose/orientation component.
            if None in (px, py, pz, qx, qy, qz, qw):
                continue
            valid_pose += 1

            origin = np.array([px, py, pz])
            gaze_raw = rotate_vector_by_quaternion(LOCAL_FORWARD, qx, qy, qz, qw)
            try:
                gaze_dir = normalize(gaze_raw)
            except ValueError:
                # Degenerate rotation produced a zero vector; skip the row.
                continue

            result = intersect_gaze_with_video_plane(
                origin, gaze_dir, PLANE_CENTER, PLANE_NORMAL, PLANE_WIDTH, PLANE_HEIGHT,
            )

            if result["hit"]:
                hits += 1
            if result["in_out"]:
                in_out_count += 1
            reason_counts[result["reason"]] += 1

            out_rows.append(
                {
                    "timestamp_unix_seconds": raw.get("timestamp_unix_seconds", ""),
                    "time_ms": raw.get("time_ms", ""),
                    "frame_index": raw.get("frame_index", ""),
                    "eye_position_x": px,
                    "eye_position_y": py,
                    "eye_position_z": pz,
                    "eye_orientation_x": qx,
                    "eye_orientation_y": qy,
                    "eye_orientation_z": qz,
                    "eye_orientation_w": qw,
                    "gaze_dir_x": float(gaze_dir[0]),
                    "gaze_dir_y": float(gaze_dir[1]),
                    "gaze_dir_z": float(gaze_dir[2]),
                    "plane_center_x": PLANE_CENTER[0],
                    "plane_center_y": PLANE_CENTER[1],
                    "plane_center_z": PLANE_CENTER[2],
                    "plane_normal_x": PLANE_NORMAL[0],
                    "plane_normal_y": PLANE_NORMAL[1],
                    "plane_normal_z": PLANE_NORMAL[2],
                    "plane_width": PLANE_WIDTH,
                    "plane_height": PLANE_HEIGHT,
                    "hit": result["hit"],
                    "in_out": result["in_out"],
                    "reason": result["reason"],
                    "t": result["t"],
                    "hit_x": result["hit_x"],
                    "hit_y": result["hit_y"],
                    "hit_z": result["hit_z"],
                    "plane_u": result["plane_u"],
                    "plane_v": result["plane_v"],
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    return {
        "rows_read": rows_read,
        "valid_pose": valid_pose,
        "hits": hits,
        "in_out_count": in_out_count,
        "reason_counts": dict(reason_counts),
        "output_path": str(output_path),
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project a real XARP eye log onto the finite video plane.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to output/xarp_eye_log_<timestamp>.csv",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output CSV path (default: output/xarp_eye_plane_projection_<timestamp>.csv)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input CSV not found: {input_path}")
        return 1

    output_path = Path(args.output) if args.output else _default_output_path(input_path)
    summary = process(input_path, output_path)

    print("=" * 60)
    print("  XARP eye -> video plane projection")
    print("=" * 60)
    print(f"  rows read:            {summary['rows_read']}")
    print(f"  rows w/ valid pose:   {summary['valid_pose']}")
    print(f"  hits:                 {summary['hits']}")
    print(f"  in_out count:         {summary['in_out_count']}")
    print(f"  reason counts:        {summary['reason_counts']}")
    print(f"  output path:          {summary['output_path']}")
    print(f"  local forward vector: {LOCAL_FORWARD.tolist()}  (assumption: validate with Arthur)")
    print(f"  plane center/normal:  {PLANE_CENTER.tolist()} / {PLANE_NORMAL.tolist()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
