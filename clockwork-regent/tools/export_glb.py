"""glTF 2.0 (GLB) export for the high-resolution model.

  static_glb(J, pose, ...)   one posed, baked mesh per material (renders)
  rigged_glb(J, clips)       joint hierarchy + animation clips (viewer, hand-off)

glTF uses metres, +Y up, and its own front as +Z. Positions are written in model
pixels / 16 (= blocks). Our world frame is otherwise already right-handed +Y up,
so no axis swap is needed. Joints become nodes with their pivot as origin; hinges
animate rotation, pistons translation, light seams scale along their own +Y.
"""
import json
import math
import struct

import numpy as np

import regent

SCALE = 1.0 / 16.0


def _pad(b, fill=b"\x00"):
    return b + fill * ((4 - len(b) % 4) % 4)


class _Builder:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors = [], []

    def add(self, arr, comp=5126, typ="VEC3", target=None, minmax=False):
        arr = np.ascontiguousarray(arr, dtype=np.float32 if comp == 5126 else np.uint32)
        off = len(self.bin)
        self.bin += _pad(arr.tobytes())
        view = dict(buffer=0, byteOffset=off, byteLength=arr.nbytes)
        if target:
            view["target"] = target
        self.views.append(view)
        acc = dict(bufferView=len(self.views) - 1, componentType=comp, count=int(arr.shape[0]), type=typ)
        if minmax:
            acc["min"] = arr.min(0).tolist() if arr.ndim > 1 else [float(arr.min())]
            acc["max"] = arr.max(0).tolist() if arr.ndim > 1 else [float(arr.max())]
        self.accessors.append(acc)
        return len(self.accessors) - 1


def _materials(names, glow=None):
    glow = glow or {}
    mats = []
    for n in names:
        base, metal, rough, em, strength = regent.MATERIALS[n]
        m = dict(name=n, pbrMetallicRoughness=dict(baseColorFactor=[*base, 1.0], metallicFactor=metal, roughnessFactor=rough))
        if em:
            s = glow.get(n, strength)
            m["emissiveFactor"] = list(em)
            m["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": s}}
        mats.append(m)
    return mats


def _flat(tris):
    v = tris.reshape(-1, 3)
    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    n = np.cross(e1, e2)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return v, np.repeat(n, 3, axis=0)


def _write(gltf, b):
    gltf["buffers"] = [dict(byteLength=len(b.bin))]
    gltf["bufferViews"] = b.views
    gltf["accessors"] = b.accessors
    js = _pad(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    bn = bytes(_pad(bytes(b.bin)))
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bn))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bn), 0x004E4942) + bn
    return out


def static_glb(J, pose=None, attach=None, seams=None, extra_tris=None, glow=None, hide_lit=False):
    """Bake a posed model. extra_tris: {material: (N,3,3) tris} e.g. the mannequin."""
    pose = regent.solve_pistons(J, pose or {})
    mats = regent.matrices(J, pose, attach, seams)
    by_mat = {}
    for name, j in J.items():
        m = mats[name]
        for pr in j.prims:
            if hide_lit and pr.material == "seam_lit":
                continue
            t = pr.tris.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            by_mat.setdefault(pr.material, []).append(t.reshape(-1, 3, 3))
    for k, v in (extra_tris or {}).items():
        by_mat.setdefault(k, []).append(v)
    names = sorted(by_mat)
    b = _Builder()
    prims = []
    for i, n in enumerate(names):
        tris = np.concatenate(by_mat[n]) * SCALE
        v, nn = _flat(tris)
        pa = b.add(v, target=34962, minmax=True)
        na = b.add(nn, target=34962)
        prims.append(dict(attributes=dict(POSITION=pa, NORMAL=na), material=i))
    extra_mats = {"skin": ((0.3, 0.3, 0.31), 0.0, 0.95, None, 0.0), "armor": ((0.36, 0.38, 0.42), 0.6, 0.5, None, 0.0)}
    for k, v in extra_mats.items():
        regent.MATERIALS.setdefault(k, v)
    gltf = dict(asset=dict(version="2.0", generator="clockwork-regent"), scene=0, scenes=[dict(nodes=[0])],
                nodes=[dict(name="clockwork_regent", mesh=0)], meshes=[dict(primitives=prims)],
                materials=_materials(names, glow), extensionsUsed=["KHR_materials_emissive_strength"])
    return _write(gltf, b)


def _quat(axis, deg):
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    h = math.radians(deg) / 2
    return [*(a * math.sin(h)), math.cos(h)]


def _quat_from_matrix(R):
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return [x, y, z, w]


def _seam_rot(axis):
    y = np.asarray(axis, float) / np.linalg.norm(axis)
    x = np.cross(y, [0, 0, 1]) if abs(y[2]) < 0.9 else np.cross(y, [1, 0, 0])
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)


