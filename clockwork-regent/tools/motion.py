"""Motion from a simulated recoil (anchor) escapement.

Real recoil escapement, per beat, with the pendulum swinging from one extreme to the
other (theta = A cos(pi u), u = 0..1 over the beat):
  recovery  the wheel creeps forward, undoing the last recoil, as the pendulum heads back
  impulse   the wheel keeps pushing forward through the pallet while the pendulum crosses centre
  drop      the tooth escapes the pallet tip and the wheel jumps forward freely (instant)
  recoil    the other pallet catches it, and the wheel is pushed BACKWARD while the
            pendulum finishes its swing (a slow drift, not a snap)
Net advance per beat = K*lift + drop. With the defaults below one beat = 6 deg of a
30-tooth wheel = one seconds mark, and the recoil is 1.5 deg over ~0.3 s.

The drive is geared to every joint; each joint has mass, so it follows the drive
through a damped spring: brass is slow to start and overshoots when it stops.

The constants are provisional: they come from the published geometry of anchor
escapements (see docs/timing-research.md), not from frame-stepped footage yet.
"""
import math

import numpy as np

import regent

ESC = dict(A=2.5, lift=3.0, drop=1.5, K=1.5)     # degrees; K*lift + drop = 6 deg per beat
FPS = 30                                          # key rate for the viewer; Kora export resamples to ticks


def beat_profile(u, esc=ESC):
    """Wheel advance (deg) within one beat, u in [0, 1). Starts at maximum recoil."""
    A, lam, K, drop = esc["A"], esc["lift"], esc["K"], esc["drop"]
    xi = A - A * math.cos(math.pi * u)          # pendulum travel since the extreme, 0..2A
    catch = A + lam / 2
    if xi <= catch:
        return K * xi
    return K * catch + drop - K * (xi - catch)


def wheel(t, beat_times, esc=ESC):
    """Escape-wheel angle (deg) at time t given the start time of every beat (sorted)."""
    step = esc["K"] * esc["lift"] + esc["drop"]
    n = np.searchsorted(beat_times, t, side="right") - 1
    if n < 0:
        return 0.0
    if n >= len(beat_times) - 1:
        return step * (len(beat_times) - 1)
    u = (t - beat_times[n]) / (beat_times[n + 1] - beat_times[n])
    return step * n + beat_profile(u, esc)


def spring(target, dt, omega, zeta=0.55, x0=None):
    """Follow `target` (array over time) with a damped spring: mass, lag and overshoot."""
    x = np.zeros_like(target)
    x[0] = target[0] if x0 is None else x0
    v = 0.0
    for i in range(1, len(target)):
        a = omega * omega * (target[i - 1] - x[i - 1]) - 2 * zeta * omega * v
        v += a * dt
        x[i] = x[i - 1] + v * dt
    return x


def _times(duration, fps=FPS, sim=1000):
    ts = np.arange(0, duration + 1e-9, 1.0 / sim)
    keys = np.round(np.arange(0, duration + 1e-9, 1.0 / fps) * sim).astype(int)
    return ts, keys


def _beats(spec):
    """spec: list of (count, period) -> beat start times."""
    t, out = 0.0, [0.0]
    for count, period in spec:
        for _ in range(count):
            t += period
            out.append(t)
    return np.array(out)


def _windowed(w, step, b0, b1):
    """0..1 progress of a joint group clutched to the wheel between beats b0 and b1."""
    return np.clip((w - step * b0) / (step * (b1 - b0)), 0.0, 1.0)


def _seam_order(J):
    """Light path from the heart outward: (seam joint, path rank 0..1)."""
    order = []
    for name, j in J.items():
        if j.kind not in ("seam", "glow"):
            continue
        if name.startswith("seam_heart"):
            r = 0.0
        elif name.startswith("seam_root"):
            r = 0.12
        elif name.startswith("seam_humerus"):
            r = 0.25
        elif name.startswith("seam_elbow"):
            r = 0.38
        elif name.startswith("seam_forearm"):
            r = 0.45 + 0.05 * int(name.split("_")[2])
        elif name.startswith("seam_hand"):
            r = 0.6 + 0.05 * int(name.split("_")[2])
        else:   # blade seams: coverts, then secondaries, then primaries, inner blades first
            tier = name.split("_")[1]
            k = int(name.split("_")[-1])
            r = {"coverts": 0.78, "secondaries": 0.86, "primaries": 0.93}[tier] + 0.008 * k
        order.append((name, r))
    return order


