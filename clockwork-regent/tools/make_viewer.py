"""Build the interactive viewer page: the rigged GLB (all clips) inlined into
viewer_template.html.  python3 make_viewer.py OUT.html [--local-three PREFIX]"""
import argparse
import base64
import json
import os

import export_model
import motion

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--local-three", default="", help="serve three.js from this URL prefix instead of jsDelivr (offline checks)")
    a = ap.parse_args()
    glb = export_model.write_all()
    page = open(os.path.join(HERE, "viewer_template.html")).read()
    page = page.replace("__GLB_B64__", base64.b64encode(glb).decode()).replace("__ESC__", json.dumps(motion.ESC))
    if a.local_three:
        page = page.replace("https://cdn.jsdelivr.net/npm/three@0.160.0/", a.local_three)
    with open(a.out, "w") as f:
        f.write(page)
    print(a.out, round(len(page) / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
