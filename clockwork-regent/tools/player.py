"""Vanilla Minecraft (Java 1.21.x) player model and pose envelope, rebuilt from the
public model dimensions and BipedEntityModel/PlayerEntityModel pose rules.

Parts are built in vanilla ModelPart space (y down, origin at the neck, face at -z)
and mapped into the shared world frame (see geom.py) with W = T(0,24,0) @ diag(-1,-1,1).

This is a stand-in until Kora's own player renderer has been read: Kora may add
poses, scale cosmetics differently or move the cape, and any of that changes the
envelope. Every number here is from vanilla, not from Kora.
"""
import math

import numpy as np

from geom import OBB, Box, about_pivot, affine, rot_zyx, translate

W = translate((0, 24, 0)) @ affine(np.diag([-1.0, -1.0, 1.0]))
W_INV = np.linalg.inv(W)

# Vanilla renders the player model at 15/16 scale (PlayerEntityRenderer.scale).
PLAYER_RENDER_SCALE = 0.9375
EYE_HEIGHT_BLOCKS = 1.62
F5_DISTANCE_BLOCKS = 4.0


def to_world(m_model):
    """Matrix taking vanilla model-space geometry into the world frame."""
    return W @ m_model


def to_world_frame(m_model):
    """The same motion expressed for geometry authored in the world frame (cosmetics)."""
    return W @ m_model @ W_INV


def _part(pivot, pitch=0.0, yaw=0.0, roll=0.0):
    return about_pivot(pivot, rot_zyx(pitch, yaw, roll))


class PlayerPose:
    """Inputs mirror vanilla setAngles. Angles in radians unless noted."""

    def __init__(self, head_pitch_deg=0.0, head_yaw_deg=0.0, limb_angle=0.0, limb_distance=0.0,
                 sneak=False, swing=0.0, arm_pose="empty", age=0.0, cape_deg=6.0, label=""):
        self.head_pitch = math.radians(head_pitch_deg)  # + looks down
        self.head_yaw = math.radians(head_yaw_deg)
        self.limb_angle = limb_angle
        self.limb_distance = limb_distance
        self.sneak = sneak
        self.swing = swing
        self.arm_pose = arm_pose
        self.age = age
        self.cape_deg = cape_deg
        self.label = label