def clip_idle(J, spread, seconds=4.0, lit=None):
    """Looping idle: the escapement ticks at 1 Hz; the wings take a tiny jolt each beat."""
    ts, keys = _times(seconds)
    beats = _beats([(int(seconds), 1.0)])
    step = ESC["K"] * ESC["lift"] + ESC["drop"]
    w = np.array([wheel(t, beats) for t in ts])
    trend = step * ts
    jitter = w - trend                                   # sawtooth-ish, mean ~0, +/- a few deg
    jitter -= jitter.mean()
    tremor = spring(jitter, 1e-3, 2 * math.pi * 5.0, 0.35) * (0.05 if not spread else 0.08)
    pend = ESC["A"] * np.cos(math.pi * ts)               # pendulum, one beat per second
    base = regent.pose_state(t=1.0 if spread else 0.0)
    frames, seams = [], []
    lit = (1.0 if spread else 0.0) if lit is None else lit
    seam_names = [n for n, j in J.items() if j.kind in ("seam", "glow")]
    for i in keys:
        f = dict(base)
        for side in ("r", "l"):
            f[f"forearm_{side}"] = f.get(f"forearm_{side}", 0.0) + tremor[i]
            f[f"hand_{side}"] = f.get(f"hand_{side}", 0.0) + tremor[i] * 0.6
            for tier in regent.TIERS:
                f[f"{tier}_{side}"] = f.get(f"{tier}_{side}", 0.0) + tremor[i] * (0.8 if spread else 0.3)
            f[f"elbow_gear_{side}"] = f.get(f"elbow_gear_{side}", 0.0) - 0.5 * w[i]
            f[f"shoulder_gear_{side}"] = f.get(f"shoulder_gear_{side}", 0.0) + 0.25 * w[i]
        f["escape_wheel"] = -w[i]
        f["pallet"] = 3.2 * pend[i]
        frames.append(regent.solve_pistons(J, f))
        s = {n: lit for n in seam_names}
        s["seam_heart"] = 1.0 if spread else DORMANT_HEART
        seams.append(s)
    return dict(times=(keys / 1000.0).tolist(), frames=frames, seams=seams, loop=True)


WAKE = dict(
    beats=[(1, 0.9), (1, 0.6), (1, 0.42), (1, 0.32), (22, 0.25)],     # slow to start, then 4 beats/s
    windows=dict(light=(0, 7), arch=(3, 8), lift=(4, 9), coverts=(7, 11), secondaries=(10, 14),
                 primaries=(13, 18), ext=(17, 21)),
)
SLEEP = dict(
    beats=[(18, 0.25), (1, 0.32), (1, 0.42), (1, 0.6), (1, 0.9)],     # runs down, hard to stop
    windows=dict(ext=(0, 3), primaries=(2, 7), secondaries=(6, 10), coverts=(9, 13), lift=(12, 17),
                 arch=(13, 18), light=(15, 22)),
)
OMEGA = {"arch": 4.0, "lift": 3.0, "coverts": 5.0, "secondaries": 4.0, "primaries": 3.0, "ext": 4.5}   # Hz; heavier = lower


def _transition_curves(spec, seconds, closing=False):
    ts, keys = _times(seconds)
    beats = _beats(spec["beats"])
    step = ESC["K"] * ESC["lift"] + ESC["drop"]
    w = np.array([wheel(t, beats) for t in ts])
    prog = {}
    for g, (b0, b1) in spec["windows"].items():
        d = _windowed(w, step, b0, b1)
        if closing:
            d = 1.0 - d
        prog[g] = spring(d, 1e-3, 2 * math.pi * OMEGA[g], 0.55) if g in OMEGA else d
    return ts, keys, w, prog


def _transition_clip(J, spec, seconds, closing):
    ts, keys, w, prog = _transition_curves(spec, seconds, closing)
    order = _seam_order(J)
    frames, seams = [], []
    for i in keys:
        p = {g: float(v[i]) for g, v in prog.items()}
        f = regent.pose_state(t=0.0, arch_t=p["arch"], lift_t=p["lift"],
                              tier_t=dict(coverts=p["coverts"], secondaries=p["secondaries"], primaries=p["primaries"]),
                              ext_t=p["ext"])
        f["escape_wheel"] = -w[i]
        f["pallet"] = 3.2 * ESC["A"] * math.cos(math.pi * ts[i] / 0.25)
        for side in ("r", "l"):
            f[f"elbow_gear_{side}"] = f.get(f"elbow_gear_{side}", 0.0) - 0.5 * w[i]
        frames.append(regent.solve_pistons(J, f))
        light = p["light"]
        # each seam fills from its inner end once the light front reaches it; the heart never fully dies
        s = {name: float(np.clip((light * 1.15 - rank) / 0.12, 0.0, 1.0)) for name, rank in order}
        s["seam_heart"] = max(s.get("seam_heart", 0.0), DORMANT_HEART)
        seams.append(s)
    return dict(times=(keys / 1000.0).tolist(), frames=frames, seams=seams, loop=False)


DORMANT_HEART = 0.45


def clip_wake(J, seconds=6.2):
    return _transition_clip(J, WAKE, seconds, closing=False)


def clip_sleep(J, seconds=6.4):
    return _transition_clip(J, SLEEP, seconds, closing=True)


def build_clips(J):
    clips = {
        "idle_folded": clip_idle(J, spread=False),
        "wake": clip_wake(J),
        "idle_spread": clip_idle(J, spread=True),
        "sleep": clip_sleep(J),
    }
    return clips


def timing_chart(seconds=6.2):
    """Per-tick table of the wake schedule (for the callout sheet)."""
    ts, keys, w, prog = _transition_curves(WAKE, seconds)
    rows = []
    for i in np.round(np.arange(0, seconds + 1e-9, 0.05) * 1000).astype(int):
        rows.append(dict(tick=int(round(ts[i] * 20)), wheel_deg=round(float(w[i]), 2),
                         **{g: round(float(v[i]), 3) for g, v in prog.items()}))
    return rows
