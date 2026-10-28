# Clockwork Regent

Back-mounted folding wings for Kora Client: an ancient, long-dormant mechanical
monarch. Target build Kora 0.13.0.

- **Folded:** the leading edges close into a curved gothic arch around the head, with crockets and cusps, and the three feather tiers lie inside it like a portal's archivolts.
- **Spread:** the tiers rise into an art deco sunburst, the primaries telescope out of their sheaths, and every seam lights from the escapement heart outward.

**Viewer:** https://claude.ai/artifact/GrTkDEfamsbY9obZbGoKjz (private until you share it).
Play dormant, wake, awake and sleep; switch stand or sneak, day or night; look from F5, 10 blocks and 30 blocks.

## Decisions from the brief's owner (2026-10-28)

| Question | Decision |
|---|---|
| Model resolution | High-resolution and intricate (bevelled plates, toothed gears, tapered stepped blades), not 1-px boxes |
| Mount | Wings attach directly to the back: each shoulder joint sits flush in a plate on the shoulder blade. No standoff, no yoke, nothing tying the wings together |
| Capes | Not taken into account |
| Recoil | Follow the real mechanism: a simulated anchor escapement drives everything |

## Status

| Brief step | State |
|---|---|
| Read Kora first | **Blocked.** The zip is on the Windows machine. See [docs/kora-intake.md](docs/kora-intake.md) |
| 1. Notan and silhouette thumbnails | Redone for the high-resolution model: [renders/step1](renders/step1). Icon sizes and screen settings are still placeholders. |
| 2. Gray box in Kora | Model, rig and clips exist as a GLB plus a format-neutral spec ([design](design)). Importing through Kora's pipeline needs the zip; the gates need Kora and players. |
| 3. Full model | Geometry, rig, light path and all four clips done, with gray-box materials. Texture painting waits on Kora's texel-density range. |
| 4. Ortho views | Shaded front, back, side and 3/4, folded and spread, on neutral dark grey with even light: [renders/model](renders/model). Paint-overs follow texturing. |
| 5. Callout sheet | Inputs ready (spec, timing table, clearance numbers); the sheet itself comes after painting |
| 6. In-game captures | Needs Kora |
| Timing from footage | The escapement model stands in, with published geometry. Footage still has to be frame-stepped to tune it: [docs/timing-research.md](docs/timing-research.md) |

Design rationale and every measured number: [docs/design-notes.md](docs/design-notes.md).

## Tools

Python 3 with numpy and Pillow, plus Node with Playwright and three.js for shaded
renders (`npm install three@0.160.0`, then set `THREE_DIR` or `SCRATCH`). Run from `tools/`.

| Script | Does |
|---|---|
| `regent.py` | The model: joints, pivots, hinge axes, geometry, poses |
| `motion.py` | The escapement simulation and the clips built from it |
| `export_model.py` | Writes `design/regent_rigged.glb`, `regent_spec.json`, `timing_wake.csv` |
| `make_viewer.py OUT.html` | The interactive viewer page with the GLB inlined |
| `render_views.py sheet\|unfold\|night OUT.png` | Shaded renders through three.js in headless Chromium |
| `clipcheck.py [--rare] [--slim] [--no-armor] [--quick]` | Every model primitive vs the vanilla player over its pose envelope, every wing state |
| `make_step1.py` | Silhouettes at icon size and at 30 blocks (true screen pixels), notan, value key |
| `f5check.py` | How much of the wearer's own F5 view the wings cover |

Shared modules: `mesh.py` (bevelled extrusions, gears, blades, lancets), `geom.py`
(frames, oriented boxes, separating-axis test), `player.py` (vanilla player model
and poses), `render.py` (a no-anti-aliasing rasteriser, like the game's),
`export_glb.py`, `scene.py`.
