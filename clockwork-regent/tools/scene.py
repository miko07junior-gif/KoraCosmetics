"""Scene assembly shared by the silhouette scripts: player boxes + the model's triangles."""
import numpy as np

import player
import regent

# Value ids. Silhouette, notan and value-key renders map these to different greys.
SKIN, ARMOR, CAPE, BRONZE, BRASS, IVORY, AMBER = range(7)
MATERIAL_ID = {"bronze": BRONZE, "bronze_dark": BRONZE, "verdigris": BRONZE, "brass": BRASS, "ivory": IVORY,
               "amber": AMBER, "seam": AMBER, "seam_lit": AMBER}
COSMETIC_IDS = (BRONZE, BRASS, IVORY, AMBER)
_J = None


def model():
    global _J
    if _J is None:
        _J = regent.build()
    return _J


def items(pose=None, player_pose=None, armor=False, slim=False, show_player=True, show_rig=True, seams=None):
    J = model()
    player_pose = player_pose or player.PlayerPose()
    out = []
    obbs, body_w = player.player_obbs(player_pose, slim=slim, armor=armor)
    if show_player:
        for o in obbs:
            if o.name.endswith(("_layer", "sleeve", "pants")):
                continue
            out.append((o.corners(), ARMOR if o.tag == "armor" else SKIN))
    if show_rig:
        pose = regent.solve_pistons(J, pose if pose is not None else regent.pose_state(t=0.0))
        mats = regent.matrices(J, pose, player.body_attach(body_w), seams)
        for name, j in J.items():
            m = mats[name]
            for pr in j.prims:
                t = pr.tris.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
                out.append((t.reshape(-1, 3, 3), MATERIAL_ID[pr.material]))
    return out


def scale_items(its, s, origin=(0, 0, 0)):
    o = np.asarray(origin, float)
    return [((np.asarray(c) - o) * s + o, v) for c, v in its]