def player_parts(pose, slim=False, armor=True, skin_layers=True):
    """Return {part: (model_matrix_world, [Box in vanilla model space])} and the body matrix.

    Boxes are given in vanilla model space; the returned matrices map them to world.
    """
    p = pose
    head_piv = np.array([0.0, 0.0, 0.0])
    body_piv = np.array([0.0, 0.0, 0.0])
    arm_y = 2.5 if slim else 2.0
    rarm_piv = np.array([-5.0, arm_y, 0.0])
    larm_piv = np.array([5.0, arm_y, 0.0])
    rleg_piv = np.array([-1.9, 12.0, 0.0])
    lleg_piv = np.array([1.9, 12.0, 0.0])

    a = {k: [0.0, 0.0, 0.0] for k in ("head", "body", "rarm", "larm", "rleg", "lleg")}
    a["head"][0] = p.head_pitch
    a["head"][1] = p.head_yaw

    la, ld = p.limb_angle, p.limb_distance
    a["rarm"][0] = math.cos(la * 0.6662 + math.pi) * 2.0 * ld * 0.5
    a["larm"][0] = math.cos(la * 0.6662) * 2.0 * ld * 0.5
    a["rleg"][0] = math.cos(la * 0.6662) * 1.4 * ld
    a["lleg"][0] = math.cos(la * 0.6662 + math.pi) * 1.4 * ld

    # Right-hand item poses (BipedEntityModel.positionRightArm / positionLeftArm).
    hp, hy = p.head_pitch, p.head_yaw
    pose_name = p.arm_pose
    if pose_name == "bow":
        a["rarm"][1] = -0.1 + hy
        a["larm"][1] = 0.1 + hy + 0.4
        a["rarm"][0] = -math.pi / 2 + hp
        a["larm"][0] = -math.pi / 2 + hp
    elif pose_name == "crossbow_hold":
        a["rarm"][1] = -0.3 + hy
        a["larm"][1] = 0.6 + hy
        a["rarm"][0] = -math.pi / 2 + hp + 0.1
        a["larm"][0] = -1.5 + hp
    elif pose_name == "block":
        a["rarm"][0] = a["rarm"][0] * 0.5 - 0.9424779
        a["rarm"][1] = -math.pi / 6
    elif pose_name == "item":
        a["rarm"][0] = a["rarm"][0] * 0.5 - math.pi / 10
    elif pose_name == "spyglass":
        a["rarm"][0] = min(max(hp - 1.9198622 - (0.2617994 if p.sneak else 0.0), -2.4), 3.3)
        a["rarm"][1] = hy - 0.2617994
    elif pose_name == "horn":
        a["rarm"][0] = min(max(hp, -1.2), 1.2) - 1.4835298
        a["rarm"][1] = hy - math.pi / 6
    elif pose_name == "trident":
        a["rarm"][0] = a["rarm"][0] * 0.5 - math.pi
        a["rarm"][1] = 0.0

    # Attack swing (BipedEntityModel.animateArms), right hand.
    if p.swing > 0:
        f = p.swing
        by = math.sin(math.sqrt(f) * math.pi * 2) * 0.2
        a["body"][1] = by
        rarm_piv[2] = math.sin(by) * 5.0
        rarm_piv[0] = -math.cos(by) * 5.0
        larm_piv[2] = -math.sin(by) * 5.0
        larm_piv[0] = math.cos(by) * 5.0
        a["rarm"][1] += by
        a["larm"][1] += by
        a["larm"][0] += by
        g = (1.0 - f) ** 4
        h = math.sin((1.0 - g) * math.pi)
        i = math.sin(f * math.pi) * -(hp - 0.7) * 0.75
        a["rarm"][0] -= h * 1.2 + i
        a["rarm"][1] += by * 2.0
        a["rarm"][2] += math.sin(f * math.pi) * -0.4

    if p.sneak:
        a["body"][0] = 0.5
        a["rarm"][0] += 0.4
        a["larm"][0] += 0.4
        rleg_piv[2] = lleg_piv[2] = 4.0
        rleg_piv[1] = lleg_piv[1] = 12.2
        head_piv[1] = 4.2
        body_piv[1] = 3.2
        rarm_piv[1] = larm_piv[1] = 5.2

    # Idle sway (CrossbowPosing.swingArm), skipped for spyglass like vanilla.
    if pose_name != "spyglass":
        a["rarm"][2] += math.cos(p.age * 0.09) * 0.05 + 0.05
        a["rarm"][0] += math.sin(p.age * 0.067) * 0.05
    a["larm"][2] -= math.cos(p.age * 0.09) * 0.05 + 0.05
    a["larm"][0] -= math.sin(p.age * 0.067) * 0.05

    # Vanilla ModelPart applies pivot then ZYX rotation; pivots here are absolute.
    def mm(piv, ang):
        return translate(piv) @ affine(rot_zyx(*ang))

    head_m = mm(head_piv, a["head"])
    body_m = mm(body_piv, a["body"])
    rarm_m = mm(rarm_piv, a["rarm"])
    larm_m = mm(larm_piv, a["larm"])
    rleg_m = mm(rleg_piv, a["rleg"])
    lleg_m = mm(lleg_piv, a["lleg"])

    arm_w = 3 if slim else 4
    r_lo = -2 if slim else -3
    head_boxes = [Box((-4, -8, -4), (8, 8, 8), "skin", name="head")]
    body_boxes = [Box((-4, 0, -2), (8, 12, 4), "skin", name="body")]
    rarm_boxes = [Box((r_lo, -2, -2), (arm_w, 12, 4), "skin", name="right_arm")]
    larm_boxes = [Box((-1, -2, -2), (arm_w, 12, 4), "skin", name="left_arm")]
    rleg_boxes = [Box((-2, 0, -2), (4, 12, 4), "skin", name="right_leg")]
    lleg_boxes = [Box((-2, 0, -2), (4, 12, 4), "skin", name="left_leg")]
    if skin_layers:
        head_boxes.append(Box((-4, -8, -4), (8, 8, 8), "skin", 0.5, "hat_layer"))
        body_boxes.append(Box((-4, 0, -2), (8, 12, 4), "skin", 0.25, "jacket_layer"))
        rarm_boxes.append(Box((r_lo, -2, -2), (arm_w, 12, 4), "skin", 0.25, "right_sleeve"))
        larm_boxes.append(Box((-1, -2, -2), (arm_w, 12, 4), "skin", 0.25, "left_sleeve"))
        rleg_boxes.append(Box((-2, 0, -2), (4, 12, 4), "skin", 0.25, "right_pants"))
        lleg_boxes.append(Box((-2, 0, -2), (4, 12, 4), "skin", 0.25, "left_pants"))
    if armor:
        # Vanilla armor cuboids: helmet/chestplate/boots dilate 1.0, leggings 0.5. Boots are the
        # full leg cuboid in vanilla but only the lower ~5 px is textured, so only that part counts.
        head_boxes.append(Box((-4, -8, -4), (8, 8, 8), "armor", 1.0, "helmet"))
        body_boxes.append(Box((-4, 0, -2), (8, 12, 4), "armor", 1.0, "chestplate"))
        rarm_boxes.append(Box((-3, -2, -2), (4, 12, 4), "armor", 1.0, "right_pauldron"))
        larm_boxes.append(Box((-1, -2, -2), (4, 12, 4), "armor", 1.0, "left_pauldron"))
        body_boxes.append(Box((-4, 0, -2), (8, 12, 4), "armor", 0.5, "leggings_belt"))
        rleg_boxes.append(Box((-2, 0, -2), (4, 12, 4), "armor", 0.5, "right_legging"))
        lleg_boxes.append(Box((-2, 0, -2), (4, 12, 4), "armor", 0.5, "left_legging"))
        rleg_boxes.append(Box((-2, 7, -2), (4, 5, 4), "armor", 1.0, "right_boot"))
        lleg_boxes.append(Box((-2, 7, -2), (4, 5, 4), "armor", 1.0, "left_boot"))

    parts = {
        "head": (to_world(head_m), head_boxes),
        "body": (to_world(body_m), body_boxes),
        "right_arm": (to_world(rarm_m), rarm_boxes),
        "left_arm": (to_world(larm_m), larm_boxes),
        "right_leg": (to_world(rleg_m), rleg_boxes),
        "left_leg": (to_world(lleg_m), lleg_boxes),
    }
    return parts, to_world_frame(body_m)


