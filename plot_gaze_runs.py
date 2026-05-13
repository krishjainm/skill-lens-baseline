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