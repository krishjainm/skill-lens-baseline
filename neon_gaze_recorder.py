"""
Stream gaze samples from a Pupil Labs Neon (Companion app on the same network)
and append rows to a CSV. Run in a terminal for lab testing:

  python neon_gaze_recorder.py
  set NEON_SESSION_ID=<id from Streamlit sidebar> & python neon_gaze_recorder.py
  python neon_gaze_recorder.py -o my_session.csv --duration 60 --session-id <id>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _gaze_to_row(gaze, device_serial: str, session_id: str) -> dict[str, object]:
    return {
        "timestamp_unix_seconds": gaze.timestamp_unix_seconds,
        "x": gaze.x,
        "y": gaze.y,
        "worn": gaze.worn,
        "device_serial": device_serial,
        "session_id": session_id,
    }


def _next_queue_get_timeout(
    t_end: float | None,
    no_gaze_limit: float,
    inactivity_limit: float,
    duration: float,
    n: int,
    rec_t0: float,
    last_row_mono: float | None,
) -> float | None:
    """
    How long the main thread may block on the gaze queue before re-checking deadlines.
    None = no deadline polling (one blocking wait, matches old behavior).
    """
    now = time.monotonic()
    if t_end is not None and now >= t_end:
        return 0.0
    need_poll = False
    step = 1.0
    if t_end is not None:
        need_poll = True
        rem = t_end - now
        if rem <= 0:
            return 0.0
        step = min(step, rem)
    if no_gaze_limit > 0 and duration == 0 and n == 0:
        need_poll = True
        rem = no_gaze_limit - (now - rec_t0)
        if rem <= 0:
            return 0.0
        step = min(step, rem)
    if inactivity_limit > 0 and n > 0 and last_row_mono is not None:
        need_poll = True
        rem = inactivity_limit - (now - last_row_mono)
        if rem <= 0:
            return 0.0
        step = min(step, rem)
    if not need_poll:
        return None
    return max(0.001, min(step, 1.0))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record Pupil Labs Neon gaze data to a CSV file (realtime API).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="CSV file path (default: under output/ with timestamp and device serial in the name).",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session UUID to align with Streamlit UI logs (default: NEON_SESSION_ID env, else random).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Record for this many seconds, then stop (0 = until Ctrl-C).",
    )
    parser.add_argument(
        "--search-timeout",
        type=float,
        default=10.0,
        dest="search_timeout",
        help="Seconds to look for a device on the LAN.",
    )
    parser.add_argument(
        "--no-gaze-seconds",
        type=float,
        default=0.0,
        dest="no_gaze_seconds",
        help="If no non-empty gaze row is written in this many seconds (from the start of "
        "the recording), exit 1. 0 disables (default). Unbounded runs only.",
    )
    parser.add_argument(
        "--inactivity-seconds",
        type=float,
        default=0.0,
        dest="inactivity_seconds",
        help="After the first gaze row, exit 1 if no new row is delivered for this many "
        "seconds. Must exceed your device's typical time between real samples, or the run "
        "can exit spuriously. 0 disables (default).",
    )
    args = parser.parse_args()

    if args.duration < 0:
        print("--duration must be >= 0 (0 = until Ctrl-C).", file=sys.stderr)
        return 1
    if args.search_timeout < 0:
        print("--search-timeout must be >= 0.", file=sys.stderr)
        return 1
    if args.no_gaze_seconds < 0:
        print("--no-gaze-seconds must be >= 0 (0 = disabled).", file=sys.stderr)
        return 1
    if args.inactivity_seconds < 0:
        print("--inactivity-seconds must be >= 0 (0 = disabled).", file=sys.stderr)
        return 1

    try:
        from pupil_labs.realtime_api.simple import discover_one_device
    except ImportError:
        print("Missing dependency. Install with: pip install pupil-labs-realtime-api", file=sys.stderr)
        return 1

    session_id = (args.session_id or os.environ.get("NEON_SESSION_ID", "")).strip()
    if not session_id:
        session_id = str(uuid.uuid4())

    print("Looking for a Neon device (Companion app must be running, same network)...")
    device = discover_one_device(max_search_duration_seconds=args.search_timeout)
    if device is None:
        print("No device found. No session was started for recording.", file=sys.stderr)
        return 1

    print(
        f"Session ID for this recording: {session_id}\n"
        "(Match the Streamlit sidebar session, or set NEON_SESSION_ID / --session-id next time.)"
    )

    n = 0
    user_interrupt = False
    no_gaze_stall = False
    inactivity_stall = False
    gaze_stream_broken = False
    out_path: Path | None = None
    meta_path: Path | None = None
    serial = "unknown"
    started = datetime.now(timezone.utc)
    had_timed_window = args.duration > 0
    csv_ready_for_meta = False
    no_gaze_limit = float(args.no_gaze_seconds) if args.no_gaze_seconds > 0 else 0.0
    inactivity_limit = float(args.inactivity_seconds) if args.inactivity_seconds > 0 else 0.0
    if no_gaze_limit > 0 and args.duration > 0:
        print(
            "Warning: --no-gaze-seconds is only applied when --duration is 0 (unbounded).",
            file=sys.stderr,
        )
    try:
        try:
            serial = device.serial_number_glasses
        except AttributeError:
            serial = "unknown"
        out_path = args.output
        if out_path is None:
            out_path = (
                _ROOT / "output"
                / f"neon_gaze_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{serial}.csv"
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path = out_path.parent / f"{out_path.stem}.meta.json"

        fieldnames = [
            "timestamp_unix_seconds",
            "x",
            "y",
            "worn",
            "device_serial",
            "session_id",
        ]
        t_end = time.monotonic() + args.duration if args.duration > 0 else None

        print(f"Connected to {serial}. Writing: {out_path.resolve()}")
        if args.duration > 0:
            print(f"Recording for {args.duration} s (Ctrl-C to stop early).")
        else:
            print("Recording until Ctrl-C.")
        if no_gaze_limit > 0 and args.duration == 0:
            print(
                f"Will exit if no gaze row is received within {no_gaze_limit} s (unbounded run)."
            )
        if inactivity_limit > 0:
            print(
                f"Will exit if no new gaze for {inactivity_limit} s after the previous row."
            )

        with out_path.open("w", encoding="utf-8", newline="") as f:
            csv_ready_for_meta = True
            # Only start the receive thread after the output file is open, so a failed
            # open() cannot leave a producer thread with no main-loop consumer.
            gaze_buf: queue.Queue[object] = queue.Queue(maxsize=1)
            _stream_end = object()

            def _gaze_producer() -> None:
                while True:
                    try:
                        g = device.receive_gaze_datum()
                    except Exception as e:  # noqa: BLE001
                        print(
                            f"receive_gaze_datum error (stopping read loop): {e}",
                            file=sys.stderr,
                        )
                        try:
                            gaze_buf.put(_stream_end)
                        except Exception:
                            pass
                        return
                    try:
                        gaze_buf.put(g)
                    except Exception:
                        try:
                            gaze_buf.put(_stream_end)
                        except Exception:
                            pass
                        return

            threading.Thread(
                target=_gaze_producer, name="neon-gaze-receive", daemon=True
            ).start()
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            f.flush()
            rec_t0 = time.monotonic()
            last_row_mono: float | None = None
            # Sentinel: nothing pending from a non-blocking get (distinct from API empty samples).
            _prefetch_empty: object = object()

            def _process_gaze_item(g: object) -> bool:
                """Return True to stop the main recording loop (end-of-stream object)."""
                nonlocal n, last_row_mono, gaze_stream_broken
                if g is _stream_end:
                    gaze_stream_broken = True
                    return True
                if g is None:
                    return False
                w.writerow(_gaze_to_row(g, serial, session_id))
                n += 1
                last_row_mono = time.monotonic()
                if n % 200 == 0:
                    f.flush()
                return False

            try:
                while not gaze_stream_broken:
                    # Honor samples already in the queue before cut checks, so a row
                    # received just before t_end / inactivity is not skipped for those exits.
                    try:
                        g_pre = gaze_buf.get_nowait()
                    except queue.Empty:
                        g_pre = _prefetch_empty
                    if g_pre is not _prefetch_empty and _process_gaze_item(g_pre):
                        break
                    if t_end is not None and time.monotonic() >= t_end:
                        break
                    if (
                        no_gaze_limit > 0
                        and args.duration == 0
                        and n == 0
                        and (time.monotonic() - rec_t0) > no_gaze_limit
                    ):
                        no_gaze_stall = True
                        break
                    if (
                        inactivity_limit > 0
                        and n > 0
                        and last_row_mono is not None
                        and (time.monotonic() - last_row_mono) > inactivity_limit
                    ):
                        inactivity_stall = True
                        break
                    t_get = _next_queue_get_timeout(
                        t_end,
                        no_gaze_limit,
                        inactivity_limit,
                        args.duration,
                        n,
                        rec_t0,
                        last_row_mono,
                    )
                    if t_get == 0.0:
                        continue
                    try:
                        if t_get is None:
                            gaze = gaze_buf.get()
                        else:
                            gaze = gaze_buf.get(timeout=t_get)
                    except queue.Empty:
                        continue
                    if _process_gaze_item(gaze):
                        break
            except KeyboardInterrupt:
                user_interrupt = True
                print("\nStopped by user.")
            finally:
                f.flush()
                # Empty the queue with the same path as the main loop (no raw discard):
                # unblocks a producer stuck on put, and still writes a pending gaze row.
                while not gaze_stream_broken:
                    try:
                        g_left = gaze_buf.get_nowait()
                    except queue.Empty:
                        break
                    if _process_gaze_item(g_left):
                        break
        if gaze_stream_broken:
            return 1
    finally:
        device.close()
        ended = datetime.now(timezone.utc)
        if (
            csv_ready_for_meta
            and out_path is not None
            and meta_path is not None
        ):
            try:
                _csv_p = str(out_path.resolve())
            except OSError:
                _csv_p = str(out_path)
            meta = {
                "session_id": session_id,
                "device_serial": serial,
                "csv_path": _csv_p,
                "started_at_utc": started.isoformat(),
                "ended_at_utc": ended.isoformat(),
                "gaze_row_count": n,
            }
            try:
                with meta_path.open("w", encoding="utf-8") as mf:
                    json.dump(meta, mf, indent=2)
            except OSError as e:
                print(f"Warning: could not write metadata to {meta_path!r}: {e}", file=sys.stderr)

    meta_note = "n/a"
    if meta_path is not None:
        try:
            meta_note = str(meta_path.resolve())
        except OSError:
            meta_note = str(meta_path)

    if inactivity_stall and n > 0:
        print(
            f"No new gaze for {inactivity_limit:g} s after the last row "
            f"({n} row(s) written; inactivity; metadata: {meta_note}).",
            file=sys.stderr,
        )
        return 1

    if n == 0:
        if no_gaze_stall:
            reason = (
                f"No gaze row within the first {no_gaze_limit:g} s "
                f"(see --no-gaze-seconds; unbounded run)."
            )
        elif had_timed_window:
            reason = "No gaze rows in the timed window."
        elif user_interrupt:
            reason = "Stopped before any gaze rows were written."
        else:
            reason = "No gaze rows recorded."
        print(f"{reason} (metadata: {meta_note}).", file=sys.stderr)
        return 1

    print(f"Wrote {n} samples. Connection closed. Metadata: {meta_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
