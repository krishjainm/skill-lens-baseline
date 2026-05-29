"""Plot the real-data XARP eye -> video plane projection output.

Reads a CSV produced by ``project_xarp_eye_to_plane.py`` and writes figures plus
a text summary to ``plots/xarp_eye_plane/``.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_ROOT = Path(__file__).resolve().parent
_PLOTS = _ROOT / "plots" / "xarp_eye_plane"


def _save(fig: "plt.Figure", name: str) -> None:
    path = _PLOTS / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def _plot_plane_uv(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    if "in_out" in df.columns:
        inside = df[df["in_out"] == True]  # noqa: E712 - pandas boolean mask
        outside = df[df["in_out"] != True]  # noqa: E712
        ax.scatter(outside["plane_u"], outside["plane_v"], alpha=0.5, s=10,
                   color="tab:red", label="outside")
        ax.scatter(inside["plane_u"], inside["plane_v"], alpha=0.5, s=10,
                   color="tab:green", label="inside")
        ax.legend()
    else:
        ax.scatter(df["plane_u"], df["plane_v"], alpha=0.5, s=10)
    ax.set_title("Real XARP Eye Projection on Video Plane")
    ax.set_xlabel("plane_u")
    ax.set_ylabel("plane_v")
    _save(fig, "real_plane_uv.png")


def _plot_in_out_vs_time(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.step(df["time_ms"], df["in_out"].astype(int), where="post", linewidth=0.8)
    ax.set_title("Real Geometry-Based In/Out Over Time")
    ax.set_xlabel("time_ms")
    ax.set_ylabel("in_out (1=in, 0=out)")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["out", "in"])
    _save(fig, "real_in_out_vs_time.png")


def _plot_hit_axis(df: pd.DataFrame, axis: str) -> None:
    col = f"hit_{axis}"
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["time_ms"], df[col], linewidth=0.8)
    ax.set_title(f"Real hit_{axis} vs Time")
    ax.set_xlabel("time_ms")
    ax.set_ylabel(col)
    _save(fig, f"real_hit_{axis}_vs_time.png")


def _plot_gaze_direction(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    for axis, color in zip("xyz", ("tab:blue", "tab:orange", "tab:green")):
        ax.plot(df["time_ms"], df[f"gaze_dir_{axis}"], linewidth=0.8,
                color=color, label=f"gaze_dir_{axis}")
    ax.set_title("Real XARP Gaze Direction vs Time")
    ax.set_xlabel("time_ms")
    ax.set_ylabel("gaze direction component")
    ax.legend()
    _save(fig, "real_gaze_direction_vs_time.png")


def _write_summary(df: pd.DataFrame) -> None:
    path = _PLOTS / "summary_stats.txt"
    rows = len(df)
    hits = int(df["hit"].astype(bool).sum()) if "hit" in df.columns else 0
    in_out = int(df["in_out"].astype(bool).sum()) if "in_out" in df.columns else 0
    reasons = dict(Counter(df["reason"])) if "reason" in df.columns else {}

    lines = [
        "Real XARP eye -> video plane projection summary",
        "=" * 48,
        f"rows:            {rows}",
        f"valid hit count: {hits}",
        f"in_out count:    {in_out}",
        f"reason counts:   {reasons}",
        "",
        "Plane assumptions used (validate with Arthur):",
        f"  plane_center: {_col_first(df, 'plane_center_x')}, "
        f"{_col_first(df, 'plane_center_y')}, {_col_first(df, 'plane_center_z')}",
        f"  plane_normal: {_col_first(df, 'plane_normal_x')}, "
        f"{_col_first(df, 'plane_normal_y')}, {_col_first(df, 'plane_normal_z')}",
        f"  plane_width:  {_col_first(df, 'plane_width')}",
        f"  plane_height: {_col_first(df, 'plane_height')}",
        "  local forward vector assumption: [0, 0, -1]",
        "",
    ]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    print(f"Saved {path}")
    print(text)


def _col_first(df: pd.DataFrame, col: str):
    if col in df.columns and len(df):
        return df[col].iloc[0]
    return "n/a"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the real XARP eye -> video plane projection output.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to output/xarp_eye_plane_projection_<timestamp>.csv",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    csv_path = Path(args.input)
    if not csv_path.is_file():
        print(f"Input CSV not found: {csv_path}\nRun project_xarp_eye_to_plane.py first.")
        return 1

    df = pd.read_csv(csv_path)
    _PLOTS.mkdir(parents=True, exist_ok=True)

    if df.empty:
        print("Projection CSV has no rows; writing summary only.")
        _write_summary(df)
        return 0

    _plot_plane_uv(df)
    _plot_in_out_vs_time(df)
    for axis in ("x", "y", "z"):
        _plot_hit_axis(df, axis)
    _plot_gaze_direction(df)
    _write_summary(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
