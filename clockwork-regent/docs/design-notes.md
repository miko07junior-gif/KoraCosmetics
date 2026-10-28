# Clockwork Regent: design notes (high-resolution model)

Numbers are in model pixels (px = 1/16 block) unless marked as blocks, and blocks
include vanilla's 15/16 player scale. Every check runs against a vanilla Minecraft
1.21.x stand-in for the player, not Kora. The scripts in `../tools` regenerate
everything; where this page and a script disagree, the script wins.

## 1. Concept to geometry

| Brief | Model |
|---|---|
| Folded, the leading edges rise into a pointed arch that frames the head without covering it | Each wing has a humerus, then a forearm and hand built as voussoirs on a drop-arch curve (radius 0.7 x span), with brass crockets on the outside and cusps on the inside. The two halves of an ivory finial close at the apex, 6.8 px above the head. |
| Spread, three stepped tiers of brass blade-feathers radiate like the Chrysler crown | 5 coverts, 6 secondaries, 7 primaries per wing fan from the elbow between 66 and 150 deg. Each blade is a blackened-bronze plate with a stepped Chrysler point and a brass rib (ivory on the coverts). The primaries carry amber triangle windows and telescope 6 px out of their sheaths. Three primaries and one secondary are chipped; one primary is snapped short. |
| Folded is dormant, spread is awake | Folded, the tiers lie inside the arch like the archivolts of a cathedral portal, and only the heart glows, at half strength. Waking, the arch splits at the apex, the tiers rise in turn, and the seams light from the heart outward. |
| One light source, an escapement heart at the root of the spine | A trefoil-framed escapement flush on the back between the two wing roots: a 15-tooth escape wheel, an anchor with pallets, amber glass and a lit core. Every seam is a lit strip that fills outward from the heart. |
| Hierarchy spine -> joint -> feather group, named pivots | `root -> shoulder -> {humerus, forearm -> hand, coverts / secondaries / primaries -> blades -> extensions}`, plus gears, a piston per wing, and light nodes: 130 joints (59 hinges, 16 slides, 55 lights), ~24k triangles |
| Pistons telescope within travel, gears turn with the hinges | Shoulder piston: anchor-to-pin length 7.6-7.7 px against a 1.5 px minimum overlap; rod and cylinder never bottom out. The shoulder gear turns 2:1 with the humerus, the elbow gear 1.5:1 with the primaries hinge, and the heart's wheel and pallet run the escapement. |

## 2. Mount: straight onto the back

The owner asked for the wings to attach directly to the body, with nothing in
between. So each wing has its own gothic plate flat on the shoulder blade (z 3.0-3.5
on a chestplate). The shoulder joint is sunk into that plate. Nothing joins the two
wings.

One constraint is geometric. Where the arm meets the shoulder (x 3-5), a resting
helmet's lower edge (y 23, back face z 5) sits above a sprinting arm's swing
(reaching z 4-5.6 at y 22-23). The only gap between them is behind z 5. So the
humerus root curves back about 2 px over the shoulder blade before it rises. That
curve is the smallest lift that passes between the two, and it is the wing's own
bone, not a separate connector.

Everything else is close to the body: the whole cosmetic sits within 5.5 px of the
chestplate (the first gray box needed 12.8 px).

### What the flush mount costs

- A turned head sweeps a helmet corner around a 7.07 px circle about the neck.
- Sneaking pitches the body 0.5 rad, and vanilla's own helmet already sinks about 2 px into the upper back.
- Anything on the upper back near the neck is inside both, so a turned or sneaking helmet brushes the wing shoulders.
- Arms, body and legs stay clean in every motion pose. Section 6 has the numbers.

## 3. Sizes

| | Model px | Blocks (15/16) |
|---|---|---|
| Folded width | 19.1 | 1.12 |
| Spread span | 50.4 | 2.95 |
| Top above the feet (folded / spread) | 41.2 / 42.0 | 2.41 / 2.46 (bare player 1.875) |
| Depth behind the chestplate | 5.5 | 0.32 |

## 4. Motion

Every move comes from a simulated anchor escapement: impulse, an instant drop, then
the recoil, a slow drift backward. Each part follows the drive through a damped
spring, so heavy brass is slow to start and overshoots when it stops. Constants,
schedule and the footage protocol are in [timing-research.md](timing-research.md).

Clips:
- `idle_folded`: 4 s loop at 1 Hz.
- `wake`: 6.2 s.
- `idle_spread`: 4 s loop.
- `sleep`: 6.4 s.

The wake schedule per tick is in `../design/timing_wake.csv`. Kora's sneak trigger
plays the same clips on the vanilla sneak pose.

## 5. Light path and emissive budget

- **Order:** heart, then root plates, humeri, elbow jewels, forearm, hand, coverts, secondaries, primaries (inner blades first).
- **Mechanics:** each lit strip scales from its inner end. Dormant, only the heart core shows, at 45% size, over dim seams.
- **Materials:** `seam` (dim), `seam_lit` (lit) and `amber` (glass and windows) are the only emissive ones.
- **Budget:** the night render shows it. Kora's bloom and emissive rules (intake section 1) decide the final strengths.

## 6. Clipping, value key and F5

### Clipping

CLIP_TABLE

### Value key

Share of the visible cosmetic, with the wearer in place (bronze / brass / ivory+amber).
The target is 60 / 30 / 10.

| | Folded | Spread |
|---|---|---|
| back | 55 / 29 / 17 | 71 / 19 / 10 |
| 3/4 back | 58 / 28 / 14 | 71 / 20 / 9 |
| front | 69 / 30 / 1 | 76 / 22 / 2 |

- **Folded:** on target from behind.
- **Spread:** bronze-heavy, because the blade plates dominate.
- **Fix at painting:** brass bevels on the blade edges move about 10 points from bronze to brass, and ivory enamel on the front faces of the hub caps and coverts lifts the front views.

### Size at 30 blocks

In screen pixels, from `../renders/step1/step1_measurements.json`:

| Screen | Bare player h | Folded w x h | Spread w x h |
|---|---|---|---|
| 1080p FOV 70 | 49 | 28 x 61 | 76 x 64 |
| 1080p FOV 90 | 34 | 20 x 42 | 52 x 44 |
| 1080p FOV 110 | 23 | 14 x 29 | 36 x 31 |

### F5

Share of the wearer's own third-person view that the wings cover beyond the player
model, looking level (`../tools/f5check.py`):

| | FOV 70 screen / centre third / crosshair box | FOV 110 |
|---|---|---|
| folded | 0.8% / 7.5% / 2.7% | 0.2% / 1.8% / 27% |
| spread | 2.9% / 26% / 1.5% | 0.7% / 6.2% / 8.1% |

- **Scale:** about a third of the first gray box's coverage (7.4% / 47%), because the wings now sit against the back.
- **The crosshair point itself** is on the head and never covered.
- **The crosshair box** is ±5% of screen height around it. At FOV 110 the player is small, so the arch over the head fills part of that box.

## 7. Open risks for the step 2 gates

- **Texturing:** gray-box materials only. Painting waits on Kora's house texel density.
- **Format:** the model is a mesh. If Kora's format is cubes-only, the bevelled and curved parts must be re-cut into cubes; that is the biggest unknown in the intake.
- **PvP head reading:** the arch ring sits 2-4 px clear of the head in most views. At 30 blocks the folded silhouette keeps air between head and arch at FOV 70-90; at FOV 110 the gap closes to about 1 screen pixel.
- **Thumbnail:** at 64 px the spread fans can read as spread fingers. The store-grid test will tell.
- **Timing:** the escapement constants are from published geometry, not footage.
