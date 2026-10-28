"""Clockwork Regent, high-resolution model (v2).

World frame as in geom.py: model pixels, +x wearer's right, +y up, +z behind the
wearer, origin between the feet. The rest pose is FOLDED and is baked into the
geometry; poses are hinge angles (degrees) about each joint's own axis.

Each wing mounts straight onto the upper back with its own root plate. Nothing ties
the two wings together. The escapement heart sits flush on the back between the
two roots: the one light source.

  heart -> escape_wheel, pallet
  root_{r,l}                 (plate on the back)
    shoulder_gear
    humerus_piston_cyl -> humerus_piston_rod
    shoulder -> humerus      (swept back so a swinging arm passes under it)
      elbow_gear
      forearm -> hand        (folded: these meet over the head as a pointed arch)
      coverts / secondaries / primaries -> blades
"""
import math

import numpy as np

import mesh
from mesh import Prim, arc_band, blade_outline, box, cylinder, extrude, frame_from, gear, lancet_outline, ngon, place

P = dict(
    back_z=3.0,                  # chestplate back face; Kora may offset for bare backs
    shoulder=(1.05, 21.9, 3.95), # right-wing shoulder joint, sunk flush into the plate on the shoulder blade
    ball_r=0.75,
    knee=(1.85, 2.15, 1.95),      # humerus lifts this far (x, y, z) over the shoulder line before the straight run
    elbow=(7.6, 28.6),           # folded: the arch springs here
    arch_r_frac=0.70,            # arc radius / span: 0.5 round, 1.0 equilateral
    apex_gap=0.12,
    arch_split=0.47,             # where the arch arc splits into forearm | hand
    wing_z=5.95,                 # centre of the wing's frontal plane (a helmet's back face is z=5)
    humerus_spread=127.0,        # phi of the humerus when spread (folded is set by shoulder->elbow)
    forearm_spread=160.0,        # phi of the forearm chord when spread
    hand_spread=150.0,
    tiers=dict(
        primaries=dict(n=7, length=10.5, ext=6.0, w_base=1.25, w_mid=2.3, fold=(206.0, 212.0), spread=(66.0, 150.0), layer=-0.95),
        secondaries=dict(n=6, length=8.6, ext=0.0, w_base=1.25, w_mid=2.2, fold=(198.0, 205.0), spread=(72.0, 146.0), layer=-0.45),
        coverts=dict(n=5, length=5.8, ext=0.0, w_base=1.3, w_mid=2.2, fold=(190.0, 198.0), spread=(78.0, 142.0), layer=0.05),
    ),
    blade_thickness=0.4,
    tatters={("primaries", 2): (6.0, 0.5, 1), ("primaries", 5): (7.5, 0.45, -1), ("secondaries", 3): (5.0, 0.4, 1)},
    short_blade=("primaries", 4, 1.2),
)

TIERS = ("primaries", "secondaries", "coverts")
MATERIALS = {
    # name: (base colour, metallic, roughness, emissive colour, emissive strength)
    "bronze": ((0.17, 0.13, 0.105), 0.85, 0.52, None, 0.0),
    "bronze_dark": ((0.10, 0.08, 0.07), 0.8, 0.6, None, 0.0),
    "brass": ((0.62, 0.47, 0.22), 1.0, 0.34, None, 0.0),
    "ivory": ((0.86, 0.82, 0.71), 0.0, 0.42, None, 0.0),
    "verdigris": ((0.26, 0.45, 0.39), 0.3, 0.7, None, 0.0),
    "amber": ((0.95, 0.55, 0.15), 0.0, 0.25, (1.0, 0.55, 0.12), 0.35),
    "seam": ((0.35, 0.18, 0.05), 0.0, 0.5, (1.0, 0.55, 0.12), 0.25),
    "seam_lit": ((1.0, 0.7, 0.35), 0.0, 0.4, (1.0, 0.6, 0.18), 3.0),
}


class Joint:
    def __init__(self, name, parent, pivot, axis=(0, 0, 1), kind="hinge"):
        self.name = name
        self.parent = parent
        self.pivot = np.asarray(pivot, float)
        self.axis = np.asarray(axis, float) / np.linalg.norm(axis)
        self.kind = kind          # hinge | slide | seam (scales along `axis` from pivot)
        self.prims = []
        self.side = None


def _dir(phi, u, v=np.array([0.0, 1.0, 0.0])):
    a = math.radians(phi)
    return math.sin(a) * u - math.cos(a) * v


