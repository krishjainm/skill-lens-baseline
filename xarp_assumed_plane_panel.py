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
#
# COORDINATE-SYSTEM CLARIFICATION (from Arthur): the Quest runtime is
# right-handed-feeling with x+ = right, y+ = up, z+ = FORWARD (toward where the
# user looks). A plane at z=-1.0 therefore sits BEHIND the viewer, which is why
# the panel/cursor were invisible. For the default visible test we place the
# plane IN FRONT at z=+1.0 with its normal pointing back at the viewer (-Z).
PLANE_CENTER = (0.0, 0.0, 1.0)
PLANE_NORMAL = (0.0, 0.0, -1.0)
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

# Gaze cursor: a small white sphere that rides on the panel surface, tracking
# where the eye ray intersects the assumed plane (default fixed-plane mode).
GAZE_CURSOR_COLOR = (1.0, 1.0, 1.0, 1.0)  # white, distinct from the red center dot
GAZE_CURSOR_SCALE = 0.05

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
    parser.add_argument(
        "--fixed-in-front",
        action="store_true",
        help="Capture the eye pose on the FIRST valid frame, place the panel "
             "1.0 m in front along that ray, then freeze it in world space "
             "forever (never re-read the eye after frame 0).",
    )
    return parser.parse_args()


def _panel_rotation() -> Quaternion:
    """Identity (normal -> +Z), or 180 deg about Y when FLIP_PANEL is set."""
    if FLIP_PANEL:
        return Quaternion.from_euler_angles(0.0, 180.0, 0.0)
    return Quaternion.identity()


def _ray_plane_intersection(origin: Vector3, direction: Vector3) -> Vector3 | None:
    """Intersect the eye ray with the assumed plane.

    Plane is defined by PLANE_CENTER (a point on it) and PLANE_NORMAL. Solving
    n . (origin + t*direction - plane_point) = 0  for t gives
        t = n . (plane_point - origin) / (n . direction)

    Returns the world-space hit point, or None when the ray is parallel to the
    plane (denominator ~ 0) or the intersection is behind the viewer (t <= 0).
    """
    plane_point = Vector3(*PLANE_CENTER)
    plane_normal = Vector3(*PLANE_NORMAL)

    denom = direction.dot(plane_normal)
    if abs(denom) < 1e-6:
        return None  # ray is parallel to the plane

    t = (plane_point - origin).dot(plane_normal) / denom
    if t <= 0.0:
        return None  # plane is behind the viewer

    return origin + direction * t


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

    # White gaze cursor. Starts at the plane center; its position is updated
    # every frame in default mode from the eye-ray/plane intersection. It lives
    # in *markers* so the existing per-frame re-send loop keeps it persisted.
    markers.append(Element(
        key="gaze_cursor",
        asset=DefaultAssets.sphere(),
        color=GAZE_CURSOR_COLOR,
        transform=Transform(
            position=Vector3(*PLANE_CENTER),
            scale=Vector3.one() * GAZE_CURSOR_SCALE,
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

    if cli_args.follow_eye:
        mode = "follow-eye"
    elif cli_args.fixed_in_front:
        mode = "fixed-in-front"
    else:
        mode = "fixed assumed plane"
    print("=" * 60)
    print("  Assumed-plane panel sanity check")
    print(f"  mode={mode}")
    print(f"  plane_center={PLANE_CENTER}  plane_normal={PLANE_NORMAL}")
    print(f"  panel_scale={PANEL_SCALE}  flip={FLIP_PANEL}")
    print("  Press Ctrl+C to stop." if duration == 0 else f"  Duration: {duration}s")
    print("=" * 60)

    panel, markers = build_elements()
    gaze_cursor = next(m for m in markers if m.key == "gaze_cursor")

    # Place the panel + markers in WORLD space exactly once. In default mode the
    # panel transform computed here is never touched again, so the panel stays
    # pinned to the assumed plane no matter where the user looks or walks. The
    # gaze cursor (a marker) IS updated each frame in default mode below.
    xr.update(panel)
    for marker in markers:
        xr.update(marker)

    if cli_args.follow_eye:
        print("FOLLOW EYE MODE: panel follows eye ray")
    elif cli_args.fixed_in_front:
        print("FIXED IN FRONT MODE: waiting for first valid eye frame...")
    else:
        print(f"DEFAULT FIXED MODE: panel position = "
              f"{tuple(panel.transform.position)}")

    # We only need the eye stream for follow-eye / fixed-in-front capture and
    # for the optional per-frame readout. The default mode NEVER uses the eye
    # pose to move or rotate the panel.
    stream = xr.sense(eye=True)
    start_time = time.time()
    frame_index = 0

    # --fixed-in-front captures the eye pose on the first valid frame, then
    # freezes the panel transform in world space forever.
    fixed_in_front_captured = False

    try:
        for frame in stream:
            if STOP_FLAG:
                break
            if duration > 0 and (time.time() - start_time) >= duration:
                break

            eye = frame.get("eye") if isinstance(frame, dict) else None

            if cli_args.follow_eye:
                # --follow-eye is the ONLY mode that continuously reads the eye
                # pose to drive the panel (like demos/video_feed.py), for
                # comparison with the fixed plane.
                if eye is not None:
                    panel.transform.position = eye.ray_point(0.8)
                    panel.transform.rotation = eye.rotation
                xr.update(panel)
            elif cli_args.fixed_in_front:
                # Read the eye pose exactly ONCE (first valid frame), place the
                # panel 1.0 m down that ray, freeze it, and never read the eye
                # again. Afterwards we only re-send the frozen transform so the
                # element persists in the scene.
                if not fixed_in_front_captured and eye is not None:
                    panel.transform.position = eye.ray_point(1.0)
                    panel.transform.rotation = eye.rotation
                    fixed_in_front_captured = True
                    print("FIXED IN FRONT MODE: captured initial eye pose and "
                          "froze panel")
                xr.update(panel)
            else:
                # Default world-fixed mode: the panel stays put (re-send the
                # SAME fixed transform). The gaze cursor rides on the panel
                # surface, tracking the eye-ray/plane intersection each frame.
                xr.update(panel)

                hit = _ray_plane_intersection(eye.position, eye.forward) \
                    if eye is not None else None
                if hit is not None:
                    gaze_cursor.transform.position = hit

                if not cli_args.quiet and eye is not None and frame_index % 30 == 0:
                    print(f"[frame {frame_index}] eye.position={eye.position} "
                          f"eye.forward={eye.forward} "
                          f"gaze_cursor.position={gaze_cursor.transform.position} "
                          f"{'hit' if hit is not None else 'no-hit'}")

            # Re-send all markers (incl. the gaze cursor) so they persist and
            # the cursor's updated position is pushed to the device.
            for marker in markers:
                xr.update(marker)

            # --follow-eye / --fixed-in-front keep their original readout
            # (default mode prints its own gaze-cursor readout above).
            if (cli_args.follow_eye or cli_args.fixed_in_front) \
                    and not cli_args.quiet and eye is not None \
                    and frame_index % 30 == 0:
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
