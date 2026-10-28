"""Write the hand-off files for Kora's pipeline:

  design/regent_rigged.glb     joints + meshes + clips (idle_folded, wake, idle_spread, sleep)
  design/regent_spec.json      format-neutral joint list: pivots, hinge axes, kinds, key poses
  design/timing_wake.csv       the wake schedule per game tick (from the escapement model)

python3 export_model.py
"""
import csv
import json
import os

import export_glb
import motion
import regent

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.join(HERE, "..", "design")


def r(v, n=4):
    return [round(float(x), n) for x in v]


def _jsonable(o):
    if isinstance(o, dict):
        return {(":".join(map(str, k)) if isinstance(k, tuple) else k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def spec(J):
    return dict(
        name="clockwork_regent",
        conventions=dict(
            units="model pixels (1/16 block), before vanilla's 15/16 player scale",
            axes="+x wearer's right, +y up, +z behind the wearer; origin between the feet; the wearer faces -z",
            attach="every joint follows the player's body part (pivot at the neck, 0,24,0)",
            rest_pose="folded, baked into the geometry; hinge poses are angles (deg) about each joint's axis at its pivot",
            kinds="hinge: rotation; slide: translation along axis (px); seam: light strip scaled along axis 0..1; "
                  "glow: lit jewel scaled uniformly 0..1",
        ),
        params=_jsonable(regent.P),
        escapement=motion.ESC,
        joints=[dict(name=n, parent=j.parent, kind=j.kind, pivot=r(j.pivot), axis=r(j.axis),
                     primitives=len(j.prims), triangles=int(sum(len(p.tris) for p in j.prims)),
                     materials=sorted({p.material for p in j.prims})) for n, j in J.items()],
        key_poses={k: {n: round(float(v), 3) for n, v in regent.solve_pistons(J, regent.pose_state(**a)).items()}
                   for k, a in regent.KEY_POSES.items()},
        counts=dict(joints=len(J), triangles=int(sum(len(p.tris) for j in J.values() for p in j.prims)),
                    hinges=sum(j.kind == "hinge" for j in J.values()), slides=sum(j.kind == "slide" for j in J.values()),
                    lights=sum(j.kind in ("seam", "glow") for j in J.values())),
    )


def write_all(J=None):
    J = J or regent.build()
    os.makedirs(DESIGN, exist_ok=True)
    glb = export_glb.rigged_glb(J, motion.build_clips(J))
    with open(os.path.join(DESIGN, "regent_rigged.glb"), "wb") as f:
        f.write(glb)
    with open(os.path.join(DESIGN, "regent_spec.json"), "w") as f:
        json.dump(spec(J), f, indent=1)
    rows = motion.timing_chart()
    with open(os.path.join(DESIGN, "timing_wake.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return glb


if __name__ == "__main__":
    g = write_all()
    print("glb", round(len(g) / 1e6, 2), "MB")
