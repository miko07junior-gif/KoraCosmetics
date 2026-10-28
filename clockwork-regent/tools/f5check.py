"""F5 (third-person back) occlusion: how much of the wearer's own screen the cosmetic
covers beyond what their own player model already covers.

  python3 f5check.py [out_dir]

Vanilla's third-person camera sits 4 blocks behind the eye along the look vector
(less if a wall is in the way; ignored here). The rig follows the body; the body
doesn't pitch with the look, the camera orbits it.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

import player
import regent
import render
import scene
from make_step1 import BLOCK, grid, label

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "renders", "checks")

STATES = {"folded": regent.pose_state(t=0.0), "spread": regent.pose_state(t=1.0)}
SCREENS = [((1920, 1080), 70), ((1920, 1080), 90), ((1920, 1080), 110)]
PITCHES = (-30, 0, 30)   # + looks down


def f5(state, res, fov, pitch_deg):
    pp = player.PlayerPose(head_pitch_deg=pitch_deg)
    pl = scene.scale_items(scene.items(None, pp, show_rig=False), BLOCK)
    co = scene.scale_items(scene.items(STATES[state], pp, show_player=False), BLOCK)
    pitch = math.radians(pitch_deg)
    look = np.array([0.0, -math.sin(pitch), -math.cos(pitch)])   # wearer faces -z
    eye = np.array([0, player.EYE_HEIGHT_BLOCKS, 0])
    cam_pos = eye - look * player.F5_DISTANCE_BLOCKS
    cam = render.Camera(cam_pos, eye, (0, 1, 0), res[0], res[1], vfov=fov)
    ids_p, _ = render.rasterise(cam, pl)
    ids_c, _ = render.rasterise(cam, co)
    extra = (ids_c >= 0) & (ids_p < 0)
    h, w = extra.shape
    centre = extra[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
    # Crosshair neighbourhood: 5% of screen height around the centre.
    r = int(0.05 * h)
    cross = extra[h // 2 - r: h // 2 + r, w // 2 - r: w // 2 + r]
    vis = np.full((h, w, 3), (205, 214, 222), np.uint8)
    vis[ids_p >= 0] = (110, 110, 110)
    vis[extra] = (40, 40, 40)
    vis[h // 2 - 1: h // 2 + 2, w // 2 - 8: w // 2 + 9] = (255, 255, 255)
    vis[h // 2 - 8: h // 2 + 9, w // 2 - 1: w // 2 + 2] = (255, 255, 255)
    return vis, dict(state=state, res=res, fov=fov, pitch=pitch_deg,
                     screen=round(float(extra.mean()), 4), centre_third=round(float(centre.mean()), 4),
                     crosshair=round(float(cross.mean()), 4))


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, panels = [], []
    for res, fov in SCREENS:
        for state in STATES:
            for pitch in PITCHES:
                vis, m = f5(state, res, fov, pitch)
                rows.append(m)
                if res == (1920, 1080) and fov == 70:
                    small = Image.fromarray(vis).resize((480, 270), Image.BOX)
                    panels.append(label(small, f"{state} look {pitch:+d}: extra {m['screen']:.1%} screen, "
                                               f"{m['centre_third']:.1%} centre, {m['crosshair']:.1%} at crosshair"))
    grid(panels, 3, title="F5 at 1080p FOV 70: dark = cosmetic covering view the player model doesn't already cover"
         ).save(os.path.join(OUT, "f5_occlusion.png"))
    with open(os.path.join(OUT, "f5_occlusion.json"), "w") as f:
        json.dump(rows, f, indent=1)
    for m in rows:
        print(m)


if __name__ == "__main__":
    main()
