import pandas as pd
import matplotlib.pyplot as plt

df1 = pd.read_csv("output/neon_gaze_20260501_161811_-1.csv")  # baseline
df2 = pd.read_csv("output/neon_gaze_20260501_162037_-1.csv")  # eye movement

# Make time start at 0 for each run
df1["time_sec"] = df1["timestamp_unix_seconds"] - df1["timestamp_unix_seconds"].iloc[0]
df2["time_sec"] = df2["timestamp_unix_seconds"] - df2["timestamp_unix_seconds"].iloc[0]

# Time vs X
plt.figure()
plt.plot(df1["time_sec"], df1["x"], label="baseline")
plt.plot(df2["time_sec"], df2["x"], label="eye movement")
plt.title("Time vs X")
plt.xlabel("Time (seconds)")
plt.ylabel("X gaze position")
plt.legend()
plt.show()

# Time vs Y
plt.figure()
plt.plot(df1["time_sec"], df1["y"], label="baseline")
plt.plot(df2["time_sec"], df2["y"], label="eye movement")
plt.title("Time vs Y")
plt.xlabel("Time (seconds)")
plt.ylabel("Y gaze position")
plt.legend()
plt.show()

# X vs Y
plt.figure()
plt.scatter(df1["x"], df1["y"], alpha=0.3, label="baseline")
plt.scatter(df2["x"], df2["y"], alpha=0.3, label="eye movement")
plt.title("X vs Y Gaze Pattern")
plt.xlabel("X gaze position")
plt.ylabel("Y gaze position")
plt.legend()
plt.show()

# ---------------------------------------------------------------------------
# Gaze Time Series Sync Plot
# Uses the time_ms column so gaze time can be compared against video time.
# If time_ms is missing (older CSVs), fall back to timestamp_unix_seconds * 1000.
# Time is normalized so each run starts at 0 ms.
# ---------------------------------------------------------------------------

def _time_ms_col(df: pd.DataFrame) -> pd.Series:
    if "time_ms" in df.columns:
        t = df["time_ms"].astype(float)
    else:
        t = df["timestamp_unix_seconds"] * 1000.0
    return t - t.iloc[0]

for label, df in [("baseline", df1), ("eye movement", df2)]:
    t = _time_ms_col(df)

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5))
    fig.suptitle(f"Gaze Time Series Sync Plot — {label}")

    ax1.plot(t, df["x"], linewidth=0.6, label="x gaze")
    ax1.set_ylabel("Gaze coordinate")
    ax1.legend(loc="upper right")

    ax2.plot(t, df["y"], linewidth=0.6, label="y gaze", color="tab:orange")
    ax2.set_xlabel("Gaze time (ms)")
    ax2.set_ylabel("Gaze coordinate")
    ax2.legend(loc="upper right")

    fig.tight_layout()
    out_name = f"gaze_time_sync_plot_{label.replace(' ', '_')}.png"
    fig.savefig(out_name, dpi=150)
    print(f"Saved {out_name}")
    plt.show()