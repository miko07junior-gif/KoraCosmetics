"""Shaded renders of the high-resolution model through three.js in headless Chromium.

  python3 render_views.py sheet OUT.png [--size 900]     ortho views, folded/spread
  python3 render_views.py unfold OUT.png                 the unfold, key poses

Needs Node, Playwright (preinstalled here) and three.js; set THREE_DIR to a three
package folder (npm install three@0.160.0).
"""
import argparse
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import export_glb
import player
import regent

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)


def render(jobs):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    env = dict(os.environ)
    env.setdefault("THREE_DIR", os.path.join(os.environ.get("SCRATCH", ""), "viewer/node_modules/three"))
    subprocess.run(["node", os.path.join(HERE, "render3d", "render.mjs"), f.name], check=True, env=env,
                   stdout=subprocess.DEVNULL)


def posed_glb(path, pose, player_pose=None, mannequin=True, seams=None, glow=None, armor=False):
    J = regent.build()
    extra = None
    attach = None
    if player_pose is not None:
        _, body_w = player.player_parts(player_pose)
        attach = player.body_attach(body_w)
    if mannequin:
        extra = export_glb.mannequin_tris(player_pose or player.PlayerPose(), armor=armor)
    with open(path, "wb") as f:
        f.write(export_glb.static_glb(J, pose, attach, seams, extra, glow))


def label(img, text):
    h = 28
    out = Image.new("RGB", (img.width, img.height + h), (232, 232, 228))
    out.paste(img, (0, h))
    ImageDraw.Draw(out).text((8, 5), text, font=FONT, fill=(20, 20, 20))
    return out


def grid(panels, cols, title, gap=8):
    w, h = panels[0].size
    rows = (len(panels) + cols - 1) // cols
    th = 34
    out = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap + th), (232, 232, 228))
    ImageDraw.Draw(out).text((gap, 8), title, font=FONT_B, fill=(10, 10, 10))
    for i, p in enumerate(panels):
        out.paste(p, (gap + (i % cols) * (w + gap), th + gap + (i // cols) * (h + gap)))
    return out


def sheet(out, states, views, size=700, title="", extent=3.5, centre=(0, 1.45, 0.3), night=False, bloom=True):
    tmp = tempfile.mkdtemp()
    jobs, labels = [], []
    for sname, pose, ppose, seams, glow in states:
        g = os.path.join(tmp, f"{sname}.glb")
        posed_glb(g, pose, ppose, seams=seams, glow=glow)
        for v in views:
            o = os.path.join(tmp, f"{sname}_{v}.png")
            jobs.append(dict(glb=g, view=v, out=o, size=size, extent=extent, centre=list(centre), night=night, bloom=bloom))
            labels.append(f"{sname}: {v.replace('three_quarter', '3/4').replace('_', ' ')}")
    render(jobs)
    panels = [label(Image.open(j["out"]).convert("RGB"), t) for j, t in zip(jobs, labels)]
    grid(panels, len(views), title).save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["sheet", "unfold", "night"])
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=700)
    a = ap.parse_args()
    dim = {"amber": 0.25, "seam_lit": 0.0, "seam": 0.12}
    lit = {"amber": 2.5, "seam_lit": 3.0, "seam": 0.4}
    dark_seams = {n: 0.0 for n in regent.build() if n.startswith("seam_")}
    if a.what == "sheet":
        states = [("folded", regent.pose_state(t=0.0), None, dark_seams, dim),
                  ("spread", regent.pose_state(t=1.0), None, None, lit)]
        sheet(a.out, states, ["front", "back", "side", "three_quarter_back"], a.size,
              "Clockwork Regent (gray-box materials): folded = dormant niche, spread = awake sunburst. Neutral grey, even light.")
    elif a.what == "unfold":
        keys = [("folded", dict(t=0.0)),
                ("arch splits", dict(t=0.0, arch_t=0.45, lift_t=0.3)),
                ("coverts rise", dict(t=0.0, arch_t=0.8, lift_t=0.7, tier_t=dict(coverts=0.8))),
                ("secondaries rise", dict(t=0.0, arch_t=1.0, lift_t=1.0, tier_t=dict(coverts=1.0, secondaries=0.8, primaries=0.25), ext_t=0.0)),
                ("primaries fan", dict(t=0.0, arch_t=1.0, lift_t=1.0, tier_t=dict(coverts=1.0, secondaries=1.0, primaries=1.0), ext_t=0.3)),
                ("spread", dict(t=1.0))]
        states = []
        for i, (n, kw) in enumerate(keys):
            f = i / (len(keys) - 1)
            glow = {"amber": 0.25 + 2.2 * f, "seam_lit": 3.0, "seam": 0.12 + 0.3 * f}
            states.append((n, regent.pose_state(**kw), None, None, glow))
        sheet(a.out, states, ["back", "three_quarter_back"], a.size, "The unfold, key poses (back and 3/4 back)")
    else:
        states = [("folded at night", regent.pose_state(t=0.0), None, dark_seams, dim),
                  ("spread at night", regent.pose_state(t=1.0), None, None, lit)]
        sheet(a.out, states, ["back", "three_quarter_back"], a.size, "Night: emissive budget check", night=True)


if __name__ == "__main__":
    main()