def rigged_glb(J, clips=None, glow=None):
    """clips: {clip: {"times": [s...], "frames": [ {joint: angle/slide}, ...], "seams": [ {joint: scale}, ... ]}}"""
    clips = clips or {}
    b = _Builder()
    names = list(J)
    index = {n: i for i, n in enumerate(names)}
    mat_names = sorted({pr.material for j in J.values() for pr in j.prims})
    mat_index = {n: i for i, n in enumerate(mat_names)}
    nodes, meshes = [], []
    seam_R = {}
    for n in names:
        j = J[n]
        parent_piv = J[j.parent].pivot if j.parent else np.zeros(3)
        node = dict(name=n, translation=((j.pivot - parent_piv) * SCALE).tolist())
        R0 = np.eye(3)
        if j.kind == "seam":
            R0 = _seam_rot(j.axis)
            seam_R[n] = R0
            node["rotation"] = _quat_from_matrix(R0)
        # Children of a seam inherit its rotation; seams here are leaves, so nothing to undo.
        if j.prims:
            prims = []
            groups = {}
            for pr in j.prims:
                groups.setdefault(pr.material, []).append(pr.tris)
            for mname, tl in groups.items():
                tris = np.concatenate(tl) - j.pivot
                tris = (tris.reshape(-1, 3) @ R0).reshape(-1, 3, 3) * SCALE
                v, nn = _flat(tris)
                prims.append(dict(attributes=dict(POSITION=b.add(v, target=34962, minmax=True), NORMAL=b.add(nn, target=34962)),
                                  material=mat_index[mname]))
            meshes.append(dict(name=n, primitives=prims))
            node["mesh"] = len(meshes) - 1
        nodes.append(node)
    for n in names:
        kids = [index[c] for c in names if J[c].parent == n]
        if kids:
            nodes[index[n]]["children"] = kids
    roots = [index[n] for n in names if not J[n].parent]
    nodes.append(dict(name="clockwork_regent", children=roots))

    anims = []
    for cname, clip in clips.items():
        times = np.asarray(clip["times"], np.float32)
        t_acc = b.add(times, typ="SCALAR", minmax=True)
        samplers, channels = [], []
        for n in names:
            j = J[n]
            parent_piv = J[j.parent].pivot if j.parent else np.zeros(3)
            if j.kind == "hinge":
                vals = [f.get(n, 0.0) for f in clip["frames"]]
                if not any(abs(v) > 1e-6 for v in vals):
                    continue
                q = np.array([_quat(j.axis, v) for v in vals], np.float32)
                samplers.append(dict(input=t_acc, output=b.add(q, typ="VEC4"), interpolation="LINEAR"))
                channels.append(dict(sampler=len(samplers) - 1, target=dict(node=index[n], path="rotation")))
            elif j.kind == "slide":
                vals = [f.get(n, 0.0) for f in clip["frames"]]
                tr = np.array([((j.pivot - parent_piv) + j.axis * v) * SCALE for v in vals], np.float32)
                samplers.append(dict(input=t_acc, output=b.add(tr), interpolation="LINEAR"))
                channels.append(dict(sampler=len(samplers) - 1, target=dict(node=index[n], path="translation")))
            elif j.kind in ("seam", "glow") and clip.get("seams"):
                vals = [max(s.get(n, 1.0), 1e-3) for s in clip["seams"]]
                sc = np.array([[1.0, v, 1.0] if j.kind == "seam" else [v, v, v] for v in vals], np.float32)
                samplers.append(dict(input=t_acc, output=b.add(sc), interpolation="LINEAR"))
                channels.append(dict(sampler=len(samplers) - 1, target=dict(node=index[n], path="scale")))
        if channels:
            anims.append(dict(name=cname, samplers=samplers, channels=channels))

    gltf = dict(asset=dict(version="2.0", generator="clockwork-regent"), scene=0, scenes=[dict(nodes=[len(nodes) - 1])],
                nodes=nodes, meshes=meshes, materials=_materials(mat_names, glow),
                extensionsUsed=["KHR_materials_emissive_strength"])
    if anims:
        gltf["animations"] = anims
    return _write(gltf, b)


def mannequin_tris(player_pose, slim=False, armor=False):
    """Vanilla player boxes (posed) as triangles for renders."""
    import player
    import mesh
    parts, _ = player.player_parts(player_pose, slim=slim, armor=armor, skin_layers=False)
    out = {"skin": [], "armor": []}
    for _, (m, boxes) in parts.items():
        for bx in boxes:
            pr = mesh.box(bx.size, 0.0)
            c = bx.lo + bx.size / 2
            t = pr.tris.reshape(-1, 3) + c
            t = t @ m[:3, :3].T + m[:3, 3]
            out["armor" if bx.tag == "armor" else "skin"].append(t.reshape(-1, 3, 3))
    return {k: np.concatenate(v) for k, v in out.items() if v}
