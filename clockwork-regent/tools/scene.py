"""Scene assembly shared by the render scripts: player + rig in one list of boxes."""
import numpy as np

import player
import rig

# Value ids. Silhouette, notan and value-key renders map these to different greys.
SKIN, ARMOR, CAPE, BRONZE, BRASS, IVORY, AMBER = range(7)
TAG_ID = {"skin": SKIN, "armor": ARMOR, "cape": CAPE, "bronze": BRONZE, "brass": BRASS, "ivory": IVORY, "amber": AMBER}
COSMETIC_IDS = (BRONZE, BRASS, IVORY, AMBER)

# Grey-box preview colours: placeholders only, not the painted ramps.
PREVIEW = {SKIN: (150, 150, 150), ARMOR: (120, 124, 140), CAPE: (90, 60, 60), BRONZE: (58, 52, 48),
           BRASS: (190, 160, 90), IVORY: (236, 228, 205), AMBER: (255, 170, 40)}


def items(rig_pose=None, player_pose=None, bones=None, armor=False, slim=False, cape=False,
          show_player=True, show_rig=True):
    bones = bones or rig.build()
    player_pose = player_pose or player.PlayerPose()
    out = []
    obbs, body_w = player.player_obbs(player_pose, slim=slim, armor=armor, cape=cape)
    if show_player:
        for o in obbs:
            # Thin skin overlay layers only matter for clipping, not for silhouettes.
            out.append((o.corners(), TAG_ID[o.tag]))
    if show_rig:
        for o in rig.world_boxes(bones, rig_pose or {}, player.body_attach(body_w)):
            out.append((o.corners(), TAG_ID[o.tag]))
    return out


def scale_items(its, s, origin=(0, 0, 0)):
    o = np.asarray(origin, float)
    return [((np.asarray(c) - o) * s + o, v) for c, v in its]
