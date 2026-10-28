"""Clockwork Regent gray-box rig (format-neutral).

Authored in the shared world frame (geom.py) with the wearer standing at rest.
The rest pose is FOLDED: every blade hangs from its shoulder hub and the leading
edges rise into the arch. Poses are local rotations (degrees) plus optional
translations added on top of rest, the way Bedrock/GeckoLib/Blockbench animations
work, so the numbers carry over to whatever format Kora loads once that's known.

Frontal-plane angles: phi is measured from straight down, rotating out toward the
wing's own side (right wing: toward +x). rz(+d) raises a right-wing part by d; the
left wing mirrors x and negates z rotations.

Hierarchy (brief: spine -> joint -> feather group, each part on a named pivot):
  regent
    heart -> escape_wheel, pallet          (the single light source)
    spine (bracket + column + yoke)
      shoulder_{r,l}                        (joint housing, static)
        gear, piston cyl -> rod
        humerus -> forearm -> hand          (leading edge; folded = pointed arch)
        coverts / secondaries / primaries   (feather groups) -> blades
"""
import json
import math

import numpy as np

from geom import OBB, Box, about_pivot, rot_zyx

# Every length is in model pixels; change here, re-run the tools.
P = dict(
    back_z=3.25,          # chestplate back face is z=3; 0.25 px clearance
    heart_y=(14.5, 19.5),  # window between the sprinting legging tops and a sneaking, looked-up helmet
    heart_w=4.0,
    heart_depth=3.5,
    standoff_z=11.5,      # front face of the frame: 11.0 clips a sprinting pauldron by 0.02 px at fine sampling
    frame_depth=3.0,
    hub_x=9.5,
    hub_y=22.5,
    # Leading edge, folded: humerus straight up, forearm and hand lean in to meet at the apex.
    humerus=dict(length=7.0, fold=180.0, width=4.0),
    forearm=dict(length=6.0, fold=200.0, width=3.5),
    hand=dict(fold=232.0, width=3.0),   # length solved so the two hands meet at the apex
    apex_gap=0.6,
    # Blades: blackened-bronze plate with a brass rib on the outer edge (the sunburst rays).
    primaries=dict(n=7, length=21.0, width=3.0, fold=(3.0, 7.0), layer=0, rib="brass"),
    secondaries=dict(n=6, length=13.0, width=3.0, fold=(3.5, 7.0), layer=1, rib="brass"),
    coverts=dict(n=5, length=8.0, width=3.0, fold=(4.0, 7.0), layer=2, rib="ivory"),
    spread="rising",
)

# Spread layouts (frontal-plane phi per part; tiers give first/last blade).
# rising:  the sunburst rises behind the wearer like the Chrysler crown / a heraldic eagle
#          "displayed, wings elevated"; the arch splits at the apex and the tiers lift from below.
# lowered: the first gray-box try, fans radiating outward and down; at 30 blocks it read as a bat/moth.
SPREADS = dict(
    rising=dict(humerus=166.0, forearm=163.0, hand=160.0,
                primaries=(74.0, 152.0), secondaries=(79.0, 148.0), coverts=(84.0, 144.0)),
    # rising, narrower (78-146 deg, 19 px primaries): fans merged into solid triangles at 30 blocks.
    rising_narrow=dict(humerus=158.0, forearm=154.0, hand=150.0,
                       primaries=(78.0, 146.0), secondaries=(83.0, 143.0), coverts=(88.0, 140.0)),
    lowered=dict(humerus=120.0, forearm=116.0, hand=112.0,
                 primaries=(22.0, 106.0), secondaries=(27.0, 102.0), coverts=(32.0, 98.0)),
)

TIERS = ("primaries", "secondaries", "coverts")

