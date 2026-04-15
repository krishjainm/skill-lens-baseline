import subprocess
import imageio_ffmpeg
from moviepy import VideoFileClip, concatenate_videoclips

inputs = [
    "videos/IMG_2301.mov",
    "videos/IMG_2304.mov",
    "videos/IMG_2305.mov",
]

converted = []
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

for i, inp in enumerate(inputs, start=1):
    out = f"videos/converted_{i}.mp4"
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", inp,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        out,
    ]
    subprocess.run(cmd, check=True)
    converted.append(out)

clips = [VideoFileClip(path) for path in converted]
final_clip = concatenate_videoclips(clips, method="compose")
final_clip.write_videofile("stitched_output.mp4")