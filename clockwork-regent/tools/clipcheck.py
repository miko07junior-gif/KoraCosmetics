"""Clipping check: every rig box against every player box over the vanilla pose envelope,
for each wing state. Prints a table and writes JSON next to the renders.

  python3 clipcheck.py            # common poses: look, walk/sprint, sneak, attack, items
  python3 clipcheck.py --rare     # adds the overhead trident throw
  python3 clipcheck.py --cape     # adds a vanilla cape (only if Kora lets wings and capes coexist)

A result is a clearance in model pixels (1/16 block, before vanilla's 15/16 player
scale). Negative = penetration. The SAT gap is a lower bound on true separation, so
reported clearances are conservative.
"""
import argparse
import json
import os
import sys

import numpy as np

import player
import rig
from geom import obb_arrays, obb_gap_matrix

STATES = {
    "folded": dict(t=0.0),
    "unfold_25": dict(t=0.25),
    "unfold_50": dict(t=0.5),
    "unfold_75": dict(t=0.75),
    "spread": dict(t=1.0),
    # Staggered unfold: leading edge first, then each tier in turn.
    "stagger_coverts": dict(t=0.6, tier_t=dict(coverts=0.6, secondaries=0.0, primaries=0.0)),
    "stagger_secondaries": dict(t=0.9, tier_t=dict(coverts=1.0, secondaries=0.6, primaries=0.0)),
    "stagger_primaries": dict(t=1.0, tier_t=dict(coverts=1.0, secondaries=1.0, primaries=0.5)),
    "spread_lowered_alt": dict(t=1.0, layout="lowered"),
}


def check(bones, poses, armor=True, slim=False, cape=False, states=STATES):
    results = {}
    for sname, sargs in states.items():
        rpose = rig.pose_spread(**sargs)
        worst = {}
        for pp in poses:
            cape_list = player.cape_angles(pp.sneak) if cape else [None]
            for cdeg in cape_list:
                if cdeg is not None:
                    pp.cape_deg = float(cdeg)
                pobbs, body_w = player.player_obbs(pp, slim=slim, armor=armor, cape=cdeg is not None)
                robbs = rig.world_boxes(bones, rpose, player.body_attach(body_w))
                gaps = obb_gap_matrix(obb_arrays(robbs), obb_arrays(pobbs))
                allow = player.vanilla_self_clip_depth(pp, slim)
                for j, po in enumerate(pobbs):
                    i = int(np.argmin(gaps[:, j]))
                    g = float(gaps[i, j])
                    if po.owner == "head" and g < 0 and -g <= allow:
                        g = 0.0  # no deeper than vanilla's own head-into-body overlap here
                    key = (po.owner, po.name)
                    if key not in worst or g < worst[key][0]:
                        worst[key] = (g, robbs[i].owner + ":" + robbs[i].name,
                                      pp.label + (f" cape {cdeg:.0f}" if cdeg is not None else ""))
        results[sname] = worst
    return results


def summarise(results, limit=0.0):
    rows = []
    for sname, worst in results.items():
        bad = sorted([(g, k, rb, lab) for k, (g, rb, lab) in worst.items() if g < limit])
        closest = min(worst.values(), key=lambda v: v[0]) if worst else (float("inf"), "", "")
        rows.append(dict(state=sname, clips=len(bad), min_clearance=round(closest[0], 2),
                         worst=[dict(player=f"{k[0]}:{k[1]}", rig=rb, pose=lab, depth=round(-g, 2)) for g, k, rb, lab in bad[:8]],
                         nearest=dict(rig=closest[1], pose=closest[2])))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rare", action="store_true")
    ap.add_argument("--cape", action="store_true")
    ap.add_argument("--slim", action="store_true")
    ap.add_argument("--no-armor", action="store_true")
    ap.add_argument("--step", type=int, default=15)
    ap.add_argument("--out", default="")
    ap.add_argument("--quick", action="store_true", help="folded + spread only, motion poses and level look")
    a = ap.parse_args(argv)
    bones = rig.build()
    poses = player.envelope(include_rare=a.rare, step=a.step)
    states = STATES
    if a.quick:
        poses = [p for p in poses if p.category != "look" or abs(p.head_pitch) < 1e-6]
        states = {k: STATES[k] for k in ("folded", "spread")}
    res = check(bones, poses, armor=not a.no_armor, slim=a.slim, cape=a.cape, states=states)
    rows = summarise(res)
    for r in rows:
        print(f"{r['state']:<22} clips={r['clips']:<3} min_clearance={r['min_clearance']:>6}  nearest={r['nearest']['rig']} @ {r['nearest']['pose']}")
        for w in r["worst"]:
            print(f"    {w['depth']:>5} px  {w['rig']:<34} x {w['player']:<26} {w['pose']}")
    pist = rig.piston_report()
    print("pistons:", pist)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(dict(args=vars(a), poses=len(poses), states=rows, pistons=pist), f, indent=1)
    return rows


if __name__ == "__main__":
    sys.exit(0 if all(r["clips"] == 0 for r in main()) else 1)