# Pistons: telescoping pairs. The cylinder is pinned at `anchor` on a static bone and
# aims at `pin`, a point carried by the driven bone; the rod's tip sits on the pin.
# Along the axis the cylinder spans [0, cyl] and the rod [L - rod, L], where L is the
# anchor-pin distance. Travel limits: rod keeps >= 1 px inside the cylinder
# (L <= cyl + rod - 1) and never pokes out of its back (L >= rod + 0.5).
def piston_specs(p):
    hx, hy = p["hub_x"], p["hub_y"]
    zp = p["standoff_z"] + p["frame_depth"] + 1.0
    specs = []
    for side, sx in (("r", 1), ("l", -1)):
        hub = np.array([sx * hx, hy, zp])
        specs.append(dict(name=f"piston_{side}_humerus", side=side, parent=f"shoulder_{side}", driven=f"humerus_{side}",
                          anchor=np.array([sx * 5.0, hy - 1.0, zp]), pin=hub + 4.0 * _dir(p["humerus"]["fold"], sx),
                          cyl=4.5, rod=5.5))
        specs.append(dict(name=f"piston_{side}_primaries", side=side, parent="spine", driven=f"primaries_{side}",
                          anchor=np.array([sx * 1.5, hy - 3.0, zp]), pin=hub + 2.5 * _dir(p["primaries"]["fold"][0] + 180.0, sx),
                          cyl=5.5, rod=5.5))
    return specs


class Bone:
    def __init__(self, name, parent, pivot, boxes=(), rest=(0.0, 0.0, 0.0)):
        self.name = name
        self.parent = parent
        self.pivot = np.asarray(pivot, float)
        self.boxes = list(boxes)
        self.rest = np.asarray(rest, float)  # degrees (x, y, z)


def _dir(phi_deg, sx=1):
    a = math.radians(phi_deg)
    return np.array([sx * math.sin(a), -math.cos(a), 0.0])


def leading_edge_points(p=P, sx=1, state="fold"):
    """Hub, elbow, wrist and tip of one leading edge in the rest frame."""
    hub = np.array([sx * p["hub_x"], p["hub_y"], 0.0])
    elbow = hub + p["humerus"]["length"] * _dir(p["humerus"][state], sx)
    wrist = elbow + p["forearm"]["length"] * _dir(p["forearm"][state], sx)
    tip = wrist + hand_length(p) * _dir(p["hand"][state], sx)
    return hub, elbow, wrist, tip


def hand_length(p=P):
    hub_x = p["hub_x"]
    wrist_x = hub_x + p["humerus"]["length"] * math.sin(math.radians(p["humerus"]["fold"])) \
        + p["forearm"]["length"] * math.sin(math.radians(p["forearm"]["fold"]))
    return (wrist_x - p["apex_gap"]) / abs(math.sin(math.radians(p["hand"]["fold"])))


def _segment(name, parent, start, length, width, z0, depth, tag, rest_deg, extra=()):
    """A bar authored pointing straight up from `start`, rotated to its fold angle by rest."""
    boxes = [Box((start[0] - width / 2, start[1], z0), (width, length, depth), tag, name=name)]
    boxes += list(extra)
    return Bone(name, parent, start, boxes, rest=(0, 0, rest_deg))


