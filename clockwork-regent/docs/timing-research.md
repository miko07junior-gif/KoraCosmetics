# Timing research: groundwork for the tick and the unfold

**Status: the motion runs on a simulated escapement; footage hasn't been frame-stepped yet.**
The brief's owner chose real motion over the stylised "kick back", so every move is now
driven by a model of an anchor (recoil) escapement (`tools/motion.py`). Its constants
come from the published geometry below. Frame-stepped footage should tune them; the
protocol at the end says how.

## The motion model (tools/motion.py)

| Constant | Value | Meaning |
|---|---|---|
| Pendulum amplitude A | 2.5 deg | anchor clocks swing about 4-6 deg in total |
| Lift | 3.0 deg | pendulum arc during which the tooth is on the impulse face |
| Drop | 1.5 deg | free jump of the wheel when the tooth escapes |
| K (wheel deg per pendulum deg) | 1.5 | so impulse + drop = 6 deg per beat, one seconds mark on a 30-tooth wheel |
| Recoil | K x (A - lift/2) = 1.5 deg | the wheel is pushed back while the pendulum finishes its swing |

Per 1 s beat (20 ticks), the wheel:
1. creeps forward, recovering the last recoil (~6 ticks);
2. pushes forward through the impulse (~8 ticks, fastest at the centre of the swing);
3. drops instantly (+1.5 deg);
4. drifts back 1.5 deg over the last ~6 ticks.

The viewer's chart plots exactly this.

- **Idle (dormant and awake):** 1 Hz. The heart's wheel and pallet move with it. The wings take a damped jolt at each drop, at most 0.17 deg folded and 0.28 deg spread (peak to peak), too small to pull an opponent's eye.
- **Wake:** the train starts slowly (beats of 0.9, 0.6, 0.42 and 0.32 s), then runs at 4 beats/s. Each part is clutched to the wheel for its own window of beats: light, then arch, lift, coverts, secondaries, primaries, telescoping. Wake ends at 6.2 s (124 ticks).
- **Mass:** each part follows the drive through a damped spring (zeta 0.55). Heavier parts are slower (primaries 3 Hz, coverts 5 Hz). That gives the lag at the start ("slow to start") and the overshoot when a window closes ("hard to stop").
- **Sleep:** the same machinery reversed in order. Primaries close first, the light retreats into the heart last, and the train runs down to long beats.
- **Per-tick table:** `design/timing_wake.csv`.

Minecraft runs at 20 ticks/s, so 1 tick = 50 ms = 3 frames at 60 fps = 6 frames at 120 fps.

## What sources say

| Item | Value | Source |
|---|---|---|
| Longcase (seconds-pendulum) beat | 1 beat/s, 3600 beats/h | [Seconds pendulum](https://en.wikipedia.org/wiki/Seconds_pendulum); [Britannica 1771](https://jimclifford.ca/early_encyclopedia_britannica/articles/1771/eb_1st_1771_013162.html) |
| Escape wheel | 30 teeth, 1 rev/min, seconds hand on its arbor | [Commons anchor-escapement animation](https://commons.wikimedia.org/wiki/File:Anchor_escapement_animation_315x478px.gif) |
| Pendulum arc | anchor clocks about 4-6 deg; "a few degrees" | [V&A longcase clock](https://collections.vam.ac.uk/item/O167453/longcase-clock-clement-william/) |
| Seconds hand | jumps forward, then "moves backwards a little just after" | [Model Engineer forum](https://www.model-engineer.co.uk/forums/topic/no-recoil/) (practitioner, not a reference) |
| Recoil size | forum advice: about half a tooth on entry, less on exit; some clocks show almost none | [NAWCC forum](https://mb.nawcc.org/threads/recoil-escapement-accuracy-vs-dead-beat.136927/) (unverified) |
| Drop time, recoil time, overshoot, settle | **not found** | |
| Peacock Clock order | owl, then peacock, then rooster | [lidenz.com](https://lidenz.com/peacock-clock-interesting-sight-seeing-inside-hermitage/) |
| Peacock start | about 90 s after the owl starts | [vsemart.com](https://vsemart.com/hermitage-peacock-clock/) |
| Peacock motion | raises and opens the tail, bows, turns about 180 deg at full spread, holds, turns back, folds | [Rambler](https://weekend.rambler.ru/other/41360312-ermitazh-glavnye-tayny-muzeya/); lidenz |
| Tail-opening time, stepped vs smooth | **not found** (only "slowly") | |
| Silver Swan length | about 32 s, or about 40 s, depending on source | [Wikipedia](https://en.wikipedia.org/wiki/Silver_Swan_(automaton)); [Smithsonian](https://www.smithsonianmag.com/smart-news/robotic-silver-swan-has-fascinated-fans-nearly-250-years-180962024/) |
| Silver Swan mechanism | three clockwork trains; the neck is driven by a zig-zag cam track | [Bowes Museum](https://thebowesmuseum.org.uk/collections/the-silver-swan/); [open-access paper](https://ray.yorksj.ac.uk/id/eprint/7932/) |

## Inferences (not published; the research agent's own reasoning, to check against footage)

- At 1 beat/s the idle tick is one beat per **20 ticks**. That much follows from the brief's "1 Hz" and needs no footage.
- With the Commons animation's drawn angles applied to a sinusoidal pendulum, the recoil phase (the wheel backing up and coming back) takes about **0.57 s of each 1 s beat (about 11 ticks)**. Only the drop is near-instant.
- If that holds, a real recoil is a **slow backward drift**, not a snap. The brief's "jump forward and a small kick back" is a stylisation of it. That's a creative call for the brief's owner (see the open questions in the README).

## Footage found (all streaming-only; none downloadable under a free licence)

- Peacock Clock, Hermitage channel, 3:35: https://www.youtube.com/watch?v=ilPlVRoUl_8 (attributed to the Hermitage by [HASTA St Andrews](http://www.hasta-standrews.com/features/2018/2/20/the-peacock-clock-at-the-hermitage)). Atlas Obscura notes the action starts about 0:56 in its embed: https://www.atlasobscura.com/articles/2688
- Silver Swan, Bowes Museum "Swan Study Week": https://www.youtube.com/watch?v=ECuS6HDa-9Y ; others of unverified origin: https://www.youtube.com/watch?v=AOXqCuqDOiI , https://www.youtube.com/watch?v=T7kmsiQpTaE
- Escapement: only the CC0 Commons GIF above, which is a drawing (reportedly 72 frames over 3.6 s), not footage. No freely licensed film of a real recoil escapement was found.

## Measuring protocol (for whoever steps the footage)

1. Use a source at 50 fps or more, at the original speed. Check it against an audible tick or a visible seconds hand. Note the frame rate.
2. **Escapement.** Track the seconds-hand tip angle every frame across at least 10 beats. Record per beat: frames from rest to peak (the jump), peak overshoot in degrees, frames from peak back to settle (the recoil), and the settled advance (6 deg per beat on a 30-tooth wheel).
3. **Peacock tail.** Record frames from first tail movement to full spread, the number of visible hesitations (stepped vs smooth), and how long the hold lasts.
4. **Silver Swan neck.** Record each turn's duration and the pause between reversals.
5. Convert frames to ticks: ticks = frames / fps x 20. Report the median and range, not a single run.
6. Fill the timing chart in the callout sheet (step 5). If Kora only interpolates smoothly, each jump and recoil becomes explicit keys (start, peak, recoil end, settle).
