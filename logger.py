"""
Event logging for the Streamlit video UI.

- ``video_log.csv`` — user actions (e.g. video selection).
- ``eye_tracking_stub.csv`` — **UI events only**, not Pupil Labs gaze data.
  Real gaze is recorded by ``neon_gaze_recorder.py`` (see project docs).

``session_id`` links rows to a corresponding Neon recording when you pass the same
id via ``--session-id`` or the ``NEON_SESSION_ID`` environment variable.
"""

from __future__ import annotations

import csv
import os
import warnings
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_FILE = str(PROJECT_ROOT / "video_log.csv")
EYE_STUB_LOG = str(PROJECT_ROOT / "eye_tracking_stub.csv")

_CSV_HEADER = ("timestamp", "video_name", "event", "session_id")

# Skip re-reading unchanged files (mtime + size).
_migrated_etag: dict[str, tuple[float, int]] = {}

try:
    from filelock import FileLock as _FileLock
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "The 'filelock' package is required (pip install filelock) for safe CSV access."
    ) from e


def _lock_path_for_csv(csv_path: str) -> str:
    return f"{csv_path}.lock"


def _lock_for(path: str) -> _FileLock:
    """Block until the lock is acquired (``timeout`` -1: no spurious time limit in lab use)."""
    return _FileLock(_lock_path_for_csv(path), timeout=-1)


def _column_is_session_field(name: str) -> bool:
    """True for session-related headers; avoids matching e.g. 'obsession' (contains 'session')."""
    n = name.strip().lower()
    if n in ("session_id", "session", "run_id", "sessionid"):
        return True
    if n.endswith("_session_id") or n.startswith("session_"):
        return True
    return False