def rodrigues(axis, deg):
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def arch_geometry(p=P):
    """Folded right half of the arch: springs vertically at the elbow, arcs in to the apex.
    Returns (centre, radius, theta_elbow, theta_wrist, theta_apex) in the frontal plane."""
    ex, ey = p["elbow"]
    span = 2 * ex
    r = p["arch_r_frac"] * span
    cx, cy = ex - r, ey
    th_apex = math.acos((p["apex_gap"] - cx) / r)
    th_wrist = th_apex * p["arch_split"]
    return np.array([cx, cy]), r, 0.0, th_wrist, th_apex


def arc_pt(p, th, z=None):
    c, r, *_ = arch_geometry(p)
    return np.array([c[0] + r * math.cos(th), c[1] + r * math.sin(th), p["wing_z"] if z is None else z])


def key_points(p=P):
    """Right wing shoulder, elbow, wrist, apex tip (folded rest)."""
    c, r, th_e, th_w, th_t = arch_geometry(p)
    S = np.array(p["shoulder"], float)
    return S, arc_pt(p, th_e), arc_pt(p, th_w), arc_pt(p, th_t)


def phi_of(v):
    """Frontal-plane angle from straight down, toward +x (right wing outward)."""
    return math.degrees(math.atan2(v[0], -v[1])) % 360.0


# ---------------------------------------------------------------- geometry helpers

