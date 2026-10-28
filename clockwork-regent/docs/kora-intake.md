# Kora 0.13.0 intake: what to read, ask and request

Nothing here has been read yet. `Kora-0.13.0.zip` is on the Windows machine
(`C:\Users\MikoKonstantyNyborg\Downloads\`), and the cloud session that started this
work can't reach it. Carry on in a session that runs on that machine (Claude Desktop,
or `claude remote-control` in a terminal), or put the zip somewhere this repo's
sessions can read it.

Handling rules from the brief: extract a copy into its own empty folder, only read it,
and don't run any script from that copy. Recheck all of this on the next Kora release.

## 1. Read from the cosmetic loader and config

| Question | Why it matters here | Current stand-in |
|---|---|---|
| Supported Minecraft versions | Pose set for the clipping envelope (spear poses arrived in 1.21.11) | vanilla 1.21.x poses, `tools/player.py` |
| Model format (Bedrock geo, GeckoLib, OBJ, glTF, own JSON?), and whether it takes meshes or only cubes | The model is a high-resolution mesh (bevelled plates, toothed gears). A cubes-only format would mean re-cutting it into many small cubes | `design/regent_rigged.glb` + `design/regent_spec.json` |
| Axis, rotation order, units, pivot semantics | Conversion and mirroring | Minecraft ModelPart ZYX, pixels |
| Bone, vertex and triangle limits | The model uses **130 joints** (59 hinges, 16 slides, 55 light nodes) and **~24k triangles**. Light nodes can be merged per tier; blades per tier if needed | unknown |
| Texture size limits, filtering, mipmaps | Texel density, what survives at 30 blocks | unknown |
| How emissive is drawn; any bloom | Amber budget, night captures, light-travel effect | unknown |
| Can emissive animate (per-bone visibility, UV scroll, frame textures)? | The light path is built as lit strips that scale 0 to 1 along their length, so bone scale keys are enough. If Kora can't scale bones, visibility steps per strip work too | bone scale |
| Animation format; triggers (idle, sprint, sneak, menu, emote?) | Which states exist and what wakes the wings | brief's four states |
| Interpolation: stepped available, or only smooth? | If smooth only, recoil is authored as extra keys | unknown |
| Wings and cape at the same time? | The owner chose not to design around capes | not considered |
| Wings vs elytra, swimming, crawling, riding, sleeping | Whether those poses need clean clearance | excluded from the envelope |
| Player render scale for cosmetics (vanilla draws the player at 15/16) | 30-block and F5 sizes | 15/16 |
| Armor offset: does Kora push back-mounted cosmetics out when a chestplate is worn? | The root plates and heart sit flush on a chestplate (z = 3), so they float 1 px off a bare back | fixed position |
| Menu preview / store icon size and camera | Step 1 icon sheets use 64/96/128 as placeholders | placeholders |
| Own-player rendering in F5 (fade, hide, transparency?) | F5 occlusion numbers below may not apply | fully opaque |

If any of these exist only in compiled code, ask Kora's developers (section 2) rather
than decompiling.

## 2. Draft questions for Kora's developers

Send only the ones the zip doesn't answer.

1. Which Minecraft versions does 0.13.0 support, and does Kora add any player poses of its own?
2. What model and animation format does the cosmetic loader take, and what are the bone, cube and texture-size limits?
3. Are animations interpolated linearly, with easing, or can keys be stepped? Is there a minimum key spacing?
4. Which triggers can start a cosmetic animation (idle, sprint, sneak, jump, hurt, menu open, emote), and can a cosmetic hold a state, for example staying spread in the menu?
5. How is emissive rendered (full-bright layer, separate texture, alpha channel)? Is there bloom? Can emissive be animated or toggled per bone?
6. Can wings and a cape be worn together? If so, is the cape moved, shortened, or drawn over the wings?
7. Is a worn cosmetic hidden with elytra, swimming, crawling, riding or sleeping?
8. Is the wearer's own cosmetic faded or hidden in F5?
9. At what size and camera angle are store icons and the menu preview rendered, and are they anti-aliased?

## 3. Data requests (Kora's player data, aggregated)

- Screen resolutions and FOV settings (distribution, not just the mode), including the share using dynamic FOV.
- GUI scale for players who open the store, if the icon size depends on it.
- Most-worn skins (top 10, or top skin archetypes: slim vs classic, light vs dark, helmet worn).
- Servers played (PvP vs SMP share), to weight the PvP head-reading gate.
- Wing sales and how long buyers keep them equipped (7-day and 30-day), to pick the comparison wings and to set the "still wearing it a week later" bar.

## 4. From the cosmetics Kora ships: the house-style table

For every shipped cosmetic (and separately for every wing), measure each value and
report min / median / max:

| Metric | How |
|---|---|
| Texture size | file header |
| Texel density | texels per model pixel, per face; flag faces that differ |
| Bone count, cube count | model file |
| Animation length (each state) | animation file, in game ticks |
| Emissive coverage | share of visible texels that are emissive; brightest value |
| Edge treatment | painted bevel width in texels, outline or not |
| Shading treatment | ramp steps per material, hue shift, baked AO or flat |
| Span (spread / folded) | from the model, in blocks at 15/16 scale |
| F5 occlusion | `tools/f5check.py` with the shipped wing loaded |
| 30-block silhouette | `tools/make_step1.py` with the shipped wing loaded |

Clockwork Regent's own row is filled from `design/regent_spec.json` once painted.
