"""Shared geometry for the Clockwork Regent tools.

World frame (used by every tool here), in model pixels (1 px = 1/16 block):
  +x = wearer's right, +y = up, +z = behind the wearer (the back faces +z),
  origin = between the feet. The vanilla player stands from y=0 to y=32.

Rotations use Minecraft's ModelPart order: R = Rz(roll) @ Ry(yaw) @ Rx(pitch).
"""
import itertools
import math

import numpy as np


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def rot_zyx(pitch, yaw, roll):
    return rz(roll) @ ry(yaw) @ rx(pitch)


def affine(rot=None, trans=(0, 0, 0)):
    m = np.eye(4)
    if rot is not None:
        m[:3, :3] = rot
    m[:3, 3] = trans
    return m


def translate(v):
    return affine(trans=v)


def about_pivot(pivot, rot, offset=(0, 0, 0)):
    """Rotate about `pivot`, then move by `offset` (Blockbench/Bedrock bone semantics)."""
    p = np.asarray(pivot, float)
    return translate(p + np.asarray(offset, float)) @ affine(rot) @ translate(-p)


class Box:
    """Axis-aligned box in its bone's rest frame. `tag` names the material/value group."""

    def __init__(self, lo, size, tag="bronze", inflate=0.0, name=""):
        self.lo = np.asarray(lo, float) - inflate
        self.size = np.asarray(size, float) + 2 * inflate
        self.tag = tag
        self.name = name

    @property
    def hi(self):
        return self.lo + self.size

    def corners(self):
        lo, hi = self.lo, self.hi
        return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


class OBB:
    """Oriented box in world space: centre c, unit axes u (rows), half-extents e."""

    def __init__(self, box, m, owner="", tag=""):
        c_local = box.lo + box.size / 2
        self.c = (m @ np.append(c_local, 1))[:3]
        cols = m[:3, :3]
        scale = np.linalg.norm(cols, axis=0)
        scale[scale == 0] = 1
        self.u = (cols / scale).T
        self.e = box.size / 2 * scale
        self.owner = owner
        self.tag = tag
        self.name = box.name

    def corners(self):
        out = []
        for sx, sy, sz in itertools.product((-1, 1), repeat=3):
            out.append(self.c + sx * self.e[0] * self.u[0] + sy * self.e[1] * self.u[1] + sz * self.e[2] * self.u[2])
        return np.array(out)


def obb_gap(a, b):
    """Separating-axis test. Returns the largest gap over the 15 candidate axes:
    > 0 means separated by at least that much (a lower bound on the true distance),
    <= 0 means overlapping, and -value is the shallowest penetration over those axes."""
    axes = [a.u[i] for i in range(3)] + [b.u[i] for i in range(3)]
    for i in range(3):
        for j in range(3):
            v = np.cross(a.u[i], b.u[j])
            n = np.linalg.norm(v)
            if n > 1e-6:
                axes.append(v / n)
    d = b.c - a.c
    best = -1e9
    for ax in axes:
        ra = np.sum(a.e * np.abs(a.u @ ax))
        rb = np.sum(b.e * np.abs(b.u @ ax))
        gap = abs(d @ ax) - ra - rb
        if gap > best:
            best = gap
    return best


def obb_arrays(obbs):
    return (np.array([o.c for o in obbs]), np.array([o.u for o in obbs]), np.array([o.e for o in obbs]))


def obb_gap_matrix(A, B):
    """Vectorised obb_gap for every pair: A, B from obb_arrays(). Returns (len(A), len(B))."""
    ac, au, ae = A
    bc, bu, be = B
    n, m = len(ac), len(bc)
    axes = np.concatenate([
        np.broadcast_to(au[:, None], (n, m, 3, 3)),
        np.broadcast_to(bu[None, :], (n, m, 3, 3)),
        np.cross(au[:, None, :, None, :], bu[None, :, None, :, :]).reshape(n, m, 9, 3),
    ], axis=2)
    norm = np.linalg.norm(axes, axis=-1, keepdims=True)
    valid = norm[..., 0] > 1e-6
    axes = axes / np.where(norm > 1e-6, norm, 1.0)
    d = bc[None, :] - ac[:, None]
    proj_d = np.abs(np.einsum("nmk,nmak->nma", d, axes))
    ra = np.einsum("nb,nmab->nma", ae, np.abs(np.einsum("nbk,nmak->nmab", au, axes)))
    rb = np.einsum("mb,nmab->nma", be, np.abs(np.einsum("mbk,nmak->nmab", bu, axes)))
    gap = np.where(valid, proj_d - ra - rb, -np.inf)
    return gap.max(axis=2)