def cape_obb(pose, armor=True):
    """Vanilla cape slab (CapeFeatureRenderer): 10x16x1, hinged 2 px behind the neck line."""
    from geom import rx, ry
    m = translate((0, 0, 2.0))
    if armor:
        m = m @ translate((0, -0.85, 1.1))
    if pose.sneak:
        m = m @ translate((0, 1.85, 1.4))
    m = m @ affine(rx(math.radians(pose.cape_deg))) @ affine(ry(math.pi))
    return OBB(Box((-5, 0, -1), (10, 16, 1), "cape", name="cape"), to_world(m), "cape", "cape")


def player_obbs(pose, slim=False, armor=True, skin_layers=True, cape=False):
    parts, body_w = player_parts(pose, slim, armor, skin_layers)
    out = []
    for part, (m, boxes) in parts.items():
        for b in boxes:
            out.append(OBB(b, m, part, b.tag))
    if cape:
        out.append(cape_obb(pose, armor))
    return out, body_w


# Rest body matrix in world space (identity when standing).
REST_BODY_W = to_world_frame(np.eye(4))


def body_attach(body_w):
    """Matrix that carries a cosmetic authored in the rest world frame along with the body."""
    return body_w @ np.linalg.inv(REST_BODY_W)


def envelope(head_pitch_range=(-90, 90), head_yaw_range=(-75, 75), include_rare=False, step=15):
    """Sample the vanilla pose envelope. Each item is a PlayerPose with a label/category."""
    poses = []
    hps = list(range(head_pitch_range[0], head_pitch_range[1] + 1, step))
    hys = list(range(head_yaw_range[0], head_yaw_range[1] + 1, step))
    for sneak in (False, True):
        for hp in hps:
            for hy in hys:
                poses.append(PlayerPose(hp, hy, sneak=sneak, label=f"look {hp}/{hy}{' sneak' if sneak else ''}"))
        ld_max = 0.35 if sneak else 1.0
        for i in range(32):
            la = i / 32 * 2 * math.pi / 0.6662
            for age in (0.0, 17.5, 35.0):
                poses.append(PlayerPose(0, 0, la, ld_max, sneak=sneak, age=age,
                                        label=f"{'sneak-walk' if sneak else 'sprint'} phase {i}/32"))
        for f in np.linspace(0.05, 0.95, 10):
            for hp in (-60, 0, 60):
                poses.append(PlayerPose(hp, 0, sneak=sneak, swing=float(f), label=f"attack swing {f:.2f} look {hp}"))
        for arm in ("bow", "crossbow_hold", "block", "item", "spyglass", "horn"):
            for hp in (-90, -45, 0, 45, 90):
                for hy in (-50, 0, 50):
                    poses.append(PlayerPose(hp, hy, 0.0, 0.3, sneak=sneak, arm_pose=arm, label=f"{arm} look {hp}/{hy}"))
        if include_rare:
            for i in range(8):
                la = i / 8 * 2 * math.pi / 0.6662
                poses.append(PlayerPose(-30, 0, la, 1.0, sneak=sneak, arm_pose="trident", label=f"trident overhead {i}/8"))
    for p in poses:
        p.category = "rare" if p.arm_pose == "trident" else ("look" if p.label.startswith("look") else "motion")
    return poses


def cape_angles(sneak):
    # 6 deg rest; forward speed adds up to 75, vertical speed -6..32, sneak +25 (vanilla clamps).
    lo, hi = (6.0 + 25.0, 6.0 + 25.0 + 20.0 + 32.0) if sneak else (0.0, 6.0 + 75.0 + 32.0)
    return np.linspace(lo, hi, 12)


def vanilla_self_clip_depth(pose, slim=False):
    """How far (px) the bare vanilla head already sinks into the bare body in this pose.
    Looking up 30 deg is already ~1 px; sneaking and looking straight up is several px.
    A rig contact with the head no deeper than this is no worse than vanilla's own model."""
    from geom import obb_gap
    parts, _ = player_parts(pose, slim=slim, armor=False, skin_layers=False)
    hm, hb = parts["head"]
    bm, bb = parts["body"]
    return max(0.0, -obb_gap(OBB(hb[0], hm), OBB(bb[0], bm)))