def bar(a, b, w0, w1, thick, normal, material="bronze", bevel=0.18, name=""):
    """Tapered plate from point a to b, lying in the plane with the given normal."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = np.linalg.norm(b - a)
    y = (b - a) / L
    x = np.cross(y, normal)
    outline = np.array([[-w0 / 2, 0], [w0 / 2, 0], [w1 / 2, L], [-w1 / 2, L]])
    # chamfer the far corners so bars read as forged, not cut
    c = min(w1, w0) * 0.22
    outline = np.array([[-w0 / 2, 0], [w0 / 2, 0], [w1 / 2, L - c], [w1 / 2 - c, L], [-w1 / 2 + c, L], [-w1 / 2, L - c]])
    return place(extrude(outline, thick, bevel, material, name), a, frame_from(x, y))


def on_plane(prim, centre, x_axis, y_axis):
    return place(prim, centre, frame_from(x_axis, y_axis))


def rivet(c, normal, r=0.22, h=0.18, material="brass"):
    n = np.asarray(normal, float)
    x = np.cross(n, [0, 1, 0]) if abs(n[1]) < 0.9 else np.cross(n, [1, 0, 0])
    y = np.cross(n, x)
    return place(cylinder(r, h, 8, 0.05, material, "rivet"), c, np.stack([x / np.linalg.norm(x), y / np.linalg.norm(y), n], 1))


def disc(c, normal, r, h, n=20, material="brass", bevel=0.06, name=""):
    nrm = np.asarray(normal, float)
    nrm /= np.linalg.norm(nrm)
    x = np.cross([0, 1, 0], nrm) if abs(nrm[1]) < 0.9 else np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(nrm, x)
    return place(cylinder(r, h, n, bevel, material, name), c, np.stack([x, y, nrm], 1))


def gear_at(c, normal, r_root, r_tip, teeth, h, material="brass", name="gear"):
    nrm = np.asarray(normal, float)
    nrm /= np.linalg.norm(nrm)
    x = np.cross([0, 1, 0], nrm) if abs(nrm[1]) < 0.9 else np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(nrm, x)
    return place(gear(r_root, r_tip, teeth, h, 0.04, material, name), c, np.stack([x, y, nrm], 1))


def crockets(a, b, side_dir, normal, count, size=0.42, material="brass"):
    """Gothic crockets: small leaf knobs along an edge."""
    out = []
    for k in range(count):
        f = (k + 0.7) / (count + 0.4)
        c = np.asarray(a) + f * (np.asarray(b) - np.asarray(a)) + side_dir * 0.15
        leaf = np.array([[0, 0], [size * 0.55, size * 0.35], [size * 0.25, size], [-size * 0.15, size * 0.55]])
        out.append(place(extrude(leaf, 0.35, 0.06, material, "crocket"), c, frame_from(np.cross(side_dir, normal), side_dir)))
    return out


# ---------------------------------------------------------------- build

def build(p=P):
    J = {}

    def joint(name, parent, pivot, axis=(0, 0, 1), kind="hinge"):
        J[name] = Joint(name, parent, pivot, axis, kind)
        return J[name]

    bz = p["back_z"]
    zf = np.array([0.0, 0.0, 1.0])

    # Heart: flush escapement between the two roots.
    H = np.array([0.0, 17.25, bz + 0.05])
    heart = joint("heart", None, H)
    trefoil = []
    for cx, cy in ((-1.05, 0.2), (1.05, 0.2), (0.0, -1.15)):
        trefoil.append(place(cylinder(1.15, 0.5, 18, 0.08, "bronze_dark", "heart_lobe"), H + [cx, cy, 0.25]))
    heart.prims += trefoil
    heart.prims.append(place(extrude(lancet_outline(1.8, 2.6, 0.7), 0.5, 0.08, "bronze_dark", "heart_crown"), H + [0, 0.9, 0.25]))
    heart.prims += [place(arc_band(1.65, 2.15, 0, math.pi, 1.0, 10, 0.08, "brass", "heart_ring"), H + [0, 0, 1.0]),
                    place(arc_band(1.65, 2.15, math.pi, 2 * math.pi, 1.0, 10, 0.08, "brass", "heart_ring"), H + [0, 0, 1.0])]
    heart.prims.append(place(cylinder(1.68, 0.35, 20, 0.05, "bronze_dark", "heart_floor"), H + [0, 0, 0.68]))
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        heart.prims.append(rivet(H + [2.42 * math.cos(a), 2.42 * math.sin(a) * 0.95, 0.62], zf, 0.16, 0.14))
    heart.prims.append(place(extrude(lancet_outline(0.9, 1.7, 0.8), 0.35, 0.05, "ivory", "heart_finial"), H + [0, 2.3, 0.75]))
    heart.prims.append(place(extrude(lancet_outline(0.6, 0.85, 0.8), 0.3, 0.05, "brass", "heart_pendant"),
                             H + [0, -2.3, 0.7], rodrigues([0, 0, 1], 180)))
    wheel = joint("escape_wheel", "heart", H + [0, 0, 1.0])
    wheel.prims.append(place(gear(1.05, 1.45, 15, 0.22, 0.03, "brass", "escape_wheel"), H + [0, 0, 1.05]))
    wheel.prims.append(place(cylinder(0.32, 0.5, 10, 0.05, "brass", "arbor"), H + [0, 0, 1.2]))
    for k in range(3):
        a = k * 2 * math.pi / 3
        wheel.prims.append(place(box((0.18, 1.0, 0.18), 0.0, "brass", "spoke"), H + [0.5 * math.sin(a), 0.5 * math.cos(a), 1.08],
                                 rodrigues([0, 0, 1], -math.degrees(a))))
    pal = joint("pallet", "heart", H + [0, 1.25, 1.35])
    pal.prims.append(place(box((2.2, 0.28, 0.22), 0.04, "brass", "anchor_bar"), H + [0, 1.25, 1.35]))
    for sx in (-1, 1):
        pal.prims.append(place(box((0.26, 0.75, 0.22), 0.04, "brass", "pallet_hook"), H + [sx * 1.0, 0.9, 1.35],
                               rodrigues([0, 0, 1], sx * 18)))
    pal.prims.append(place(cylinder(0.22, 0.4, 8, 0.04, "brass", "anchor_arbor"), H + [0, 1.25, 1.5]))
    heart.prims.append(place(cylinder(1.6, 0.18, 20, 0.04, "amber", "heart_glass"), H + [0, 0, 1.62]))
    glow = joint("seam_heart", "heart", H + [0, 0, 1.75], kind="glow")
    glow.prims.append(place(cylinder(1.2, 0.08, 20, 0.02, "seam_lit", "heart_glow"), H + [0, 0, 1.76]))

    # Wings: build the right one, mirror for the left.
    right = _build_wing(p, J)
    for name in list(right):
        _mirror_joint(J, name)
    return J


def _arc_segments(p, th0, th1, n, w0, w1, z, thick, material="bronze"):
    """Voussoirs along the arch arc from th0 to th1: short tapered bars, slightly overlapping."""
    out = []
    for k in range(n):
        a0 = th0 + (th1 - th0) * k / n
        a1 = th0 + (th1 - th0) * (k + 1) / n
        pa, pb = arc_pt(p, a0, z), arc_pt(p, a1, z)
        d = (pb - pa) / np.linalg.norm(pb - pa)
        f0, f1 = k / n, (k + 1) / n
        out.append(bar(pa - d * 0.12, pb + d * 0.12, w0 + (w1 - w0) * f0, w0 + (w1 - w0) * f1, thick,
                       np.array([0, 0, 1.0]), material, 0.2, "voussoir"))
    return out


def _build_wing(p, J):
    names = []

    def joint(name, parent, pivot, axis=(0, 0, 1), kind="hinge"):
        J[name] = Joint(name, parent, pivot, axis, kind)
        J[name].side = "r"
        names.append(name)
        return J[name]

    bz = p["back_z"]
    zf = np.array([0.0, 0.0, 1.0])
    S, E, W, T = key_points(p)
    c, r, th_e, th_w, th_t = arch_geometry(p)
    wz = p["wing_z"]

    # Root: a gothic plate lying flat on the shoulder blade; the shoulder joint is sunk into it.
    root = joint("root_r", None, (1.25, 19.0, bz))
    root.prims.append(place(extrude(lancet_outline(1.3, 5.4, 0.8), 0.45, 0.1, "bronze_dark", "root_plate"), (1.05, 15.9, bz + 0.25)))
    root.prims.append(place(extrude(lancet_outline(0.85, 4.0, 0.8), 0.18, 0.04, "brass", "root_trim"), (1.05, 16.5, bz + 0.53)))
    root.prims.append(place(extrude(lancet_outline(0.4, 1.5, 0.85), 0.12, 0.03, "ivory", "root_lancet"), (1.05, 17.0, bz + 0.62)))
    for y in (16.5, 19.4):
        root.prims.append(rivet((0.65, y, bz + 0.5), zf, 0.12, 0.11))
        root.prims.append(rivet((1.45, y, bz + 0.5), zf, 0.12, 0.11))
    seam_root = joint("seam_root_r", "root_r", (1.05, 18.7, bz + 0.62), (0, 1, 0), kind="seam")
    seam_root.prims.append(bar((1.05, 18.7, bz + 0.64), (1.05, 21.0, bz + 0.64), 0.16, 0.16, 0.06, zf, "seam_lit", 0.0, "seam"))
    root.prims.append(bar((1.05, 18.7, bz + 0.61), (1.05, 21.0, bz + 0.61), 0.28, 0.28, 0.05, zf, "seam", 0.0, "seam_dim"))

    sg = joint("shoulder_gear_r", "root_r", S, zf)
    sg.prims.append(gear_at(S + zf * 0.85, zf, 0.55, 0.75, 9, 0.25))
    sg.prims.append(disc(S + zf * 1.02, zf, 0.3, 0.3, 10, "ivory", 0.05, "gear_cap"))

    # Shoulder joint and humerus. The humerus lifts just enough over the shoulder line to pass
    # between a helmet's lower edge and a swinging arm, then runs straight to the elbow.
    sh = joint("shoulder_r", "root_r", S, zf)
    sh.prims.append(disc(S, zf, p["ball_r"], 1.5, 16, "bronze_dark", 0.3, "shoulder_joint"))
    K = S + np.array(p["knee"])
    # Curved root: back first while still under the helmet's lower edge (y < 23), then up.
    M1 = S + np.array([0.5, 0.45, 1.0])
    M2 = S + np.array([1.1, 0.95, 1.8])
    for a_, b_, w in ((S, M1, 1.55), (M1, M2, 1.55), (M2, K, 1.6)):
        d_ = (b_ - a_) / np.linalg.norm(b_ - a_)
        nrm = np.cross(d_, np.array([1.0, 0.0, 0.0]))
        sh.prims.append(bar(a_ - d_ * 0.25, b_ + d_ * 0.25, w, w, 1.2, nrm / np.linalg.norm(nrm), "bronze", 0.22, "humerus_root"))
    for q in (M1, M2):
        sh.prims.append(disc(q, np.array([1.0, 0, 0]), 0.62, 1.7, 12, "brass", 0.1, "root_knuckle"))
    hy_ = (E - K) / np.linalg.norm(E - K)
    hx = np.cross(hy_, zf)
    sh.prims.append(bar(K - hy_ * 0.3, E, 1.95, 1.75, 1.4, zf, "bronze", 0.24, "humerus"))
    sh.prims.append(disc(K + zf * 0.15, zf, 0.8, 1.3, 12, "brass", 0.12, "humerus_knuckle"))
    for sgn in (1, -1):
        sh.prims.append(bar(K + hy_ * 0.8 + hx * sgn * 0.8 + zf * 0.6, E - hy_ * 0.9 + hx * sgn * 0.72 + zf * 0.6,
                            0.28, 0.26, 0.32, zf, "brass", 0.05, "humerus_trim"))
    sh.prims.append(place(extrude(lancet_outline(0.75, 2.2, 0.8), 0.16, 0.03, "ivory", "inlay"), K + hy_ * 1.4 + zf * 0.68, frame_from(hx, hy_)))
    for f in (0.25, 0.75):
        sh.prims.append(rivet(K + (E - K) * f + zf * 0.75, zf, 0.15, 0.12))
    lug = K + hy_ * 1.1 - hx * 0.95
    sh.prims.append(place(box((0.8, 0.9, 0.9), 0.12, "brass", "piston_lug"), lug, frame_from(hx, hy_)))
    seam_h = joint("seam_humerus_r", "shoulder_r", K + hy_ * 0.6 + zf * 0.76, hy_, kind="seam")
    seam_h.prims.append(bar(K + hy_ * 0.6 + zf * 0.76, E - hy_ * 1.0 + zf * 0.76, 0.15, 0.13, 0.06, zf, "seam_lit", 0.0, "seam"))
    sh.prims.append(bar(K + hy_ * 0.6 + zf * 0.74, E - hy_ * 1.0 + zf * 0.74, 0.25, 0.21, 0.05, zf, "seam", 0.0, "seam_dim"))

    # Shoulder piston, lying along the back: cylinder pinned on the root plate, rod on the humerus lug.
    anchor = np.array([0.6, 18.4, bz + 1.0])
    pin = lug.copy()
    _piston(joint, J, "humerus_piston_r", "root_r", "shoulder_r", anchor, pin)

    # Elbow: knuckle, gear and jewel.
    sh.prims.append(disc(E, zf, 1.3, 2.2, 16, "bronze_dark", 0.26, "elbow_knuckle"))
    eg = joint("elbow_gear_r", "shoulder_r", E, zf)
    eg.prims.append(gear_at(E + zf * 1.2, zf, 1.55, 1.95, 18, 0.3))
    eg.prims.append(disc(E + zf * 1.45, zf, 0.7, 0.35, 14, "ivory", 0.06, "elbow_cap"))
    glow_e = joint("seam_elbow_r", "elbow_gear_r", E + zf * 1.66, zf, kind="glow")  # lit jewel
    glow_e.prims.append(disc(E + zf * 1.66, zf, 0.36, 0.12, 10, "seam_lit", 0.03, "elbow_jewel"))

    # Leading edge: forearm and hand are voussoirs on the arch arc, with crockets and cusps.
    fore = joint("forearm_r", "shoulder_r", E, zf)
    fore.prims += _arc_segments(p, th_e, th_w, 4, 2.15, 1.85, wz, 1.4)
    hand = joint("hand_r", "forearm_r", W, zf)
    hand.prims += _arc_segments(p, th_w, th_t, 5, 1.85, 1.15, wz, 1.25)
    for bone, a0, a1, n in ((fore, th_e, th_w, 3), (hand, th_w, th_t, 4)):
        for k in range(n):
            a = a0 + (a1 - a0) * (k + 0.55) / n
            pt = arc_pt(p, a, wz)
            out_dir = np.array([math.cos(a), math.sin(a), 0.0])
            tang = np.array([-math.sin(a), math.cos(a), 0.0])
            leaf = np.array([[0, 0], [0.55, 0.32], [0.3, 0.95], [-0.15, 0.55]])
            w_here = 1.0 if bone is fore else 0.8
            bone.prims.append(place(extrude(leaf, 0.42, 0.06, "brass", "crocket"), pt + out_dir * w_here, frame_from(tang, out_dir)))
            if k % 2 == 1 or bone is hand:
                cusp = np.array([[0, 0], [0.32, -0.45], [0.0, -0.9], [-0.32, -0.45]])
                bone.prims.append(place(extrude(cusp, 0.45, 0.05, "brass", "cusp"), pt - out_dir * (w_here - 0.05) + zf * 0.1,
                                        frame_from(tang, out_dir)))
        # bands between voussoirs
        for k in range(1, 4):
            a = a0 + (a1 - a0) * k / 4
            pt = arc_pt(p, a, wz)
            tang = np.array([-math.sin(a), math.cos(a), 0.0])
            out_dir = np.array([math.cos(a), math.sin(a), 0.0])
            bone.prims.append(place(box((2.0 if bone is fore else 1.6, 0.26, 1.55), 0.05, "brass", "band"), pt, frame_from(out_dir, tang)))
    fore.prims.append(disc(W, zf, 0.8, 1.7, 14, "brass", 0.15, "wrist_knuckle"))
    half_fleur = np.array([[-0.02, -0.5], [0.8, 0.15], [0.62, 1.1], [0.28, 1.45], [-0.02, 2.5]])
    hand.prims.append(place(extrude(half_fleur, 0.75, 0.08, "ivory", "half_finial"), T + [0.0, -0.1, 0.0]))
    for bone, a0, a1, tag in ((fore, th_e, th_w, "forearm"), (hand, th_w, th_t, "hand")):
        n = 3
        for k in range(n):
            q0, q1 = arc_pt(p, a0 + (a1 - a0) * (k + 0.12) / n, wz + 0.74), arc_pt(p, a0 + (a1 - a0) * (k + 0.88) / n, wz + 0.74)
            d = (q1 - q0) / np.linalg.norm(q1 - q0)
            sj = joint(f"seam_{tag}_{k}_r", bone.name, q0, d, kind="seam")
            sj.prims.append(bar(q0, q1, 0.14, 0.13, 0.06, zf, "seam_lit", 0.0, "seam"))
            bone.prims.append(bar(q0 - zf * 0.02, q1 - zf * 0.02, 0.24, 0.22, 0.05, zf, "seam", 0.0, "seam_dim"))

    # Feather tiers hinged at the elbow. Folded they lie inside the arch like archivolts;
    # primaries telescope out of their sheaths when the wing wakes.
    th = p["blade_thickness"]
    for tier in TIERS:
        t = p["tiers"][tier]
        zl = wz + 1.2 + (t["layer"] + 0.95)
        grp = joint(f"{tier}_r", "shoulder_r", E, zf)
        n = t["n"]
        for k in range(n):
            phi = t["fold"][0] + (t["fold"][1] - t["fold"][0]) * k / max(n - 1, 1)
            L = t["length"]
            if p["short_blade"][:2] == (tier, k):
                L -= p["short_blade"][2]
            notch = p["tatters"].get((tier, k))
            d = _dir(phi, np.array([1.0, 0, 0]))
            bx = np.cross(d, zf)
            fr = frame_from(-bx, d)
            base = np.array([E[0], E[1], zl]) + d * 0.9
            bj = joint(f"{tier}_r_{k}", f"{tier}_r", E, zf)
            blade_len = L - 0.9
            if t["ext"] > 0:
                # sheath: open-ended blade plate; the extension blade rides behind it
                ol = np.array([[-t["w_base"] / 2, 0], [t["w_base"] / 2, 0], [t["w_mid"] / 2, blade_len * 0.5], [t["w_mid"] / 2, blade_len],
                               [-t["w_mid"] / 2, blade_len], [-t["w_mid"] / 2, blade_len * 0.5]])
                bj.prims.append(place(extrude(ol, th, 0.08, "bronze", "sheath"), base, fr))
                bj.prims.append(place(box((t["w_mid"] + 0.12, 0.35, th + 0.14), 0.05, "brass", "sheath_lip"), base + d * (blade_len - 0.15), fr))
                ext = joint(f"{tier}_r_{k}_ext", f"{tier}_r_{k}", base, d, kind="slide")
                ext_len = t["ext"] + blade_len * 0.55
                eo = blade_outline(ext_len, t["w_mid"] * 0.86, t["w_mid"] * 0.86, steps=3, notch=notch)
                ext.prims.append(place(extrude(eo, th * 0.8, 0.07, "bronze", "blade"), base + d * (blade_len - ext_len + 0.2) + zf * (th * 0.92), fr))
                ext.prims.append(place(box((0.3, ext_len * 0.8, th * 0.8 + 0.1), 0.04, "brass", "rib"),
                                       base + d * (blade_len - ext_len * 0.55 + 0.2) + zf * (th * 0.92), fr))
                for m, (f, sz) in enumerate(((0.62, 0.7), (0.74, 0.55))):
                    tri = np.array([[-sz / 2, 0], [sz / 2, 0], [0, sz * 1.15]])
                    ext.prims.append(place(extrude(tri, th * 0.8 + 0.06, 0.02, "amber", "window"),
                                           base + d * (blade_len - ext_len + 0.2 + ext_len * f) + bx * 0.5 * (1 if m == 0 else -1) + zf * (th * 0.92), fr))
                ext.travel = t["ext"]
                rib_len = blade_len * 0.86
            else:
                ol = blade_outline(blade_len, t["w_base"], t["w_mid"], steps=3, notch=notch)
                bj.prims.append(place(extrude(ol, th, 0.08, "bronze", "blade"), base, fr))
                rib_len = blade_len * 0.8
            rib_mat = "ivory" if tier == "coverts" else "brass"
            bj.prims.append(place(box((0.32, rib_len, th + 0.12), 0.05, rib_mat, "rib"), base + d * (rib_len / 2 + 0.3), fr))
            bj.prims.append(rivet(base + d * 0.5 + zf * (th / 2 + 0.07), zf, 0.16, 0.11))
            sj = joint(f"seam_{tier}_r_{k}", f"{tier}_r_{k}", base + d * 0.6 + zf * (th / 2 + 0.07), d, kind="seam")
            sj.prims.append(place(box((0.11, rib_len * 0.85, 0.05), 0.0, "seam_lit", "seam"), base + d * (0.6 + rib_len * 0.425) + zf * (th / 2 + 0.08), fr))
            bj.prims.append(place(box((0.19, rib_len * 0.85, 0.04), 0.0, "seam", "seam_dim"), base + d * (0.6 + rib_len * 0.425) + zf * (th / 2 + 0.065), fr))
    return names


def _piston(joint, J, name, parent, driven, anchor, pin, frac=0.6):
    d = (pin - anchor) / np.linalg.norm(pin - anchor)
    L0 = float(np.linalg.norm(pin - anchor))
    cyl = joint(name + "_cyl", parent, anchor, (0, 0, 1))
    rod = joint(name + "_rod", name + "_cyl", anchor, d, kind="slide")
    cyl_len, rod_len = frac * L0, frac * L0
    cyl.prims.append(_along(cylinder(0.4, cyl_len, 12, 0.06, "bronze_dark", "piston_cylinder"), anchor + d * cyl_len / 2, d))
    cyl.prims.append(_along(cylinder(0.48, 0.28, 12, 0.05, "brass", "piston_collar"), anchor + d * (cyl_len - 0.14), d))
    cyl.prims.append(disc(anchor, np.array([0, 0, 1.0]), 0.42, 0.9, 10, "brass", 0.05, "piston_pin"))
    rod.prims.append(_along(cylinder(0.2, rod_len, 10, 0.03, "brass", "piston_rod"), pin - d * rod_len / 2, d))
    rod.prims.append(disc(pin, np.array([0, 0, 1.0]), 0.3, 1.0, 10, "brass", 0.04, "piston_eye"))
    cyl.L0, cyl.cyl_len, cyl.rod_len, cyl.pin_joint, cyl.pin = L0, cyl_len, rod_len, driven, pin


def _along(prim, centre, d):
    """Place a Z-axis primitive (cylinder) so its axis runs along d."""
    d = np.asarray(d, float) / np.linalg.norm(d)
    x = np.cross(d, [0, 1, 0]) if abs(d[1]) < 0.9 else np.cross(d, [1, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(d, x)
    return place(prim, centre, np.stack([x, y, d], 1))


MIRROR = np.diag([-1.0, 1.0, 1.0])


def _mirror_joint(J, name):
    src = J[name]
    lname = name.replace("_r_", "_l_") if "_r_" in name else (name[:-2] + "_l" if name.endswith("_r") else name)
    par = src.parent
    if par and (par.endswith("_r") or "_r_" in par):
        par = par.replace("_r_", "_l_") if "_r_" in par else par[:-2] + "_l"
    j = Joint(lname, par, MIRROR @ src.pivot, src.axis, src.kind)
    # A hinge about axis a on the right is a hinge about -(M a) with the same angle on the left.
    j.axis = -(MIRROR @ src.axis) if src.kind == "hinge" else MIRROR @ src.axis
    j.side = "l"
    for pr in src.prims:
        tris = pr.tris.copy()
        tris[..., 0] *= -1
        tris = tris[:, ::-1, :]
        q = Prim(tris, pr.lo, pr.hi, pr.material, pr.name)
        q.frame = np.diag([-1.0, 1, 1, 1]) @ getattr(pr, "frame", np.eye(4))
        j.prims.append(q)
    for attr in ("L0", "cyl_len", "rod_len"):
        if hasattr(src, attr):
            setattr(j, attr, getattr(src, attr))
    if hasattr(src, "pin_joint"):
        j.pin_joint = src.pin_joint[:-2] + "_l"
        j.pin = MIRROR @ src.pin
    J[lname] = j


# ---------------------------------------------------------------- poses

# Key poses of the unfold, shared by renders, clipping and export.
KEY_POSES = {
    "folded": dict(t=0.0),
    "arch_splits": dict(t=0.0, arch_t=0.45, lift_t=0.3),
    "coverts_rise": dict(t=0.0, arch_t=0.8, lift_t=0.7, tier_t=dict(coverts=0.8)),
    "secondaries_rise": dict(t=0.0, arch_t=1.0, lift_t=1.0, tier_t=dict(coverts=1.0, secondaries=0.8, primaries=0.25), ext_t=0.0),
    "primaries_fan": dict(t=0.0, arch_t=1.0, lift_t=1.0, tier_t=dict(coverts=1.0, secondaries=1.0, primaries=1.0), ext_t=0.3),
    "spread": dict(t=1.0),
}


def fold_angles(p=P):
    S, E, W, T = key_points(p)
    return dict(humerus=phi_of(E - S), forearm=phi_of(W - E), hand=phi_of(T - W))


def pose_state(p=P, t=1.0, tier_t=None, arch_t=None, lift_t=None, ext_t=None, extra=None):
    """Hinge angles (deg) and slides (px) between folded (0) and spread (1). Separate
    progress values stagger the unfold: the arch opens, the humerus lifts, each tier fans
    in turn, then the primaries telescope out."""
    tier_t = tier_t or {}
    arch_t = t if arch_t is None else arch_t
    lift_t = t if lift_t is None else lift_t
    fa = fold_angles(p)
    pose = {}
    for side in ("r", "l"):
        d_h = (p["humerus_spread"] - fa["humerus"]) * lift_t
        w_f = (p["forearm_spread"] - fa["forearm"]) * arch_t          # forearm's total change in the plane
        w_k = (p["hand_spread"] - fa["hand"]) * arch_t
        pose[f"shoulder_{side}"] = d_h
        pose[f"shoulder_gear_{side}"] = -2.0 * d_h
        pose[f"forearm_{side}"] = w_f - d_h
        pose[f"hand_{side}"] = w_k - w_f
        for tier in TIERS:
            tt = tier_t.get(tier, t)
            spec = p["tiers"][tier]
            n = spec["n"]
            pose[f"{tier}_{side}"] = (spec["spread"][0] - spec["fold"][0]) * tt - d_h
            fs = (spec["fold"][1] - spec["fold"][0]) / max(n - 1, 1)
            ss = (spec["spread"][1] - spec["spread"][0]) / max(n - 1, 1)
            for k in range(n):
                pose[f"{tier}_{side}_{k}"] = k * (ss - fs) * tt
                if spec["ext"] > 0:
                    e = tier_t.get(tier, t) if ext_t is None else ext_t
                    pose[f"{tier}_{side}_{k}_ext"] = spec["ext"] * e
        pose[f"elbow_gear_{side}"] = -1.5 * pose[f"primaries_{side}"]
    if extra:
        pose.update(extra)
    return pose


def matrices(J, pose=None, attach=None, seams=None):
    """World 4x4 per joint. pose: {joint: angle_deg or slide}. seams: {joint: scale 0..1}."""
    pose = pose or {}
    seams = seams or {}
    attach = np.eye(4) if attach is None else attach
    out = {}

    def m_of(name):
        if name in out:
            return out[name]
        j = J[name]
        par = m_of(j.parent) if j.parent else attach
        local = np.eye(4)
        if j.kind == "hinge":
            R = rodrigues(j.axis, pose.get(name, 0.0))
            local[:3, :3] = R
            local[:3, 3] = j.pivot - R @ j.pivot
        elif j.kind == "slide":
            local[:3, 3] = j.axis * pose.get(name, 0.0)
        elif j.kind in ("seam", "glow"):
            s = max(seams.get(name, 1.0), 1e-3)
            S = np.eye(3) * s if j.kind == "glow" else np.eye(3) + (s - 1.0) * np.outer(j.axis, j.axis)
            local[:3, :3] = S
            local[:3, 3] = j.pivot - S @ j.pivot
        out[name] = par @ local
        return out[name]

    for n in J:
        m_of(n)
    return out


def solve_pistons(J, pose):
    """Aim each piston cylinder at its pin and slide the rod onto it (after the joints are posed)."""
    pose = dict(pose)
    for name, j in J.items():
        if not hasattr(j, "pin_joint"):
            continue
        mats = matrices(J, pose)
        pin_w = (mats[j.pin_joint] @ np.append(j.pin, 1.0))[:3]
        a = j.pivot
        d0 = (j.pin - a) / np.linalg.norm(j.pin - a)
        d1 = (pin_w - a) / np.linalg.norm(pin_w - a)
        ang = math.degrees(math.atan2(np.cross(d0, d1) @ j.axis, d0 @ d1))
        pose[name] = ang
        pose[name.replace("_cyl_", "_rod_")] = float(np.linalg.norm(pin_w - a) - j.L0)
    return pose


def piston_travel(J, poses):
    """Rod overlap check: the rod must keep >= 0.5 px inside the cylinder and never reach its base."""
    rows = []
    for name, j in J.items():
        if not hasattr(j, "pin_joint"):
            continue
        rod = name.replace("_cyl_", "_rod_")
        slides = [solve_pistons(J, ps)[rod] for ps in poses]
        L = [j.L0 + s for s in slides]
        rod_start = [l - j.rod_len for l in L]          # rod's inner end, measured from the anchor
        overlap = [j.cyl_len - rs for rs in rod_start]
        rows.append(dict(piston=name, L_min=round(min(L), 2), L_max=round(max(L), 2),
                         overlap_min=round(min(overlap), 2), rod_base_min=round(min(rod_start), 2),
                         ok=min(overlap) >= 0.5 and min(rod_start) >= 0.3))
    return rows


def world_obbs(J, pose=None, attach=None, include_seams=False):
    from geom import Box, OBB
    mats = matrices(J, pose, attach)
    out = []
    for name, j in J.items():
        if j.kind in ("seam", "glow") and not include_seams:
            continue
        for pr in j.prims:
            if pr.name in ("seam_dim",):
                continue
            fr = getattr(pr, "frame", np.eye(4))
            out.append(OBB(Box(pr.lo, pr.hi - pr.lo, pr.material, name=pr.name), mats[name] @ fr, name, pr.material))
    return out
