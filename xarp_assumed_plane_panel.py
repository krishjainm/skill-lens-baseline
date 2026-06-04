import argparse
import signal
import time

from xarp.entities import DefaultAssets, Element, TextAsset
from xarp.express import SyncXR
from xarp.server import make_qrcode_image, run
from xarp.spatial import Quaternion, Transform, Vector3

# --- Assumed plane (must match project_xarp_eye_to_plane.py) ----------------
# NOTE: these are only used here for VISUALIZATION. The projection math lives in
# project_xarp_eye_to_plane.py and is intentionally not touched by this script.
PLANE_CENTER = (0.0, 0.0, -1.0)
PLANE_NORMAL = (0.0, 0.0, 1.0)
PLANE_WIDTH = 1.0
PLANE_HEIGHT = 0.6

FLIP_PANEL = False

# DEBUG VISUALS: temporarily enlarged + opaque so the panel is easy to spot.
# Panel is scaled 1.5 x 1.0 (wider than the real 1.0 x 0.6 assumed plane) purely
# to make it easier to see; this does NOT change any projection assumptions.
PANEL_SCALE = (1.5, 1.0, 1.0)

PANEL_COLOR = (0.2, 0.5, 1.0, 1.0)   # opaque blue panel
CENTER_DOT_COLOR = (1.0, 0.0, 0.0, 1.0)  # bright red dot at the plane center
CENTER_DOT_SCALE = 0.15  # enlarged from 0.04 for easier debugging

# Distance markers along the gaze axis (z), each a different color, with labels.
# (position, RGBA color, text label)
DISTANCE_MARKERS = [
    ((0.0, 0.0, -0.5), (0.0, 1.0, 0.0, 1.0), "z=-0.5 (green)"),
    ((0.0, 0.0, -1.0), (1.0, 1.0, 0.0, 1.0), "z=-1.0 (yellow / plane center)"),
    ((0.0, 0.0, -2.0), (1.0, 0.0, 1.0, 1.0), "z=-2.0 (magenta)"),
]
MARKER_SCALE = 0.08
LABEL_OFFSET_Y = 0.12  # raise the text label above each marker sphere

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
    parser.add_argument(
        "--follow-eye",
        action="store_true",
        help="Make the panel follow the eye ray (like demos/video_feed.py) for "
             "comparison, instead of staying at the fixed assumed plane.",
    )
    return parser.parse_args()


def _panel_rotation() -> Quaternion:
    """Identity (normal -> +Z), or 180 deg about Y when FLIP_PANEL is set."""
    if FLIP_PANEL:
        return Quaternion.from_euler_angles(0.0, 180.0, 0.0)
    return Quaternion.identity()


def build_elements() -> tuple[Element, list[Element]]:
    """Build the flat panel plus debug markers (center dot, distance spheres, labels).

    Returns (panel, markers) where *markers* is everything except the panel.
    """
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

    markers: list[Element] = []

    # Big bright red sphere right at the assumed plane center.
    markers.append(Element(
        key="assumed_plane_center",
        asset=DefaultAssets.sphere(),
        color=CENTER_DOT_COLOR,
        transform=Transform(
            position=Vector3(*PLANE_CENTER),
            scale=Vector3.one() * CENTER_DOT_SCALE,
        ),
    ))

    # Distance markers along the z axis, each a different color + text label.
    for i, (pos, color, label) in enumerate(DISTANCE_MARKERS):
        markers.append(Element(
            key=f"distance_marker_{i}",
            asset=DefaultAssets.sphere(),
            color=color,
            transform=Transform(
                position=Vector3(*pos),
                scale=Vector3.one() * MARKER_SCALE,
            ),
        ))
        markers.append(Element(
            key=f"distance_label_{i}",
            asset=TextAsset.from_obj(label),
            color=color,
            transform=Transform(
                position=Vector3(pos[0], pos[1] + LABEL_OFFSET_Y, pos[2]),
            ),
        ))

    return panel, markers


def app(xr: SyncXR, *args, **kwargs) -> None:
    global STOP_FLAG

    cli_args = parse_args()
    duration = cli_args.duration

    mode = "follow-eye" if cli_args.follow_eye else "fixed assumed plane"
    print("=" * 60)
    print("  Assumed-plane panel sanity check")
    print(f"  mode={mode}")
    print(f"  plane_center={PLANE_CENTER}  plane_normal={PLANE_NORMAL}")
    print(f"  panel_scale={PANEL_SCALE}  flip={FLIP_PANEL}")
    print("  Press Ctrl+C to stop." if duration == 0 else f"  Duration: {duration}s")
    print("=" * 60)

    panel, markers = build_elements()

    # Place the panel + markers in WORLD space exactly once. In default mode the
    # transform computed here is never touched again, so the panel stays pinned
    # to the assumed plane no matter where the user looks or walks.
    xr.update(panel)
    for marker in markers:
        xr.update(marker)

    if cli_args.follow_eye:
        print("FOLLOW EYE MODE: panel follows eye ray")
    else:
        print(f"DEFAULT FIXED MODE: panel position = "
              f"{tuple(panel.transform.position)}")

    # We only need the eye stream for follow-eye mode and for the optional
    # per-frame readout. The default mode NEVER uses the eye pose to move or
    # rotate the panel.
    stream = xr.sense(eye=True)
    start_time = time.time()
    frame_index = 0

    try:
        for frame in stream:
            if STOP_FLAG:
                break
            if duration > 0 and (time.time() - start_time) >= duration:
                break

            eye = frame.get("eye") if isinstance(frame, dict) else None

            if cli_args.follow_eye:
                # --follow-eye is the ONLY mode that reads the eye pose to drive
                # the panel (like demos/video_feed.py), for comparison with the
                # fixed plane.
                if eye is not None:
                    panel.transform.position = eye.ray_point(0.8)
                    panel.transform.rotation = eye.rotation
                xr.update(panel)
            else:
                # Default world-fixed mode: re-send the SAME fixed transform so
                # the element persists, but never recompute it from eye/head.
                xr.update(panel)

            for marker in markers:
                xr.update(marker)

            if not cli_args.quiet and eye is not None and frame_index % 30 == 0:
                print(f"[frame {frame_index}] eye.position={eye.position} "
                      f"eye.rotation={eye.rotation} "
                      f"panel.position={panel.transform.position}")
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
