"""Contact report split by what is touched.

  python3 contacts.py           -> ../renders/checks/contacts.json

1. Arms, body and legs: every contact over the motion and item poses (no head
   look-around), worst per (model part, player part), for folded, mid-unfold
   and spread.
2. Head: worst contact per look-up angle (0..90 deg, every head yaw), standing
   and sneaking, raw and beyond vanilla's own head-into-body overlap.
"""
import json
import os

import numpy as np

import player
import regent
from geom import obb_arrays, obb_gap_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "renders", "checks", "contacts.json")
STATES = {"folded": dict(t=0.0), "secondaries_rise": regent.KEY_POSES["secondaries_rise"], "spread": dict(t=1.0)}


def body_contacts(J, step=30, limit=0.05):
    poses = [p for p in player.envelope(step=step, include_rare=True) if p.category != "look"]
    worst = {}
    for sn, sa in STATES.items():
        rp = regent.solve_pistons(J, regent.pose_state(**sa))
        for pp in poses:
            po, bw = player.player_obbs(pp)
            ro = regent.world_obbs(J, rp, player.body_attach(bw))
            G = obb_gap_matrix(obb_arrays(ro), obb_arrays(po))
            for i, j in zip(*np.where(G < limit)):
                if po[j].owner == "head":
                    continue
                k = (ro[i].owner + ":" + ro[i].name, po[j].owner, pp.category == "rare")
                g = float(G[i, j])
                if k not in worst or g < worst[k]["gap"]:
                    worst[k] = dict(model=k[0], player=k[1], gap=round(g, 2), state=sn, pose=pp.label, rare=pp.category == "rare")
    return sorted(worst.values(), key=lambda r: r["gap"])


def head_scan(J):
    rows = []
    for sn, sa in (("folded", dict(t=0.0)), ("spread", dict(t=1.0))):
        rp = regent.solve_pistons(J, regent.pose_state(**sa))
        for sneak in (False, True):
            for up in range(0, 91, 10):
                raw, beyond, who = 1e9, 1e9, ""
                for yaw in range(-75, 76, 15):
                    pp = player.PlayerPose(-up, yaw, sneak=sneak)
                    po, bw = player.player_obbs(pp)
                    heads = [o for o in po if o.owner == "head"]
                    ro = regent.world_obbs(J, rp, player.body_attach(bw))
                    G = obb_gap_matrix(obb_arrays(ro), obb_arrays(heads))
                    g = float(G.min())
                    if g < raw:
                        i, j = np.unravel_index(np.argmin(G), G.shape)
                        raw, who = g, f"{ro[i].owner}:{ro[i].name} x {heads[j].name} (yaw {yaw})"
                    beyond = min(beyond, g + player.vanilla_self_clip_depth(pp))
                rows.append(dict(state=sn, sneak=sneak, look_up=up, worst_gap=round(raw, 2),
                                 beyond_vanilla=round(min(beyond, 0.0), 2), nearest=who))
    return rows


def main():
    J = regent.build()
    out = dict(body=body_contacts(J), head=head_scan(J))
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    for r in out["body"]:
        print(f"{r['gap']:6.2f}  {r['model']:<36} x {r['player']:<10} {r['state']:<17} {r['pose']}")
    for r in out["head"]:
        print(r)


if __name__ == "__main__":
    main()
