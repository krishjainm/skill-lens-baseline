"""
Generate time-series and spatial gaze plots from Neon CSV runs.

Reads baseline and eye-movement CSVs from output/ and saves plots into plots/.
Run:  python plot_gaze_runs.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_ROOT = Path(__file__).resolve().parent
_OUTPUT = _ROOT / "output"
_PLOTS = _ROOT / "plots"

BASELINE_CSV = _OUTPUT / "neon_gaze_20260514_164420_-1.csv"
EYE_MOVEMENT_CSV = _OUTPUT / "neon_gaze_20260514_165253_-1.csv"


def _time_ms_col(df: pd.DataFrame) -> pd.Series:
    """Return gaze time in ms, normalized so the run starts at 0."""
    if "time_ms" in df.columns:
        t = df["time_ms"].astype(float)
    else:
        t = df["timestamp_unix_seconds"] * 1000.0
    return t - t.iloc[0]


def _save(fig: plt.Figure, name: str) -> None:
    path = _PLOTS / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def _parse_in_out(series: pd.Series) -> pd.Series:
    """Coerce in_out to integer 0/1 regardless of bool-string or numeric input."""
    mapped = series.astype(str).str.strip().str.lower()
    return mapped.map({"true": 1, "false": 0, "1": 1, "0": 0, "1.0": 1, "0.0": 0}).fillna(0).astype(int)


def _print_in_out_stats(df: pd.DataFrame, label: str) -> None:
    raw = df["in_out"]
    unique = sorted({str(v) for v in raw.dropna().unique()})
    parsed = _parse_in_out(raw)
    n = len(parsed)
    n_in = int(parsed.sum())
    n_out = n - n_in
    pct_in = 100.0 * n_in / n if n else 0.0
    pct_out = 100.0 * n_out / n if n else 0.0
    print(f"  [{label}] unique in_out values: {unique}")
    print(f"  [{label}] in: {n_in}/{n} ({pct_in:.1f}%)  out: {n_out}/{n} ({pct_out:.1f}%)")


def main() -> None:
    _PLOTS.mkdir(exist_ok=True)

    df1 = pd.read_csv(BASELINE_CSV)
    df2 = pd.read_csv(EYE_MOVEMENT_CSV)

    df1["time_sec"] = df1["timestamp_unix_seconds"] - df1["timestamp_unix_seconds"].iloc[0]
    df2["time_sec"] = df2["timestamp_unix_seconds"] - df2["timestamp_unix_seconds"].iloc[0]

    # z is constant (head-fixed plane); fill blanks with 0 for plotting
    df1["z"] = pd.to_numeric(df1["z"], errors="coerce").fillna(0.0)
    df2["z"] = pd.to_numeric(df2["z"], errors="coerce").fillna(0.0)

    # ---- Time vs X ----
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df1["time_sec"], df1["x"], linewidth=0.6, label="baseline")
    ax.plot(df2["time_sec"], df2["x"], linewidth=0.6, label="eye movement")
    ax.set_title("Time vs X")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("X gaze position")
    ax.legend()
    _save(fig, "time_vs_x.png")

    # ---- Time vs Y ----
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df1["time_sec"], df1["y"], linewidth=0.6, label="baseline")
    ax.plot(df2["time_sec"], df2["y"], linewidth=0.6, label="eye movement")
    ax.set_title("Time vs Y")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Y gaze position")
    ax.legend()
    _save(fig, "time_vs_y.png")

    # ---- Time vs Z ----
    # z is currently constant (gaze projected onto a head-fixed plane).
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df1["time_sec"], df1["z"], linewidth=0.6, label="baseline")
    ax.plot(df2["time_sec"], df2["z"], linewidth=0.6, label="eye movement")
    ax.set_title("Time vs Z (constant — head-fixed plane projection)")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Z gaze position")
    ax.legend()
    _save(fig, "time_vs_z.png")

    # ---- Combined X/Y/Z stacked sync plot (per run) ----
    for label, df in [("baseline", df1), ("eye_movement", df2)]:
        t = _time_ms_col(df)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, figsize=(10, 7))
        fig.suptitle(f"Gaze Time Series Sync — {label.replace('_', ' ')}")

        ax1.plot(t, df["x"], linewidth=0.6, label="x gaze")
        ax1.set_ylabel("X coordinate")
        ax1.legend(loc="upper right")

        ax2.plot(t, df["y"], linewidth=0.6, label="y gaze")
        ax2.set_ylabel("Y coordinate")
        ax2.legend(loc="upper right")

        ax3.plot(t, df["z"], linewidth=0.6, label="z gaze")
        ax3.set_xlabel("Gaze time (ms)")
        ax3.set_ylabel("Z coordinate")
        ax3.legend(loc="upper right")

        fig.tight_layout()
        _save(fig, f"gaze_time_sync_{label}.png")

    # ---- X vs Y gaze pattern ----
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df1["x"], df1["y"], alpha=0.3, s=4, label="baseline")
    ax.scatter(df2["x"], df2["y"], alpha=0.3, s=4, label="eye movement")
    ax.set_title("X vs Y Gaze Pattern")
    ax.set_xlabel("X gaze position")
    ax.set_ylabel("Y gaze position")
    ax.legend()
    _save(fig, "x_vs_y_gaze_pattern.png")

    # ---- in_out vs Time ----
    io1 = _parse_in_out(df1["in_out"])
    io2 = _parse_in_out(df2["in_out"])

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.step(df1["time_sec"], io1, where="post", linewidth=0.8, label="baseline")
    ax.step(df2["time_sec"], io2, where="post", linewidth=0.8, label="eye movement")
    ax.set_title("In/Out vs Time")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("in_out (1 = in, 0 = out)")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["out", "in"])
    ax.legend()
    _save(fig, "in_out_vs_time.png")

    print("\nin_out field summary:")
    _print_in_out_stats(df1, "baseline")
    _print_in_out_stats(df2, "eye movement")

    print(f"\nAll plots saved to {_PLOTS}/")


if __name__ == "__main__":
    main()
