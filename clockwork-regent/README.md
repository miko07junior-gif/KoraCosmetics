# Clockwork Regent

Back-mounted folding wings for Kora Client: an ancient, long-dormant mechanical
monarch. Target build Kora 0.13.0.

- **Folded:** the leading edges rise into a gothic pointed arch around the wearer's head, a statue standing in a niche.
- **Spread:** a rising art deco sunburst of three stepped brass tiers.

## Status

| Brief step | State |
|---|---|
| Read Kora first | **Blocked.** The zip is on the Windows machine and this cloud session can't reach it. Checklist, developer questions and data requests: [docs/kora-intake.md](docs/kora-intake.md) |
| 1. Notan and silhouette thumbnails | **Done, against vanilla stand-ins.** Icon sizes and screen settings are placeholders until Kora's preview size and player data are known. [renders/step1](renders/step1) |
| 2. Gray box in Kora | **Prepared, not imported.** Format-neutral rig with hierarchy, fold, pistons and gears, clear of the vanilla pose envelope ([design/regent_graybox.json](design/regent_graybox.json)). Importing through Kora's pipeline needs the zip. The step 2 gates need Kora and players. |
| 3-6. Full model, ortho views, callout sheet, captures | Not started. These come after the step 2 gates, as the brief orders. |
| Timing from footage | Not started. Groundwork and measuring protocol: [docs/timing-research.md](docs/timing-research.md) |

Design rationale and every measured number: [docs/design-notes.md](docs/design-notes.md).

## Decisions waiting on the brief's owner

1. **Capes.** A vanilla cape sweeps exactly where the brief puts the bronze spine and heart, so "no clipping against a worn cape" is only possible if Kora hides or moves the cape when wings are worn. If Kora draws both with vanilla physics, the spine-on-the-back idea has to give. See design notes §3.
2. **Recoil.** Early research suggests a real recoil escapement backs up slowly, over roughly half the beat, rather than kicking. Should the tick follow the real mechanism or the brief's "small kick back"? Footage settles what's real; the stylisation is a creative call.
3. **F5.** Spread covers about 7% of the wearer's F5 screen and nearly half its centre third at 1080p FOV 70. The crosshair is never covered. Is "no blocking" measured against Kora's existing wings, or does it mean a fixed limit?

## Tools

Python 3 with numpy and Pillow. Run from `tools/`:

| Script | Does |
|---|---|
| `make_step1.py` | Silhouettes at icon size and at 30 blocks (true screen pixels), notan, value key with measured area shares |
| `clipcheck.py [--rare] [--cape] [--slim] [--no-armor]` | Every rig cube vs every player cube over the vanilla pose envelope, for every wing state. Exits non-zero on any clip. |
| `f5check.py` | How much of the wearer's own F5 view the cosmetic covers |
| `export_graybox.py` | Writes `design/regent_graybox.json`, the hand-off to Kora's format |

Shared modules: `geom.py` (frames, boxes, separating-axis test), `player.py` (vanilla
player model and poses), `rig.py` (the gray box and its poses), `render.py` (a
no-anti-aliasing rasteriser, like the game's), `scene.py`.
