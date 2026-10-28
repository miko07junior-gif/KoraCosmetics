"""Tiny z-buffer rasteriser for flat-valued box models (silhouettes, notan, value keys,
occlusion maps). It samples one ray per pixel centre with no anti-aliasing, which is
how vanilla Minecraft rasterises geometry, so the 30-block thumbnails show the same
stair-stepping the game does.
"""
import math

import numpy as np

FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def _tris(corners):
    for a, b, c, d in FACES:
        yield corners[a], corners[b], corners[c]
        yield corners[a], corners[c], corners[d]


class Camera:
    """Either orthographic (scale = px per world unit) or perspective (vfov in degrees)."""

    def __init__(self, eye, target, up=(0, 1, 0), width=256, height=256, vfov=None, scale=None, centre=None):
        self.eye = np.asarray(eye, float)
        f = np.asarray(target, float) - self.eye
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, np.asarray(up, float))
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.w, self.h = width, height
        self.vfov = vfov
        self.scale = scale
        self.centre = np.asarray(centre if centre is not None else target, float)

    def project(self, pts):
        d = pts - self.eye
        x, y, z = d @ self.r, d @ self.u, d @ self.f
        if self.vfov is None:
            c = self.centre - self.eye
            cx, cy = c @ self.r, c @ self.u
            sx = self.w / 2 + (x - cx) * self.scale
            sy = self.h / 2 - (y - cy) * self.scale
            return np.stack([sx, sy, z], 1)
        k = (self.h / 2) / math.tan(math.radians(self.vfov) / 2)
        z = np.maximum(z, 1e-4)
        return np.stack([self.w / 2 + x / z * k, self.h / 2 - y / z * k, z], 1)


def rasterise(cam, items):
    """items: iterable of (corners[8,3], value). Returns (value image, depth image).
    `value` can be any int id; background is -1."""
    img = np.full((cam.h, cam.w), -1, np.int32)
    zbuf = np.full((cam.h, cam.w), np.inf)
    for corners, val in items:
        sp = cam.project(np.asarray(corners, float))
        for a, b, c in _tris(sp):
            xs = (a[0], b[0], c[0])
            ys = (a[1], b[1], c[1])
            x0 = max(int(math.floor(min(xs))), 0)
            x1 = min(int(math.ceil(max(xs))), cam.w - 1)
            y0 = max(int(math.floor(min(ys))), 0)
            y1 = min(int(math.ceil(max(ys))), cam.h - 1)
            if x0 > x1 or y0 > y1:
                continue
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if abs(area) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            w0 = ((b[0] - gx) * (c[1] - gy) - (b[1] - gy) * (c[0] - gx)) / area
            w1 = ((c[0] - gx) * (a[1] - gy) - (c[1] - gy) * (a[0] - gx)) / area
            w2 = 1.0 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any():
                continue
            depth = w0 * a[2] + w1 * b[2] + w2 * c[2]
            sub_z = zbuf[y0:y1 + 1, x0:x1 + 1]
            win = inside & (depth < sub_z)
            sub_z[win] = depth[win]
            img[y0:y1 + 1, x0:x1 + 1][win] = val
    return img, zbuf


def colourise(ids, palette, background=(0, 0, 0)):
    out = np.zeros(ids.shape + (3,), np.uint8)
    out[:] = background
    for k, rgb in palette.items():
        out[ids == k] = rgb
    return out


def ortho_view(name, centre, extent_px, size, distance=200.0):
    """Named orthographic views around `centre` (world units). extent_px = world units across."""
    dirs = {
        "front": (0, 0, -1),   # camera in front of the wearer, looking at the face
        "back": (0, 0, 1),
        "side": (1, 0, 0),     # from the wearer's right
        "three_quarter": (0.70710678, 0, -0.70710678),       # front-right 3/4
        "three_quarter_back": (0.70710678, 0, 0.70710678),   # back-right 3/4
        "top": (0, 1, 0.0001),
    }
    d = np.asarray(dirs[name], float)
    d /= np.linalg.norm(d)
    c = np.asarray(centre, float)
    up = (0, 0, -1) if name == "top" else (0, 1, 0)
    return Camera(c + d * distance, c, up, size, size, scale=size / extent_px, centre=c)
