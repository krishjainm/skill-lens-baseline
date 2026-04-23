import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import imageio_ffmpeg
from moviepy import VideoFileClip, concatenate_videoclips

from pathutil import try_remove_file

_ROOT = Path(__file__).resolve().parent

_try_remove = try_remove_file


def _ffmpeg_debug_stderr() -> bool:
    v = os.environ.get("STITCH_FFMPEG_DEBUG", "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def main() -> int:
    videos = _ROOT / "videos"
    inputs = [videos / "IMG_2301.mov", videos / "IMG_2304.mov", videos / "IMG_2305.mov"]
    in_strs = [str(p) for p in inputs]

    missing = [p for p in in_strs if not os.path.isfile(p)]
    if missing:
        for p in missing:
            print(f"Missing input file: {p}", file=sys.stderr)
        return 1

    converted: list[str] = []
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    stitched = str(_ROOT / "stitched_output.mp4")

    try:
        for i, inp in enumerate(in_strs, start=1):
            out = str(videos / f"converted_{i}.mp4")
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
            # Non-debug: discard ffmpeg stderr. Debug: write stderr to a temp file (avoids a massive PIPE buffer on success or failure).
            dbg = _ffmpeg_debug_stderr()
            err_path: str | None = None
            err_f: object = subprocess.DEVNULL
            if dbg:
                _fd, err_path = tempfile.mkstemp(suffix=".fferr", text=True)
                os.close(_fd)
                err_f = open(  # noqa: SIM115
                    err_path, "w", encoding="utf-8", errors="replace", newline=""
                )
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=err_f,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                for p in converted:
                    _try_remove(p)
                _try_remove(out)
                if err_f is not subprocess.DEVNULL and hasattr(err_f, "close"):
                    try:
                        err_f.close()
                    except OSError:
                        pass
                    err_f = subprocess.DEVNULL
                if dbg and err_path and os.path.isfile(err_path):
                    try:
                        with open(  # noqa: SIM115
                            err_path, encoding="utf-8", errors="replace"
                        ) as rerr:
                            _tail = rerr.read(200_000)
                        if _tail:
                            print(_tail, file=sys.stderr, end="")
                    except OSError:
                        pass
                elif e.stderr:
                    print(e.stderr, file=sys.stderr, end="")
                elif not dbg:
                    print(
                        "Set STITCH_FFMPEG_DEBUG=1 to write ffmpeg stderr to a temp file on failure.",
                        file=sys.stderr,
                    )
                print(
                    f"ffmpeg failed (exit {e.returncode}) for {inp!r} -> {out!r}.",
                    file=sys.stderr,
                )
                if err_path and os.path.isfile(err_path):
                    try:
                        os.remove(err_path)
                    except OSError:
                        pass
                return 1
            finally:
                if err_f is not subprocess.DEVNULL and hasattr(err_f, "close"):
                    try:
                        err_f.close()
                    except OSError:
                        pass
                if err_path and os.path.isfile(err_path):
                    try:
                        os.remove(err_path)
                    except OSError:
                        pass
            converted.append(out)

        clips: list[VideoFileClip] = []
        final_clip = None
        try:
            for path in converted:
                clips.append(VideoFileClip(path))
            final_clip = concatenate_videoclips(clips, method="compose")
            try:
                final_clip.write_videofile(stitched)
            except KeyboardInterrupt:
                for p in converted:
                    _try_remove(p)
                _try_remove(stitched)
                print("stitch: interrupted", file=sys.stderr)
                return 1
            except Exception:
                _try_remove(stitched)
                raise
            finally:
                if final_clip is not None:
                    try:
                        final_clip.close()
                    except OSError:
                        pass
        finally:
            if final_clip is None and clips:
                for c in clips:
                    try:
                        c.close()
                    except OSError:
                        pass

        for p in converted:
            _try_remove(p)
    except KeyboardInterrupt:
        for p in converted:
            _try_remove(p)
        _try_remove(stitched)
        print("stitch: interrupted", file=sys.stderr)
        return 1
    except Exception as e:
        for p in converted:
            _try_remove(p)
        _try_remove(stitched)
        print(f"stitch failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
