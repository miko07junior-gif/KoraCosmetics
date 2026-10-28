"""Mesh primitives for the high-resolution model.

Every primitive is built in its own local frame and returns a Prim: flat-shaded
triangles plus the local bounding box, which the clipping check uses as a
conservative oriented box. Units are model pixels (1/16 block).
"""
import math

import numpy as np


class Prim:
    def __init__(self, tris, lo, hi, material, name=""):
        self.tris = np.asarray(tris, float).reshape(-1, 3, 3)
        self.lo = np.asarray(lo, float)
        self.hi = np.asarray(hi, float)
        self.material = material
        self.name = name

    def transformed(self, m):
        """Bake a 4x4 placement into the triangles; the OBB keeps the placement as its frame."""
        p = Prim(_apply(m, self.tris.reshape(-1, 3)).reshape(-1, 3, 3), self.lo, self.hi, self.material, self.name)
        p.frame = m @ getattr(self, "frame", np.eye(4))
        return p


def _apply(m, pts):
    return pts @ m[:3, :3].T + m[:3, 3]


def _area2(poly):
    x, y = poly[:, 0], poly[:, 1]
    return np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def triangulate(poly):
    """Ear clipping for a simple polygon (CCW). Returns index triples."""
    idx = list(range(len(poly)))
    out = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                d1 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
                d2 = (c[0] - b[0]) * (p[1] - b[1]) - (c[1] - b[1]) * (p[0] - b[0])
                d3 = (a[0] - c[0]) * (p[1] - c[1]) - (a[1] - c[1]) * (p[0] - c[0])
                if d1 >= -1e-12 and d2 >= -1e-12 and d3 >= -1e-12:
                    ok = False
                    break
            if ok:
                out.append((i0, i1, i2))
                idx.pop(k)
                break
        else:
            break
    if len(idx) == 3:
        out.append(tuple(idx))
    return out


def inset(poly, d):
    """Miter-offset a CCW polygon inward by d (clamped at sharp corners)."""
    n = len(poly)
    out = np.zeros_like(poly)
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        e0 = p1 - p0
        e1 = p2 - p1
        e0 /= np.linalg.norm(e0) + 1e-12
        e1 /= np.linalg.norm(e1) + 1e-12
        n0 = np.array([-e0[1], e0[0]])
        n1 = np.array([-e1[1], e1[0]])
        m = n0 + n1
        ml = np.linalg.norm(m)
        if ml < 1e-6:
            out[i] = p1 + n0 * d
            continue
        m /= ml
        s = d / max(m @ n0, 0.35)
        out[i] = p1 + m * s
    return out


def extrude(poly, thickness, bevel=0.0, material="bronze", name=""):
    """Extrude a 2D outline (in local XY) along Z, centred on z=0, with a chamfer."""
    poly = np.asarray(poly, float)
    if _area2(poly) < 0:
        poly = poly[::-1]
    t = thickness / 2.0
    b = min(bevel, t * 0.9)
    inner = inset(poly, b) if b > 0 else poly
    rings = [(inner, -t), (poly, -t + b), (poly, t - b), (inner, t)] if b > 0 else [(poly, -t), (poly, t)]
    tris = []
    tri_idx = triangulate(inner)
    for i0, i1, i2 in tri_idx:
        a, c, d = inner[i0], inner[i1], inner[i2]
        tris.append([[*a, t], [*c, t], [*d, t]])
        tris.append([[*a, -t], [*d, -t], [*c, -t]])
    n = len(poly)
    for (ra, za), (rb, zb) in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            p00, p01 = [*ra[i], za], [*ra[j], za]
            p10, p11 = [*rb[i], zb], [*rb[j], zb]
            tris.append([p00, p01, p11])
            tris.append([p00, p11, p10])
    lo = np.array([poly[:, 0].min(), poly[:, 1].min(), -t])
    hi = np.array([poly[:, 0].max(), poly[:, 1].max(), t])
    return Prim(tris, lo, hi, material, name)


def rect(w, h, cx=0.0, cy=0.0):
    return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]])


def box(size, bevel=0.0, material="bronze", name=""):
    sx, sy, sz = size
    return extrude(rect(sx, sy), sz, bevel, material, name)


def ngon(r, n, phase=0.0):
    a = phase + np.arange(n) * 2 * math.pi / n
    return np.stack([r * np.cos(a), r * np.sin(a)], 1)


def cylinder(r, h, n=12, bevel=0.0, material="brass", name=""):
    """Axis along local Z."""
    return extrude(ngon(r, n, math.pi / n), h, bevel, material, name)


