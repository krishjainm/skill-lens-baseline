"""Read the synthetic ray-plane CSV and produce per-case plots + a text summary."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_ROOT = Path(__file__).resolve().parent
_CSV = _ROOT / "output" / "ray_plane_simulation.csv"
_PLOTS = _ROOT / "plots" / "ray_plane"


def _save(fig: plt.Figure, name: str) -> None:
    path = _PLOTS / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def _plot_distance_vs_time(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    for case, grp in df.groupby("case_name", sort=False):
        ax.plot(grp["time_ms"], grp["distance_intersection_minus_gaze_xy0"],
                linewidth=0.8, label=case)
    ax.set_title("Distance Between Gaze XY0 and Ray-Plane Intersection")
    ax.set_xlabel("time_ms")
    ax.set_ylabel("distance")
    ax.legend()
    _save(fig, "distance_vs_time_by_case.png")


def _plot_in_out_vs_time(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 3))
    for case, grp in df.groupby("case_name", sort=False):
        ax.step(grp["time_ms"], grp["in_out"].astype(int),
                where="post", linewidth=0.8, label=case)
    ax.set_title("Geometry-Based In/Out Over Time")
    ax.set_xlabel("time_ms")
    ax.set_ylabel("in_out (1=in, 0=out)")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["out", "in"])
    ax.legend()
    _save(fig, "in_out_vs_time_by_case.png")


def _plot_plane_uv(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for case, grp in df.groupby("case_name", sort=False):
        ax.scatter(grp["plane_u"], grp["plane_v"], alpha=0.4, s=6, label=case)
    ax.set_title("Intersection Coordinates on Video Plane")
    ax.set_xlabel("plane_u")
    ax.set_ylabel("plane_v")
    ax.legend()
    _save(fig, "plane_uv_by_case.png")


def _plot_hit_axis(df: pd.DataFrame, axis: str) -> None:
    col = f"hit_{axis}"
    fig, ax = plt.subplots(figsize=(10, 4))
    for case, grp in df.groupby("case_name", sort=False):
        ax.plot(grp["time_ms"], grp[col], linewidth=0.8, label=case)
    ax.set_title(f"hit_{axis} vs Time by Case")
    ax.set_xlabel("time_ms")
    ax.set_ylabel(col)
    ax.legend()
    _save(fig, f"hit_{axis}_vs_time_by_case.png")


def _write_summary(df: pd.DataFrame) -> None:
    path = _PLOTS / "summary_stats.txt"
    lines: list[str] = []
    for case, grp in df.groupby("case_name", sort=False):
        hits = int(grp["hit"].sum())
        ins = int(grp["in_out"].sum())
        reasons = dict(Counter(grp["reason"]))
        dists = grp["distance_intersection_minus_gaze_xy0"].dropna()
        mean_d = float(dists.mean()) if len(dists) else float("nan")
        max_d = float(dists.max()) if len(dists) else float("nan")
        lines.append(f"--- {case} ---")
        lines.append(f"  rows:         {len(grp)}")
        lines.append(f"  hits:         {hits}")
        lines.append(f"  in_out:       {ins}")
        lines.append(f"  reasons:      {reasons}")
        lines.append(f"  mean distance: {mean_d:.6f}")
        lines.append(f"  max distance:  {max_d:.6f}")
        lines.append("")
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    print(f"Saved {path}")
    print(text)


def main() -> int:
    if not _CSV.is_file():
        print(f"CSV not found: {_CSV}\nRun ray_plane_simulation.py first.")
        return 1

    df = pd.read_csv(_CSV)
    _PLOTS.mkdir(parents=True, exist_ok=True)

    _plot_distance_vs_time(df)
    _plot_in_out_vs_time(df)
    _plot_plane_uv(df)
    for axis in ("x", "y", "z"):
        _plot_hit_axis(df, axis)
    _write_summary(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
