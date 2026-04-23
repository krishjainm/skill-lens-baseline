"""
Quick connectivity test: find one Neon, print up to five non-empty gaze samples, exit.
Empty API samples are skipped; exit code 1 if no samples were received at all.
Use in the lab before a longer run with neon_gaze_recorder.py.

  python neon_test.py
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from pupil_labs.realtime_api.simple import discover_one_device
    except ImportError:
        print("Install: pip install pupil-labs-realtime-api", file=sys.stderr)
        return 1

    print("Looking for a device (10 s)...")
    device = discover_one_device(max_search_duration_seconds=10)
    if device is None:
        print("No device found.", file=sys.stderr)
        return 1

    try:
        try:
            serial = device.serial_number_glasses
        except AttributeError:
            serial = "unknown"
        print(f"Connected to {serial}. Up to 5 receive attempts (empty samples skipped)...")

        received = 0
        for _ in range(5):
            gaze = device.receive_gaze_datum()
            if gaze is None:
                print("  (no sample — check timeout or connection)")
                continue
            received += 1
            print(
                f"  t={gaze.timestamp_unix_seconds:.3f}  "
                f"xy=({gaze.x:.3f}, {gaze.y:.3f})  "
                f"worn={gaze.worn}"
            )
        if received == 0:
            print("No gaze samples received.", file=sys.stderr)
            return 1
        if received < 5:
            print(
                f"Only {received}/5 non-empty samples (stream may be intermittent).",
                file=sys.stderr,
            )
        print("OK — Neon realtime gaze stream is working.")
        return 0
    finally:
        device.close()


if __name__ == "__main__":
    raise SystemExit(main())
