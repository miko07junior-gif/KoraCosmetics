"""Write the gray-box rig and its key poses as format-neutral JSON.

  python3 export_graybox.py [out.json]

This is the hand-off point to Kora's own format. It's deliberately not a Bedrock,
GeckoLib or Blockbench file: Kora's loader decides axes, rotation order and units,
and none of that has been read yet. Conventions are spelled out in the file.
"""
import json
import os
import sys

import rig

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "design", "regent_graybox.json")

KEY_POSES = {
    "folded": dict(t=0.0),
    "arch_split": dict(t=0.35, tier_t=dict(coverts=0.0, secondaries=0.0, primaries=0.0)),
    "coverts_open": dict(t=0.7, tier_t=dict(coverts=1.0, secondaries=0.0, primaries=0.0)),
    "secondaries_open": dict(t=0.9, tier_t=dict(coverts=1.0, secondaries=1.0, primaries=0.0)),
    "spread": dict(t=1.0),
}


def r(v, n=4):
    return [round(float(x), n) for x in v]


def main():
    bones = rig.build()
    out = dict(
        name="clockwork_regent_graybox",
        conventions=dict(
            units="model pixels (1/16 block) before vanilla's 15/16 player scale",
            axes="+x wearer's right, +y up, +z behind the wearer; origin between the feet; wearer faces -z",
            rotation="degrees, applied as R = Rz @ Ry @ Rx about the bone pivot (Minecraft ModelPart order)",
            attach="every bone follows the player's body part (pivot at the neck, 0,24,0)",
            rest_pose="folded; poses are local deltas added to rest, translations in the bone's parent frame",
        ),
        params=rig.P,
        spread_layouts=rig.SPREADS,
        bones=[dict(name=b.name, parent=b.parent, pivot=r(b.pivot), rest_rotation=r(b.rest),
                    cubes=[dict(name=c.name, material=c.tag, origin=r(c.lo), size=r(c.size)) for c in b.boxes])
               for b in bones.values()],
        poses={k: {bone: r(v) for bone, v in rig.pose_spread(**a).items()} for k, a in KEY_POSES.items()},
        pistons=rig.piston_report(),
        counts=dict(bones=len(bones), cubes=sum(len(b.boxes) for b in bones.values())),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(OUT, out["counts"])


if __name__ == "__main__":
    main()
