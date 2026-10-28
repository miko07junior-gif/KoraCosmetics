"""Step 1 of the brief: notan and silhouette thumbnails at store-icon size and 30-block size.

  python3 make_step1.py [out_dir]

Writes contact sheets plus step1_measurements.json. Assumptions that Kora's own
files or player data must replace are listed in that JSON under "assumptions".
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import player
import render
import rig
import scene

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "renders", "step1")

# Placeholders until Kora's menu-preview size and player settings are known.
ICON_SIZES = (64, 96, 128)
SCREENS = [((1366, 768), 70), ((1920, 1080), 70), ((1920, 1080), 90), ((1920, 1080), 110), ((2560, 1440), 90)]

STATES = {"folded": {}, "spread": rig.pose_spread(), "spread_lowered": rig.pose_spread(layout="lowered")}
MAIN_STATES = ("folded", "spread")
BLOCK = player.PLAYER_RENDER_SCALE / 16.0   # model px -> blocks

FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)

WHITE, BLACK = (255, 255, 255), (0, 0, 0)
SIL = {k: BLACK for k in range(7)}
NOTAN = {scene.SKIN: (168, 168, 168), scene.ARMOR: (168, 168, 168), scene.CAPE: (168, 168, 168),
         scene.BRONZE: BLACK, scene.BRASS: WHITE, scene.IVORY: WHITE, scene.AMBER: WHITE}
# Value key: blackened bronze dark, aged brass mid, ivory enamel and amber light.
VALUE = {scene.SKIN: (92, 92, 92), scene.ARMOR: (92, 92, 92), scene.CAPE: (92, 92, 92),
         scene.BRONZE: (38, 38, 38), scene.BRASS: (140, 140, 140), scene.IVORY: (232, 232, 232), scene.AMBER: (205, 205, 205)}
DARK_GREY = (64, 64, 64)


def label(img, text, font=FONT, pad=4, fg=(20, 20, 20), bg=(236, 236, 232)):
    w = img.width
    h = font.getbbox("Ag")[3] + 2 * pad
    out = Image.new("RGB", (w, img.height + h), bg)
    out.paste(img, (0, h))
    ImageDraw.Draw(out).text((pad, pad), text, font=font, fill=fg)
    return out


def grid(panels, cols, gap=6, bg=(236, 236, 232), title=None):
    rows = [panels[i:i + cols] for i in range(0, len(panels), cols)]
    cw = max(p.width for p in panels)
    rh = [max(p.height for p in r) for r in rows]
    th = (FONT_B.getbbox("Ag")[3] + 14) if title else 0
    out = Image.new("RGB", (cols * cw + (cols + 1) * gap, sum(rh) + (len(rows) + 1) * gap + th), bg)
    if title:
        ImageDraw.Draw(out).text((gap, gap), title, font=FONT_B, fill=(10, 10, 10))
    y = gap + th
    for r, h in zip(rows, rh):
        x = gap
        for p in r:
            out.paste(p, (x, y))
            x += cw + gap
        y += h + gap
    return out


def up(arr, k):
    return Image.fromarray(arr).resize((arr.shape[1] * k, arr.shape[0] * k), Image.NEAREST)


def fit_ortho(view, its, size, pad=0.08):
    """Orthographic camera framing `its` in a size x size icon, like a store tile."""
    cam0 = render.ortho_view(view, (0, 0, 0), 1.0, 1)
    pts = np.concatenate([c for c, _ in its])
    pr = cam0.project(pts)
    lo, hi = pr[:, :2].min(0), pr[:, :2].max(0)
    extent = max(hi - lo) * (1 + 2 * pad)
    # Recentre on the projected bounding box.
    mid2 = (lo + hi) / 2 - np.array([0.5, 0.5])
    centre = mid2[0] * cam0.r - mid2[1] * cam0.u
    return render.ortho_view(view, centre, extent, size)


def icon(state, view, size, palette, show_player=True, supersample=1):
    its = scene.items(STATES[state], show_player=show_player)
    cam = fit_ortho(view, its, size * supersample)
    ids, _ = render.rasterise(cam, its)
    img = render.colourise(ids, palette, WHITE)
    if supersample > 1:
        img = np.asarray(Image.fromarray(img).resize((size, size), Image.BOX))
    return img


def thirty_block(state, facing, res, fov, palette, distance=30.0, show_rig=True, bg=WHITE):
    """The wearer `distance` blocks away on flat ground; viewer's eye at 1.62 blocks, looking level."""
    its = scene.scale_items(scene.items(STATES[state] if show_rig else {}, show_rig=show_rig), BLOCK)
    yaw = {"front": 0.0, "back": math.pi, "side": math.pi / 2, "three_quarter": math.pi / 4}[facing]
    # Wearer faces -z; place the viewer along the facing direction, rotated by yaw.
    d = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
    eye = d * distance + np.array([0, player.EYE_HEIGHT_BLOCKS, 0])
    cam = render.Camera(eye, eye - d, (0, 1, 0), res[0], res[1], vfov=fov)
    ids, _ = render.rasterise(cam, its)
    ys, xs = np.where(ids >= 0)
    box = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else (0, 0, 0, 0)
    cw = ch = 112
    cx, cy = res[0] // 2, int(round((box[1] + box[3]) / 2)) if len(xs) else res[1] // 2
    crop = ids[cy - ch // 2: cy + ch // 2, cx - cw // 2: cx + cw // 2]
    return render.colourise(crop, palette, bg), dict(w_px=int(box[2] - box[0] + 1), h_px=int(box[3] - box[1] + 1))


def area_fractions(state, view, size=512):
    """Share of the visible cosmetic in each value group, with the wearer in place (what viewers see)."""
    its = scene.items(STATES[state])
    cam = fit_ortho(view, its, size)
    ids, _ = render.rasterise(cam, its)
    counts = {k: int((ids == k).sum()) for k in scene.COSMETIC_IDS}
    tot = sum(counts.values()) or 1
    return dict(bronze=round(counts[scene.BRONZE] / tot, 3), brass=round(counts[scene.BRASS] / tot, 3),
                ivory_amber=round((counts[scene.IVORY] + counts[scene.AMBER]) / tot, 3))


def main():
    os.makedirs(OUT, exist_ok=True)
    meas = dict(assumptions=dict(
        icon_sizes=f"{ICON_SIZES} are placeholders until Kora's menu preview size is read from its files",
        screens="resolution/FOV pairs are placeholders until Kora's player data is available; Minecraft FOV is vertical",
        player_scale="vanilla renders the player model at 15/16; cosmetics assumed to inherit it",
        distance="30 blocks horizontal, both eyes at 1.62 blocks, looking level, no view bobbing",
    ))

    # 1. Silhouettes at icon sizes: whole figure, and cosmetic alone.
    views = ("three_quarter_back", "back", "front")
    for show_player, tag in ((True, "on_wearer"), (False, "cosmetic_only")):
        panels = []
        for size in ICON_SIZES:
            k = {64: 4, 96: 3, 128: 2}[size]
            for state in MAIN_STATES:
                for v in views:
                    a = icon(state, v, size, SIL, show_player)
                    panels.append(label(up(a, k), f"{size}px {state} {v.replace('_', ' ')}"))
        grid(panels, 6, title=f"Silhouettes at store-icon size ({tag.replace('_', ' ')}), shown at integer zoom, no anti-aliasing"
             ).save(os.path.join(OUT, f"silhouettes_icon_{tag}.png"))

    # Filtered icons (if Kora downsamples pre-rendered icons instead of rasterising at size).
    panels = []
    for size in ICON_SIZES:
        k = {64: 4, 96: 3, 128: 2}[size]
        for state in MAIN_STATES:
            for v in views:
                panels.append(label(up(icon(state, v, size, SIL, True, supersample=8), k), f"{size}px {state} {v.replace('_', ' ')}"))
    grid(panels, 6, title="Silhouettes at store-icon size, box-filtered from 8x (if Kora's icons are anti-aliased)"
         ).save(os.path.join(OUT, "silhouettes_icon_filtered.png"))

    # 2. 30-block silhouettes at real screen-pixel size.
    meas["thirty_blocks"] = []
    panels = []
    for res, fov in SCREENS:
        row = []
        for state, facing in (("none", "front"), ("folded", "front"), ("folded", "back"), ("folded", "side"),
                              ("spread", "back"), ("spread", "three_quarter"), ("spread_lowered", "back")):
            arr, dims = thirty_block("folded" if state == "none" else state, facing, res, fov, SIL, show_rig=state != "none")
            row.append(label(up(arr, 3), f"{res[1]}p fov{fov} {state} {facing}"))
            meas["thirty_blocks"].append(dict(res=res, fov=fov, state=state, facing=facing, **dims))
        panels += row
    grid(panels, 7, title="30 blocks: true screen pixels (3x nearest zoom). 'none' = bare player for scale; 'spread_lowered' = rejected first layout"
         ).save(os.path.join(OUT, "silhouettes_30_blocks.png"))

    # 3. Notan: cosmetic in two values (bronze dark / everything else light); wearer and field mid grey.
    panels = []
    for state in STATES:
        for v in ("front", "back", "three_quarter_back", "side"):
            its = scene.items(STATES[state])
            cam = fit_ortho(v, its, 220)
            ids, _ = render.rasterise(cam, its)
            panels.append(label(Image.fromarray(render.colourise(ids, NOTAN, (112, 112, 112))),
                                f"{state} {v.replace('three_quarter', '3/4').replace('_', ' ')}"))
    grid(panels, 4, title="Notan: blackened bronze = black, brass / ivory / amber = white; wearer light grey, field mid grey"
         ).save(os.path.join(OUT, "notan.png"))

    # 4. Value key: three values on neutral dark grey, with measured shares of visible area.
    panels = []
    meas["value_key"] = {}
    for state in STATES:
        for v in ("front", "back", "three_quarter_back"):
            its = scene.items(STATES[state])
            cam = fit_ortho(v, its, 300)
            ids, _ = render.rasterise(cam, its)
            fr = area_fractions(state, v)
            meas["value_key"][f"{state}_{v}"] = fr
            panels.append(label(Image.fromarray(render.colourise(ids, VALUE, DARK_GREY)),
                                f"{state} {v.replace('three_quarter', '3/4').replace('_', ' ')}: {fr['bronze']:.0%} / {fr['brass']:.0%} / {fr['ivory_amber']:.0%}"))
    grid(panels, 3, title="Value key (bronze / brass / ivory+amber share of visible cosmetic). Target ~60 / 30 / 10"
         ).save(os.path.join(OUT, "value_key.png"))

    # 5. Gray-box views and the unfold, in placeholder colours (not the painted ramps).
    seq = [("folded", {}), ("arch splits", rig.pose_spread(t=0.35, tier_t=dict(coverts=0, secondaries=0, primaries=0))),
           ("coverts open", rig.pose_spread(t=0.7, tier_t=dict(coverts=1, secondaries=0, primaries=0))),
           ("secondaries open", rig.pose_spread(t=0.9, tier_t=dict(coverts=1, secondaries=1, primaries=0))),
           ("spread", rig.pose_spread())]
    panels = []
    for name, pose in seq:
        for v in ("front", "back", "side", "three_quarter_back"):
            cam = render.ortho_view(v, (0, 27, 6), 84, 240)
            ids, _ = render.rasterise(cam, scene.items(pose))
            panels.append(label(Image.fromarray(render.colourise(ids, scene.PREVIEW, (30, 30, 34))),
                                f"{name}: {v.replace('three_quarter', '3/4').replace('_', ' ')}"))
    grid(panels, 4, title="Gray box, placeholder colours: the unfold from dormant niche to sunburst (front = facing viewer)"
         ).save(os.path.join(OUT, "graybox_unfold.png"))

    with open(os.path.join(OUT, "step1_measurements.json"), "w") as f:
        json.dump(meas, f, indent=1)
    print(json.dumps(meas["value_key"], indent=1))
    for r in meas["thirty_blocks"]:
        print(r)


if __name__ == "__main__":
    main()