def build(p=P):
    z0 = p["standoff_z"]
    fd = p["frame_depth"]
    z1 = z0 + fd
    zc = z0 + fd / 2
    hx, hy = p["hub_x"], p["hub_y"]
    bz = p["back_z"]
    hy0, hy1 = p["heart_y"]
    hd = p["heart_depth"]
    bones = []

    bones.append(Bone("regent", None, (0, 24, 0)))
    bones.append(Bone("heart", "regent", (0, (hy0 + hy1) / 2, bz), [
        Box((-p["heart_w"] / 2, hy0, bz), (p["heart_w"], hy1 - hy0, hd), "bronze", name="heart_case"),
        Box((-1.5, hy0 + 1.0, bz + hd), (3, hy1 - hy0 - 2.0, 0.5), "amber", name="heart_glass"),
    ]))
    wheel_c = np.array([0, (hy0 + hy1) / 2, bz + hd + 0.5])
    bones.append(Bone("escape_wheel", "heart", wheel_c, [
        Box((-2, wheel_c[1] - 0.5, wheel_c[2]), (4, 1, 0.5), "brass", name="wheel_a"),
        Box((-0.5, wheel_c[1] - 2, wheel_c[2]), (1, 4, 0.5), "brass", name="wheel_b"),
    ]))
    bones.append(Bone("pallet", "heart", (0, hy1 - 0.5, bz + hd + 0.5), [
        Box((-2, hy1 - 1.5, bz + hd + 1.0), (4, 1, 0.5), "brass", name="anchor"),
    ]))
    # Spine: heart -> straight back at |x|<=1.5 (outside every arm's reach) -> up to the yoke.
    bones.append(Bone("spine", "regent", (0, hy0 + 2, bz + hd), [
        Box((-1.5, hy0 + 1.0, bz + hd), (3, 3, z0 - bz - hd), "bronze", name="spine_bracket"),
        Box((-1.5, hy0 + 1.0, z0), (3, hy - hy0 + 0.5, fd), "bronze", name="spine_column"),
        Box((-hx + 2, hy - 1.5, z0), (2 * hx - 4, 3, fd), "bronze", name="yoke"),
    ]))

    for side, sx in (("r", 1), ("l", -1)):
        hub = np.array([sx * hx, hy, zc])
        bones.append(Bone(f"shoulder_{side}", "spine", hub, [
            Box((sx * hx - 2, hy - 2, z0 - 0.5), (4, 4, fd + 1.0), "bronze", name="hub_case"),
        ]))
        bones.append(Bone(f"gear_{side}", f"shoulder_{side}", (hub[0], hub[1], z1 + 0.75), [
            Box((sx * hx - 2.5, hy - 1, z1 + 0.5), (5, 2, 0.5), "brass", name="gear_a"),
            Box((sx * hx - 1, hy - 2.5, z1 + 0.5), (2, 5, 0.5), "brass", name="gear_b"),
        ]))
        _, elbow, wrist, tip = leading_edge_points(p, sx, "fold")
        # rest rotation: authored pointing up (phi=180), rotated to its fold phi; children inherit,
        # so each child's rest is relative to its parent.
        hum, fore, hand = p["humerus"], p["forearm"], p["hand"]
        r_h = sx * (hum["fold"] - 180.0)
        r_f = sx * (fore["fold"] - hum["fold"])
        r_k = sx * (hand["fold"] - fore["fold"])
        hub_up = np.array([hub[0], hy, 0.0])
        e_up = hub_up + np.array([0, hum["length"], 0])
        w_up = e_up + np.array([0, fore["length"], 0])
        bones.append(_segment(f"humerus_{side}", f"shoulder_{side}", hub_up, hum["length"], hum["width"],
                              z0 - 0.5, fd + 1.0, "bronze", r_h))
        bones.append(_segment(f"forearm_{side}", f"humerus_{side}", e_up, fore["length"], fore["width"],
                              z0 - 0.25, fd + 0.5, "bronze", r_f,
                              [Box((e_up[0] - 1.75, e_up[1] - 1.25, z0 - 0.75), (3.5, 2.5, fd + 1.5), "brass", name="elbow_knuckle")]))
        L3 = hand_length(p)
        bones.append(_segment(f"hand_{side}", f"forearm_{side}", w_up, L3, hand["width"],
                              z0, fd, "bronze", r_k,
                              [Box((w_up[0] - 1.5, w_up[1] - 1.0, z0 - 0.5), (3, 2, fd + 1.0), "brass", name="wrist_knuckle"),
                               Box((w_up[0] - 1.0, w_up[1] + L3 - 1.0, z0 + 0.5), (2.0, 2.5, 2.0), "ivory", name="finial")]))
        bones.append(Bone(f"elbow_gear_{side}", f"humerus_{side}", (e_up[0], e_up[1], z1 + 0.75), [
            Box((e_up[0] - 1.75, e_up[1] - 0.75, z1 + 0.5), (3.5, 1.5, 0.5), "brass", name="gear_a"),
            Box((e_up[0] - 0.75, e_up[1] - 1.75, z1 + 0.5), (1.5, 3.5, 0.5), "brass", name="gear_b"),
        ], rest=(0, 0, 45)))
        for tier in TIERS:
            t = p[tier]
            zl = z0 + t["layer"] * (fd / 3.0)
            lever = [Box((sx * hx - 0.75, hy, z1 + 0.5), (1.5, 3.25, 1.0), "bronze", name="lever")] if tier == "primaries" else []
            bones.append(Bone(f"{tier}_{side}", f"shoulder_{side}", hub, lever, rest=(0, 0, sx * t["fold"][0])))
            fold_step = (t["fold"][1] - t["fold"][0]) / max(t["n"] - 1, 1)
            for k in range(t["n"]):
                w, L, th = t["width"], t["length"], fd / 3.0
                blade = Box((sx * hx - w / 2, hy - L, zl), (w, L - 1.5, th), "bronze", name=f"{tier}_{k}")
                # Rib on the blade's outer edge, proud by 0.05 px so it reads on both faces.
                rib_x = sx * hx + sx * (w / 2 - 0.5) - 0.5
                rib = Box((rib_x, hy - L - 0.5, zl - 0.05), (1.0, L - 1.5, th + 0.1), t["rib"], name=f"{tier}_{k}_rib")
                seam = Box((sx * hx - 0.25, hy - L + 2.0, zl + th), (0.5, L - 4.0, 0.06),
                           "amber", name=f"{tier}_{k}_seam")
                bones.append(Bone(f"{tier}_{side}_{k}", f"{tier}_{side}", hub, [blade, rib, seam],
                                  rest=(0, 0, sx * k * fold_step)))
    for ps in piston_specs(p):
        a, pin = ps["anchor"], ps["pin"]
        aim = math.degrees(math.atan2(-(pin - a)[0], (pin - a)[1]))
        L = float(np.linalg.norm(pin - a))
        bones.append(Bone(ps["name"] + "_cyl", ps["parent"], a, [
            Box((a[0] - 0.75, a[1], a[2] - 0.75), (1.5, ps["cyl"], 1.5), "bronze", name="cylinder"),
        ], rest=(0, 0, aim)))
        bones.append(Bone(ps["name"] + "_rod", ps["name"] + "_cyl", a, [
            Box((a[0] - 0.5, a[1] + L - ps["rod"], a[2] - 0.5), (1.0, ps["rod"], 1.0), "brass", name="rod"),
        ]))
    return {b.name: b for b in bones}


