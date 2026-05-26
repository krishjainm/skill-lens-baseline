"""
xarp_eye_logger.py — Use XARP to inspect and log real XR eye/head tracking data to CSV.

Reference: HAL-UCSB/xarp demos/brush.py
"""

import argparse
import csv
import os
import signal
import time
from datetime import datetime

from xarp.express import SyncXR
from xarp.server import run, make_qrcode_image


STOP_FLAG = False


def handle_sigint(sig, frame):
    global STOP_FLAG
    print("\n[xarp_eye_logger] Ctrl+C received, stopping...")
    STOP_FLAG = True


signal.signal(signal.SIGINT, handle_sigint)


def safe_get(obj, key, default=""):
    """Safely retrieve an attribute or key from an object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_position(obj):
    """Extract x, y, z position from a Pose or object with a position attribute."""
    if obj is None:
        return ("", "", "")
    pos = safe_get(obj, "position", None)
    if pos is None:
        return ("", "", "")
    x = safe_get(pos, "x", "")
    y = safe_get(pos, "y", "")
    z = safe_get(pos, "z", "")
    return (x, y, z)


def extract_orientation(obj):
    """Extract x, y, z, w orientation (quaternion) from a Pose or object with an orientation/rotation attribute."""
    if obj is None:
        return ("", "", "", "")
    ori = safe_get(obj, "orientation", None)
    if ori is None:
        ori = safe_get(obj, "rotation", None)
    if ori is None:
        return ("", "", "", "")
    x = safe_get(ori, "x", "")
    y = safe_get(ori, "y", "")
    z = safe_get(ori, "z", "")
    w = safe_get(ori, "w", "")
    return (x, y, z, w)


def parse_args():
    parser = argparse.ArgumentParser(description="XARP Eye/Head Tracking Logger")
    parser.add_argument(
        "--duration", type=float, default=30.0,
        help="Recording duration in seconds (default: 30)"
    )
    return parser.parse_args()


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
        "eye_available",
        "head_available",
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

    stream = xr.sense(eye=True, head=True)
    start_time = time.time()
    frame_index = 0
    first_frame_printed = False

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

            keys = list(frame.keys()) if isinstance(frame, dict) else dir(frame)
            available_keys = ";".join(str(k) for k in keys)

            if not first_frame_printed:
                print(f"\n[Frame 0] Available keys: {keys}")
                first_frame_printed = True

            eye_data = frame.get("eye", None) if isinstance(frame, dict) else getattr(frame, "eye", None)
            head_data = frame.get("head", None) if isinstance(frame, dict) else getattr(frame, "head", None)

            eye_available = eye_data is not None
            head_available = head_data is not None

            eye_pos = extract_position(eye_data)
            eye_ori = extract_orientation(eye_data)
            head_pos = extract_position(head_data)
            head_ori = extract_orientation(head_data)

            row = [
                f"{now_unix:.6f}",
                f"{time_ms:.1f}",
                frame_index,
                available_keys,
                eye_available,
                head_available,
                *eye_pos,
                *eye_ori,
                *head_pos,
                *head_ori,
            ]
            writer.writerow(row)
            frame_index += 1

            if frame_index <= 3:
                print(f"  [Frame {frame_index}] eye={eye_available} head={head_available} "
                      f"eye_pos={eye_pos} head_pos={head_pos}")

        stream.close()

    print(f"\n[xarp_eye_logger] Logged {frame_index} frames in {elapsed:.1f}s")
    print(f"[xarp_eye_logger] CSV saved to: {csv_path}")


if __name__ == "__main__":
    make_qrcode_image()
    run(app)
