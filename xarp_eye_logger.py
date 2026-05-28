"""
xarp_eye_logger.py — Use XARP to inspect and log real XR eye tracking data to CSV.

This version is defensive because XARP may return the eye pose under different
frame keys depending on the API/client version.
"""

import argparse
import csv
import os
import signal
import time
from datetime import datetime

from xarp.data_models import Pose
from xarp.express import SyncXR
from xarp.server import run, make_qrcode_image


STOP_FLAG = False


def handle_sigint(sig, frame):
    global STOP_FLAG
    print("\n[xarp_eye_logger] Ctrl+C received, stopping...")
    STOP_FLAG = True


signal.signal(signal.SIGINT, handle_sigint)


def parse_args():
    parser = argparse.ArgumentParser(description="XARP Eye Tracking Logger")
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Recording duration in seconds (default: 30)",
    )
    return parser.parse_args()


def safe_get(obj, key, default=""):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_frame_keys(frame):
    if isinstance(frame, dict):
        return list(frame.keys())
    return [k for k in dir(frame) if not k.startswith("_")]


def find_eye_pose(frame):
    """
    Try common key names first, then fall back to any Pose-like object.
    """
    candidate_keys = ["eyes", "eye", "gaze", "pose"]

    if isinstance(frame, dict):
        for key in candidate_keys:
            if key in frame:
                return frame[key], key

        for key, value in frame.items():
            if hasattr(value, "position") and (
                hasattr(value, "rotation") or hasattr(value, "orientation")
            ):
                return value, key

    else:
        for key in candidate_keys:
            value = getattr(frame, key, None)
            if value is not None:
                return value, key

        for key in get_frame_keys(frame):
            value = getattr(frame, key, None)
            if hasattr(value, "position") and (
                hasattr(value, "rotation") or hasattr(value, "orientation")
            ):
                return value, key

    return None, ""


def extract_pose_values(pose: Pose | object | None):
    if pose is None:
        return ("", "", "", "", "", "", "")

    pos = safe_get(pose, "position", None)
    rot = safe_get(pose, "rotation", None)
    if rot is None:
        rot = safe_get(pose, "orientation", None)

    if pos is None:
        px = py = pz = ""
    else:
        px = safe_get(pos, "x", "")
        py = safe_get(pos, "y", "")
        pz = safe_get(pos, "z", "")

    if rot is None:
        rx = ry = rz = rw = ""
    else:
        rx = safe_get(rot, "x", "")
        ry = safe_get(rot, "y", "")
        rz = safe_get(rot, "z", "")
        rw = safe_get(rot, "w", "")

    return px, py, pz, rx, ry, rz, rw


def app(xr: SyncXR, *args, **kwargs) -> None:
    global STOP_FLAG

    cli_args = parse_args()
    duration = cli_args.duration

    print("=" * 60)
    print("  Skill Lens XARP logger started")
    print(f"  Duration: {duration}s | Press Ctrl+C to stop early")
    print("=" * 60)

    os.makedirs("output", exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"output/xarp_eye_log_{timestamp_str}.csv"

    columns = [
        "timestamp_unix_seconds",
        "time_ms",
        "frame_index",
        "available_keys",
        "eye_key_used",
        "eye_available",
        "eye_position_x",
        "eye_position_y",
        "eye_position_z",
        "eye_orientation_x",
        "eye_orientation_y",
        "eye_orientation_z",
        "eye_orientation_w",
        "head_position_x",
        "head_position_y",
        "head_position_z",
        "head_orientation_x",
        "head_orientation_y",
        "head_orientation_z",
        "head_orientation_w",
    ]

    stream = xr.sense(eye=True)
    start_time = time.time()
    elapsed = 0.0
    frame_index = 0

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)

        for frame in stream:
            if STOP_FLAG:
                break

            elapsed = time.time() - start_time
            if elapsed >= duration:
                break

            now_unix = time.time()
            time_ms = elapsed * 1000.0

            keys = get_frame_keys(frame)
            eye_pose, eye_key = find_eye_pose(frame)

            if frame_index < 5:
                print(f"\n[Frame {frame_index}] keys = {keys}")
                print(f"[Frame {frame_index}] eye_key_used = {eye_key!r}")
                print(f"[Frame {frame_index}] raw frame = {frame}")
                if eye_pose is not None:
                    print(f"[Frame {frame_index}] position = {safe_get(eye_pose, 'position', None)}")
                    print(f"[Frame {frame_index}] rotation = {safe_get(eye_pose, 'rotation', None)}")

            px, py, pz, rx, ry, rz, rw = extract_pose_values(eye_pose)

            row = [
                f"{now_unix:.6f}",
                f"{time_ms:.1f}",
                frame_index,
                ";".join(str(k) for k in keys),
                eye_key,
                eye_pose is not None,
                px,
                py,
                pz,
                rx,
                ry,
                rz,
                rw,
                "", "", "",
                "", "", "", "",
            ]
            writer.writerow(row)
            frame_index += 1

        close = getattr(stream, "close", None)
        if callable(close):
            close()

    print(f"\n[xarp_eye_logger] Logged {frame_index} frames in {elapsed:.1f}s")
    print(f"[xarp_eye_logger] CSV saved to: {csv_path}")


if __name__ == "__main__":
    make_qrcode_image()
    run(app)