def mirror_rot(side, deg):
    return deg if side == "r" else -deg


def pose_spread(p=P, t=1.0, tier_t=None, layout=None):
    """Local deltas for a pose between folded (t=0) and spread (t=1). tier_t gives each
    feather tier its own progress for the staggered unfold; t drives the leading edge."""
    tier_t = tier_t or {}
    sp = SPREADS[layout or p["spread"]]
    pose = {}
    hum, fore, hand = p["humerus"], p["forearm"], p["hand"]
    for side, sx in (("r", 1), ("l", -1)):
        d_h = (sp["humerus"] - hum["fold"]) * t
        d_f = ((sp["forearm"] - sp["humerus"]) - (fore["fold"] - hum["fold"])) * t
        d_k = ((sp["hand"] - sp["forearm"]) - (hand["fold"] - fore["fold"])) * t
        pose[f"humerus_{side}"] = (0, 0, mirror_rot(side, d_h))
        pose[f"forearm_{side}"] = (0, 0, mirror_rot(side, d_f))
        pose[f"hand_{side}"] = (0, 0, mirror_rot(side, d_k))
        pose[f"elbow_gear_{side}"] = (0, 0, mirror_rot(side, -2.0 * d_f))
        for tier in TIERS:
            tt = tier_t.get(tier, t)
            spec = p[tier]
            n = spec["n"]
            pose[f"{tier}_{side}"] = (0, 0, mirror_rot(side, (sp[tier][0] - spec["fold"][0]) * tt))
            fold_step = (spec["fold"][1] - spec["fold"][0]) / max(n - 1, 1)
            spread_step = (sp[tier][1] - sp[tier][0]) / max(n - 1, 1)
            for k in range(n):
                pose[f"{tier}_{side}_{k}"] = (0, 0, mirror_rot(side, k * (spread_step - fold_step) * tt))
        # Hub gear turns with the primaries hinge, 2:1.
        d_p = (sp["primaries"][0] - p["primaries"]["fold"][0]) * tier_t.get("primaries", t)
        pose[f"gear_{side}"] = (0, 0, mirror_rot(side, -2.0 * d_p))
    pose.update(solve_pistons(p, pose))
    return pose


