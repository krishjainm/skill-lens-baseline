# skill-lens-baseline

Baseline **Streamlit** video UI, **Pupil Labs Neon** gaze recording to CSV, and optional **FFmpeg** / **MoviePy** stitching for pilot work.

Paths for logs, `videos/`, and default Neon output are resolved from **`app.py` / `logger.py` / script location** (not the shell current working directory), as long as you run commands from the project folder in the normal way.

## Setup

```bash
pip install -r requirements.txt
```

Python **3.10+** is required for the current Pupil Labs realtime client. **`filelock`** is required for safe concurrent CSV appends and migrations.

## Run the web UI

```bash
streamlit run app.py
```

- Copy the **Session** ID from the sidebar, or use **New session ID** to start a clean ID. A paired `video_log` + eye-stub line is written when the app first loads, when the **selected video in the dropdown changes**, and again **right after a new session ID** (even if the selected video is unchanged, so the new session is tied to the current clip).
- For a Neon run in another terminal, use the same id:

**Windows (cmd):** `set NEON_SESSION_ID=<id>` then `python neon_gaze_recorder.py`

**Windows (PowerShell):** `$env:NEON_SESSION_ID="<id>"; python neon_gaze_recorder.py`

Or: `python neon_gaze_recorder.py --session-id <id>`

A session id is only printed from **`neon_gaze_recorder.py` after a device is found** (not if discovery fails or the import is missing).

UI logs go to `video_log.csv` and `eye_tracking_stub.csv` (stub events only; not Pupil Labs gaze). The app writes those two with **one shared timestamp and nested locks** so the pair cannot skew between files. Gaze + `session_id` are in the CSV from `neon_gaze_recorder.py`, with a sidecar `stem.meta.json` next to `stem.csv` (e.g. `run.meta.json` for `run.csv`) after the CSV file is **opened** successfully (not if opening the file fails before write).

**Exit code 1** (failure for automation) includes: **no gaze rows** in the CSV (e.g. a **positive `--duration`** elapses with no data, **Ctrl+C** before any row, **inactivity** / **no-gaze-seconds** stalls, or an empty file for other reasons). It also includes **a broken gaze read loop** after `receive_gaze_datum()` errors (the process exits **1** even if some rows were already written—treat the run as failed; metadata still records `gaze_row_count`). **Exit code 0** when at least one row is written and none of the failure conditions apply.

## Tests

```bash
python -m unittest discover -s tests -v
```

These are **unit** tests (logger migration, path helpers, paired logging, a mocked `app` import). They do **not** require a Neon device or the sample videos used by `stitch.py`—**lab validation** of gaze recording and stitching is still manual.

## Neon (lab)

1. Neon Companion on the same network as the PC.
2. `python neon_test.py` — quick stream check.
3. `python neon_gaze_recorder.py` — full gaze → CSV (see `--help`).

For **unbounded** recording (`--duration` 0), **`--no-gaze-seconds N`** fails fast if the stream produces **no row** in the first *N* seconds (exit 1). That option is ignored when `--duration` is positive (a warning is printed if both are set).

**`--inactivity-seconds M`** (after the **first** gaze row) ends the run with exit 1 if **M** wall-clock seconds pass without a new row—useful for a dead stream after data started. **M** should exceed the normal gap between valid samples for your update rate, or you may exit spuriously. A background thread feeds `receive_gaze_datum()` into a queue; the main loop **polls the queue** (up to once per second when deadlines apply) so inactivity and timed duration are re-evaluated even if the API blocks. **Before** those checks each iteration, any sample already in the queue is **written to the CSV** so a gaze that arrived just before a timed stop is not lost when the run ends. When the loop **stops** (any reason), the queue is flushed the same way—pending samples are written, not dropped, and the receive thread is unblocked. Disabled when *M* is 0 (default). Meta JSON write errors are a stderr warning and do not mask the run outcome; the metadata file stores an absolute `csv_path` when possible.

## Stitch (optional)

```bash
python stitch.py
```

Requires the three `videos/IMG_*.mov` inputs (or change paths in `stitch.py`). On **success**, intermediate `videos/converted_*.mp4` files are **removed** after the stitched file is written. **Ctrl+C** cleans up and exits with code **1** (portable; not Unix signal 128+n). FFmpeg is run with **stdout/stderr discarded** to avoid unbounded memory from progress logs. Set **`STITCH_FFMPEG_DEBUG=1`** (or `true`/`yes`/`y`/`on`) to write **stderr to a short-lived temp file** (disk, not a giant in-memory buffer) and print the tail of that file if a transcode step fails. MoviePy: the stitched clip is closed after encoding; if concatenation **never** runs, the script closes each `VideoFileClip` that was opened.

## Logs

- `video_log.csv` / `eye_tracking_stub.csv`: `timestamp, video_name, event, session_id`. The helpers `log_video_selection` / `log_eye_data_stub` / `log_session_ui_events_for_video` all write the **same paired rows**; use **at most one** per selection to avoid duplicate lines.
- Gaze file columns include `session_id` for joins with the UI.
