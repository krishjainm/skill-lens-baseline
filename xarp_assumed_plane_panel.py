"""xarp_assumed_plane_panel.py — XR visual sanity-check for our assumed video plane.

Arthur's suggestion: display an image/panel at the SAME location our projection
code assumes for the video plane, so we can eyeball whether the plane placement
is sensible from inside the headset.

This mirrors the panel pattern from HAL-UCSB/xarp ``demos/video_feed.py``, but
instead of following the eye (``eye.ray_point(.49)``) we PIN the panel at the
fixed plane assumed by ``project_xarp_eye_to_plane.py``:

    plane_center = [0, 0, -1.0]
    plane_normal = [0, 0,  1.0]
    plane_width  = 1.0
    plane_height = 0.6

This script only reads the eye pose for an optional console readout; it does not
modify xarp_eye_logger.py, project_xarp_eye_to_plane.py, or ray_plane_geometry.py.
"""

import argparse
import signal
import time

from xarp.entities import DefaultAssets, Element
from xarp.express import SyncXR
from xarp.server import make_qrcode_image, run
from xarp.spatial import Quaternion, Transform, Vector3

# --- Assumed plane (must match project_xarp_eye_to_plane.py) ----------------
PLANE_CENTER = (0.0, 0.0, -1.0)
PLANE_NORMAL = (0.0, 0.0, 1.0)
PLANE_WIDTH = 1.0
PLANE_HEIGHT = 0.6

# ASSUMPTION (rotation): a default Quad lies in its local XY plane. We use the
# IDENTITY rotation, which leaves the quad's surface normal along +Z — matching
# our assumed plane_normal of [0, 0, 1]. XARP/Unity uses a right-handed, Y-up,
# Z-forward convention (see xarp.spatial.Vector3). If the panel looks like it is
# facing AWAY from you in the headset, flip it 180 deg about Y by setting
# FLIP_PANEL = True (we do not silently flip it).
FLIP_PANEL = False

# ASSUMPTION (scale): the default Quad is 1x1 in local units, so scaling X by
# plane_width and Y by plane_height yields a 1.0 x 0.6 panel. Z scale stays 1.0.
PANEL_SCALE = (PLANE_WIDTH, PLANE_HEIGHT, 1.0)

PANEL_COLOR = (0.2, 0.5, 1.0, 0.6)   # semi-transparent blue panel
CENTER_DOT_COLOR = (1.0, 0.0, 0.0, 1.0)  # solid red dot at the plane center
CENTER_DOT_SCALE = 0.04

STOP_FLAG = False


def handle_sigint(sig, frame):
    global STOP_FLAG
    print("\n[xarp_assumed_plane_panel] Ctrl+C received, stopping...")
    STOP_FLAG = True


signal.signal(signal.SIGINT, handle_sigint)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Display a panel at our assumed video-plane location in XARP.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Seconds to keep the panel up (0 = until Ctrl+C). Default: 0.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print the eye pose each frame.",
    )
    return parser.parse_args()


def _panel_rotation() -> Quaternion:
    """Identity (normal -> +Z), or 180 deg about Y when FLIP_PANEL is set."""
    if FLIP_PANEL:
        return Quaternion.from_euler_angles(0.0, 180.0, 0.0)
    return Quaternion.identity()


def build_elements() -> tuple[Element, Element]:
    """Build the flat panel and a small dot marking the plane center."""
    panel = Element(
        key="assumed_plane_panel",
        asset=DefaultAssets.quad(),
        color=PANEL_COLOR,
        transform=Transform(
            position=Vector3(*PLANE_CENTER),
            rotation=_panel_rotation(),
            scale=Vector3(*PANEL_SCALE),
        ),
    )
    center_dot = Element(
        key="assumed_plane_center",
        asset=DefaultAssets.sphere(),
        color=CENTER_DOT_COLOR,
        transform=Transform(
            position=Vector3(*PLANE_CENTER),
            scale=Vector3.one() * CENTER_DOT_SCALE,
        ),
    )
    return panel, center_dot


def app(xr: SyncXR, *args, **kwargs) -> None:
    global STOP_FLAG

    cli_args = parse_args()
    duration = cli_args.duration

    print("=" * 60)
    print("  Assumed-plane panel sanity check")
    print(f"  plane_center={PLANE_CENTER}  plane_normal={PLANE_NORMAL}")
    print(f"  width={PLANE_WIDTH}  height={PLANE_HEIGHT}  flip={FLIP_PANEL}")
    print("  Press Ctrl+C to stop." if duration == 0 else f"  Duration: {duration}s")
    print("=" * 60)

    panel, center_dot = build_elements()
    xr.update(panel)
    xr.update(center_dot)

    # Sense the eye pose only for an optional readout; the panel is pinned to the
    # fixed assumed plane and is re-sent each frame so it persists in the scene.
    stream = xr.sense(eye=True)
    start_time = time.time()
    frame_index = 0

    try:
        for frame in stream:
            if STOP_FLAG:
                break
            if duration > 0 and (time.time() - start_time) >= duration:
                break

            xr.update(panel)
            xr.update(center_dot)

            if not cli_args.quiet:
                eye = frame.get("eye") if isinstance(frame, dict) else None
                if eye is not None and frame_index % 30 == 0:
                    print(f"[frame {frame_index}] eye.position={eye.position} "
                          f"eye.rotation={eye.rotation}")
            frame_index += 1
    except KeyboardInterrupt:
        print("\n[xarp_assumed_plane_panel] KeyboardInterrupt, stopping...")
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:  # noqa: BLE001 - closing should never crash exit
                print(f"[xarp_assumed_plane_panel] stream.close() failed: {exc!r}")

    print(f"\n[xarp_assumed_plane_panel] Done after {frame_index} frames.")


if __name__ == "__main__":
    make_qrcode_image()
    run(app)