def _atomic_write_rows_impl(path: str, rows: list[list[str]]) -> None:
    """Write ``rows`` to ``path`` (caller must hold the file lock if needed)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    os.replace(tmp, path)


def _atomic_write_rows(path: str, rows: list[list[str]]) -> None:
    with _lock_for(path):
        _atomic_write_rows_impl(path, rows)


def _get_cell(d: dict[str, str], *names: str) -> str:
    for n in names:
        nlow = n.lower()
        for k, v in d.items():
            if k.lower() == nlow:
                return v
    return ""


def _row_dict_first_wins(header: list[str], padded: list[str]) -> dict[str, str]:
    d: dict[str, str] = {}
    for i, h in enumerate(header):
        k = h.strip()
        if k not in d and i < len(padded):
            d[k] = padded[i]
    return d


def _rows_from_flexible_header(
    header: list[str],
    data_rows: list[list[str]],
    default_event: str,
) -> list[list[str]] | None:
    """If header contains a session-like or known column, map to canonical 4 columns."""
    if not any(_column_is_session_field(h) for h in header):
        return None

    out: list[list[str]] = [list(_CSV_HEADER)]
    for row in data_rows:
        if not row or not any(c.strip() for c in row):
            continue
        padded = (list(row) + [""] * len(header))[: len(header)]
        d = _row_dict_first_wins(header, padded)
        ts = _get_cell(d, "timestamp", "time", "ts")
        vn = _get_cell(d, "video_name", "video", "file", "clip")
        ev = _get_cell(d, "event", "action", "type")
        sid = _get_cell(d, "session_id", "session", "run_id")
        if not sid:
            for i, hname in enumerate(header):
                if _column_is_session_field(hname) and i < len(padded):
                    sid = padded[i]
                    break
        if ts or vn or ev or sid:
            out.append(
                [
                    ts or (row[0] if row else ""),
                    vn or (row[1] if len(row) > 1 else ""),
                    ev or default_event,
                    (sid or "legacy_no_session").strip() or "legacy_no_session",
                ]
            )
    if len(out) <= 1:
        return None
    return out


def _header_starts_canonical(header: list[str]) -> bool:
    if len(header) < 4:
        return False
    h = [c.strip().lower() for c in header[:4]]
    return h == ["timestamp", "video_name", "event", "session_id"]


def _migrate_log_to_four_columns(
    path: str,
    *,
    default_event_when_two_data_cols: str,
) -> bool:
    """Normalize legacy CSVs. Returns True if the file was rewritten."""
    if not os.path.isfile(path):
        return False

    with _lock_for(path):
        st0 = os.stat(path)
        etag0 = (st0.st_mtime, st0.st_size)
        if _migrated_etag.get(path) == etag0:
            return False

        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            stf = os.stat(path)
            _migrated_etag[path] = (stf.st_mtime, stf.st_size)
            return False
        header = [c.strip() for c in rows[0]]
        hlower = [h.lower() for h in header]

        if not header:
            warnings.warn(
                f"Unrecognized empty CSV header in {path!r}; file left unchanged.",
                UserWarning,
                stacklevel=2,
            )
            stf = os.stat(path)
            _migrated_etag[path] = (stf.st_mtime, stf.st_size)
            return False

        data_rows = rows[1:]
        did_write = False

        # Drop extra header columns if the first four are already canonical
        if _header_starts_canonical(header) and len(header) > 4:
            out0: list[list[str]] = [list(_CSV_HEADER)]
            for row in data_rows:
                r = (row + [""] * 4)[:4]
                if not any(c.strip() for c in r):
                    continue
                out0.append(r)
            _atomic_write_rows_impl(path, out0)
            did_write = True
            st2 = os.stat(path)
            _migrated_etag[path] = (st2.st_mtime, st2.st_size)
            return did_write

        if _header_starts_canonical(header):
            stf = os.stat(path)
            _migrated_etag[path] = (stf.st_mtime, stf.st_size)
            return False

        named = _rows_from_flexible_header(header, data_rows, default_event_when_two_data_cols)
        if named is not None:
            _atomic_write_rows_impl(path, named)
            did_write = True
        elif len(header) == 2 and hlower[0] == "timestamp":
            out: list[list[str]] = [list(_CSV_HEADER)]
            for row in data_rows:
                if len(row) < 2:
                    continue
                out.append(
                    [row[0], row[1], default_event_when_two_data_cols, "legacy_no_session"]
                )
            _atomic_write_rows_impl(path, out)
            did_write = True
        elif len(header) == 3:
            out2: list[list[str]] = [list(_CSV_HEADER)]
            for row in data_rows:
                if len(row) == 2:
                    out2.append(
                        [row[0], row[1], default_event_when_two_data_cols, "legacy_no_session"]
                    )
                elif len(row) >= 3:
                    out2.append(row[:3] + ["legacy_no_session"])
            _atomic_write_rows_impl(path, out2)
            did_write = True
        elif len(header) >= 4:
            out3: list[list[str]] = [list(_CSV_HEADER)]
            for row in data_rows:
                r = (row + [""] * 4)[:4]
                if not any(c.strip() for c in r):
                    continue
                out3.append(
                    [
                        r[0],
                        r[1],
                        r[2] or default_event_when_two_data_cols,
                        (r[3] or "legacy_no_session").strip() or "legacy_no_session",
                    ]
                )
            if len(out3) > 1 or (len(header) >= 4 and hlower[3:4] and hlower[3] != "session_id"):
                _atomic_write_rows_impl(path, out3)
                did_write = True
        elif len(header) == 1 and hlower[0] in ("timestamp", "time"):
            out4: list[list[str]] = [list(_CSV_HEADER)]
            for row in data_rows:
                if not row or not str(row[0]).strip():
                    continue
                out4.append(
                    [row[0], "unknown", default_event_when_two_data_cols, "legacy_no_session"]
                )
            _atomic_write_rows_impl(path, out4)
            did_write = True
        else:
            warnings.warn(
                f"Unrecognized CSV layout in {path!r} ({len(header)} columns); file left unchanged.",
                UserWarning,
                stacklevel=2,
            )

        st2 = os.stat(path)
        _migrated_etag[path] = (st2.st_mtime, st2.st_size)
        return did_write


def _ensure_migrations() -> None:
    _migrate_log_to_four_columns(
        LOG_FILE, default_event_when_two_data_cols="video_selected"
    )
    _migrate_log_to_four_columns(
        EYE_STUB_LOG, default_event_when_two_data_cols="eye_tracking_started"
    )


def _fsync_file(f) -> None:
    try:
        f.flush()
        os.fsync(f.fileno())
    except OSError:
        pass


def log_session_ui_events_for_video(video_name: str, session_id: str) -> None:
    """
    Log video selection and eye stub in one go: same order as migrations (``LOG_FILE`` then
    ``EYE_STUB_LOG``), both locks held, and one shared ``timestamp`` for the pair.
    Data rows are written in one try/segment and both files are flushed to OS buffers together.
    """
    vrow = [datetime.now().isoformat(), video_name, "video_selected", session_id]
    erow = [vrow[0], video_name, "eye_tracking_started", session_id]
    _ensure_migrations()
    with _lock_for(LOG_FILE):
        with _lock_for(EYE_STUB_LOG):
            need_video = (not os.path.isfile(LOG_FILE)) or os.path.getsize(LOG_FILE) == 0
            need_eye = (not os.path.isfile(EYE_STUB_LOG)) or os.path.getsize(
                EYE_STUB_LOG
            ) == 0
            with open(LOG_FILE, "a", encoding="utf-8", newline="") as fv, open(
                EYE_STUB_LOG, "a", encoding="utf-8", newline=""
            ) as fe:
                wv, we = csv.writer(fv), csv.writer(fe)
                try:
                    if need_video:
                        wv.writerow(_CSV_HEADER)
                    if need_eye:
                        we.writerow(_CSV_HEADER)
                    wv.writerow(vrow)
                    we.writerow(erow)
                except OSError as e:
                    warnings.warn(
                        f"UI CSV append failed in paired write ({e!r}); logs may be partial.",
                        UserWarning,
                        stacklevel=2,
                    )
                    raise
                _fsync_file(fe)
                _fsync_file(fv)


def log_video_selection(video_name: str, session_id: str) -> None:
    """
    Log a **video_selected** line *and* the matching eye-stub line for this selection.
    For one selection event, call at most one of: ``log_session_ui_events_for_video``,
    ``log_video_selection``, ``log_ui_eye_stub_for_video``, or ``log_eye_data_stub``.
    """
    log_session_ui_events_for_video(video_name, session_id)


def log_ui_eye_stub_for_video(video_name: str, session_id: str) -> None:
    """
    Log the eye **stub** line *and* the matching ``video_log`` line for this selection.
    (Same as :func:`log_session_ui_events_for_video` — do not also call that for the same event.)
    """
    log_session_ui_events_for_video(video_name, session_id)


def log_eye_data_stub(video_name: str, session_id: str) -> None:
    """Back-compat: same as :func:`log_session_ui_events_for_video` (paired log)."""
    log_session_ui_events_for_video(video_name, session_id)