def gear_outline(r_root, r_tip, teeth, tip_frac=0.45):
    pts = []
    for k in range(teeth):
        a0 = 2 * math.pi * k / teeth
        da = 2 * math.pi / teeth
        for f, r in ((0.0, r_root), (0.5 - tip_frac / 2 - 0.08, r_root), (0.5 - tip_frac / 2, r_tip),
                     (0.5 + tip_frac / 2, r_tip), (0.5 + tip_frac / 2 + 0.08, r_root)):
            a = a0 + f * da
            pts.append([r * math.cos(a), r * math.sin(a)])
    return np.array(pts)


def gear(r_root, r_tip, teeth, thickness, bevel=0.05, material="brass", name=""):
    return extrude(gear_outline(r_root, r_tip, teeth), thickness, bevel, material, name)


def arc_band(r_in, r_out, a0, a1, thickness, segs=12, bevel=0.04, material="brass", name=""):
    """Annular sector (angles in radians, CCW from +x), as one outline."""
    a = np.linspace(a0, a1, segs + 1)
    outer = np.stack([r_out * np.cos(a), r_out * np.sin(a)], 1)
    inner = np.stack([r_in * np.cos(a[::-1]), r_in * np.sin(a[::-1])], 1)
    return extrude(np.concatenate([outer, inner]), thickness, bevel, material, name)


def _half_blade(length, w_base, w_mid, steps, step_len):
    """Right half of a blade, base to just below the tip: taper, then Chrysler-style setbacks."""
    body = length - steps * step_len - step_len * 0.6
    hw = w_mid / 2
    pts = [[w_base / 2, 0.0], [hw, body * 0.45], [hw, body]]
    x = hw
    for s in range(1, steps + 1):
        x_new = hw * (1 - s / (steps + 1))
        y = body + (s - 1) * step_len
        pts += [[x_new, y + 0.12 * step_len], [x_new, y + step_len]]
        x = x_new
    return np.array(pts)


def _notched(half, notch_y, depth):
    out = [half[0]]
    for p0, p1 in zip(half[:-1], half[1:]):
        if notch_y is not None and p0[1] < notch_y < p1[1]:
            f = (notch_y - p0[1]) / (p1[1] - p0[1])
            q = p0 + f * (p1 - p0)
            out += [q + [0, -0.3], [q[0] - depth, notch_y + 0.1], q + [0, 0.3]]
        out.append(p1)
    return np.array(out)


def blade_outline(length, w_base, w_mid, steps=3, step_len=None, notch=None):
    """Art deco blade-feather in local XY: base at y=0, pointing +y, ending in a stepped
    point like the Chrysler crown's setbacks. notch=(y, depth, side) chips a tatter
    out of the right (+1) or left (-1) edge."""
    step_len = step_len or length * 0.07
    half = _half_blade(length, w_base, w_mid, steps, step_len)
    right = _notched(half, notch[0], notch[1]) if notch and notch[2] > 0 else half
    left = _notched(half, notch[0], notch[1]) if notch and notch[2] < 0 else half
    left = left[::-1] * [-1, 1]
    return np.concatenate([right, [[0.0, length]], left])


def lancet_outline(w, h, point=0.6, segs=8):
    """Gothic lancet window outline, base at y=0: straight jambs, two arcs meeting at a point.
    point = arc radius as a multiple of w (0.5 = round, 1.0 = equilateral)."""
    r = max(point, 0.5) * w
    cx = w / 2 - r                      # centre of the right-hand arc (on the left side)
    rise = math.sqrt(max(r * r - cx * cx, 1e-9))
    base_y = h - rise
    right = [[w / 2, 0.0], [w / 2, base_y]]
    for k in range(1, segs):
        y = base_y + rise * k / segs
        right.append([cx + math.sqrt(max(r * r - (y - base_y) ** 2, 0.0)), y])
    right = np.array(right)
    left = right[::-1] * [-1, 1]
    return np.concatenate([right, [[0.0, h]], left])


def place(prim, pos=(0, 0, 0), rot=None):
    """rot: 3x3. Returns the prim baked at pos/rot (its OBB frame follows)."""
    m = np.eye(4)
    if rot is not None:
        m[:3, :3] = rot
    m[:3, 3] = pos
    return prim.transformed(m)


def frame_from(x_axis, y_axis):
    """Rotation whose local +y points along y_axis and local +x along x_axis (orthogonalised)."""
    y = np.asarray(y_axis, float)
    y /= np.linalg.norm(y)
    x = np.asarray(x_axis, float)
    x = x - (x @ y) * y
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)
