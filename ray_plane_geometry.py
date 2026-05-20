"""Pure geometry helpers for ray-plane intersection with a finite rectangular video plane."""
from __future__ import annotations

import math

import numpy as np


def normalize(v) -> np.ndarray:
    """Return unit vector.  Raises ValueError if *v* is near-zero."""
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise ValueError("Cannot normalize a near-zero vector.")
    return v / n


def ray_plane_intersection(
    ray_origin,
    ray_direction,
    plane_point,
    plane_normal,
    eps: float = 1e-9,
) -> tuple[np.ndarray | None, float | None, str]:
    """Intersect a ray with an infinite plane.

    Returns (intersection_point, t, reason).
    *reason* is ``"hit"``, ``"parallel"``, or ``"behind_ray"``.
    """
    ray_origin = np.asarray(ray_origin, dtype=float)
    ray_direction = normalize(ray_direction)
    plane_point = np.asarray(plane_point, dtype=float)
    plane_normal = normalize(plane_normal)

    denom = np.dot(plane_normal, ray_direction)
    if abs(denom) < eps:
        return None, None, "parallel"

    t = float(np.dot(plane_point - ray_origin, plane_normal) / denom)
    if t < 0:
        return None, t, "behind_ray"

    intersection = ray_origin + t * ray_direction
    return intersection, t, "hit"


def make_plane_axes(plane_normal) -> tuple[np.ndarray, np.ndarray]:
    """Return two orthonormal basis vectors (u, v) lying in the plane."""
    plane_normal = normalize(plane_normal)
    world_up = np.array([0.0, 1.0, 0.0])
    if abs(np.dot(plane_normal, world_up)) > 0.99:
        world_up = np.array([1.0, 0.0, 0.0])
    u = normalize(np.cross(world_up, plane_normal))
    v = normalize(np.cross(plane_normal, u))
    return u, v


def plane_local_coordinates(
    point, plane_center, u_axis, v_axis,
) -> tuple[float, float]:
    """Project *point* onto the plane's local (u, v) frame."""
    d = np.asarray(point, dtype=float) - np.asarray(plane_center, dtype=float)
    return float(np.dot(d, u_axis)), float(np.dot(d, v_axis))


def point_inside_rect_plane(
    point, plane_center, u_axis, v_axis, width: float, height: float,
) -> tuple[bool, float, float]:
    """Return (in_out, u, v) — *in_out* is True when the point is inside the rectangle."""
    u, v = plane_local_coordinates(point, plane_center, u_axis, v_axis)
    inside = abs(u) <= width / 2 and abs(v) <= height / 2
    return inside, u, v


def intersect_gaze_with_video_plane(
    ray_origin,
    ray_direction,
    plane_center,
    plane_normal,
    width: float,
    height: float,
) -> dict:
    """Full pipeline: intersect a gaze ray with a finite rectangular video plane.

    Returns a dict with keys:
        hit, in_out, reason, t, hit_x, hit_y, hit_z, plane_u, plane_v
    """
    pt, t, reason = ray_plane_intersection(
        ray_origin, ray_direction, plane_center, plane_normal,
    )
    nan = float("nan")

    if pt is None:
        return {
            "hit": False,
            "in_out": False,
            "reason": reason,
            "t": t,
            "hit_x": nan,
            "hit_y": nan,
            "hit_z": nan,
            "plane_u": nan,
            "plane_v": nan,
        }

    u_axis, v_axis = make_plane_axes(plane_normal)
    inside, u, v = point_inside_rect_plane(
        pt, plane_center, u_axis, v_axis, width, height,
    )
    return {
        "hit": True,
        "in_out": inside,
        "reason": "inside" if inside else "outside",
        "t": t,
        "hit_x": float(pt[0]),
        "hit_y": float(pt[1]),
        "hit_z": float(pt[2]),
        "plane_u": u,
        "plane_v": v,
    }
