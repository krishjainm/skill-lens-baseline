"""
xarp_eye_logger.py — Use XARP to log real XR eye tracking data to CSV.

Reference: HAL-UCSB/xarp demos/brush.py
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

    stream = xr.sense(eyes=True)
    start_time = time.time()
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

            eyes: Pose = frame['eyes']

            if frame_index < 3:
                print(eyes.position)
                print(eyes.rotation)

            pos = eyes.position
            rot = eyes.rotation

            row = [
                f"{now_unix:.6f}",
                f"{time_ms:.1f}",
                frame_index,
                pos.x, pos.y, pos.z,
                rot.x, rot.y, rot.z, rot.w,
                "", "", "",
                "", "", "", "",
            ]
            writer.writerow(row)
            frame_index += 1

        stream.close()

    print(f"\n[xarp_eye_logger] Logged {frame_index} frames in {elapsed:.1f}s")
    print(f"[xarp_eye_logger] CSV saved to: {csv_path}")


if __name__ == "__main__":
    make_qrcode_image()
    run(app)