_BONES_CACHE = {}


def solve_pistons(p, pose):
    """Aim each cylinder at its pin and slide the rod so its tip sits on the pin."""
    key = json.dumps(p, sort_keys=True)
    if key not in _BONES_CACHE:
        _BONES_CACHE[key] = build(p)
    bones = _BONES_CACHE[key]
    mats = bone_matrices(bones, pose)
    out = {}
    for ps in piston_specs(p):
        a, pin0 = ps["anchor"], ps["pin"]
        driven = mats[ps["driven"]]
        pin = (driven @ np.append(pin0, 1.0))[:3]
        rest_aim = math.degrees(math.atan2(-(pin0 - a)[0], (pin0 - a)[1]))
        aim = math.degrees(math.atan2(-(pin - a)[0], (pin - a)[1]))
        L0, L = float(np.linalg.norm(pin0 - a)), float(np.linalg.norm(pin - a))
        out[ps["name"] + "_cyl"] = (0, 0, aim - rest_aim)
        out[ps["name"] + "_rod"] = (0, 0, 0, 0, L - L0, 0)
    return out


def bone_matrices(bones, pose=None, attach=None):
    """World matrix per bone. attach = body matrix (player.body_attach) or identity."""
    pose = pose or {}
    attach = np.eye(4) if attach is None else attach
    out = {}

    def m_of(name):
        if name in out:
            return out[name]
        b = bones[name]
        val = tuple(pose.get(name, (0, 0, 0)))
        val = val + (0,) * (6 - len(val))
        ang = b.rest + np.asarray(val[:3], float)
        local = about_pivot(b.pivot, rot_zyx(*np.radians(ang)), val[3:])
        parent = m_of(b.parent) if b.parent else attach
        out[name] = parent @ local
        return out[name]

    for n in bones:
        m_of(n)
    return out


def world_boxes(bones, pose=None, attach=None):
    mats = bone_matrices(bones, pose, attach)
    return [OBB(box, mats[name], name, box.tag) for name, b in bones.items() for box in b.boxes]


def piston_report(p=P, steps=41, layout=None):
    """Anchor-pin distance L through the unfold vs each piston's travel limits."""
    rows = []
    for ps in piston_specs(p):
        Ls = []
        for k in range(steps):
            pose = pose_spread(p, t=k / (steps - 1), layout=layout)
            Ls.append(float(np.linalg.norm(ps["anchor"] - ps["pin"])) + pose[ps["name"] + "_rod"][4])
        lo_lim, hi_lim = ps["rod"] + 0.5, ps["cyl"] + ps["rod"] - 1.0
        rows.append(dict(piston=ps["name"], L_min=round(min(Ls), 2), L_max=round(max(Ls), 2),
                         limits=(lo_lim, hi_lim), ok=lo_lim <= min(Ls) and max(Ls) <= hi_lim))
    return rows
