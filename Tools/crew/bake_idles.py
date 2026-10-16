"""Crew C1b: bakes the CMU idle clips (Tools/crew/clips.csv, fetched by fetch_cmu.sh into Data/CMU/raw) into
Source/SailingSim/Private/CrewClipData.inl, the table the crew's clip layer plays (CrewClips.h).

Each clip becomes, per frame at RATE Hz, each joint's motion about the posture it is held in (R = Delta * Slow, the slow
posture a Gaussian mean over HIGHPASS_S, the jitter smoothed over LOWPASS_S) as a rotation vector in the character frame
(CrewPose.h: X facing, Y right, Z up), plus the gaze's turn from the head and neck (yaw, pitch). The subject's heading is
taken out of the pelvis. Deltas are compressed softly toward each joint's limit (L tanh(a / L)), so the runtime clamp is a
backstop. Weight-shift onsets (the trunk's lean, sideways or fore and aft, starting a move of at least SHIFT_MIN_DEG) are
listed per clip with their direction and axis, so a shift can be started in step with a change of heel: a sailor facing
forward feels the heel sideways, one facing across the boat fore and aft.
    Tools/venv/bin/python Tools/crew/bake_idles.py
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "Data", "CMU", "raw")
OUT = os.path.join(ROOT, "Source", "SailingSim", "Private", "CrewClipData.inl")
RATE = 15.0
LOWPASS_S = 0.08
HIGHPASS_S = 4.0
SHIFT_MIN_DEG = 1.2

# The layer's joints and how far a clip may turn each from the stance (degrees): what SK_Sailor's stances can take without
# a limb leaving its place (a free hand stays within a hand's width, the trunk within a few degrees of the balance lean).
JOINTS = [("pelvis", 2.5), ("spine", 7), ("chest", 6), ("shoulder_l", 6), ("shoulder_r", 6), ("upperarm_l", 14),
          ("upperarm_r", 14), ("forearm_l", 14), ("forearm_r", 14), ("hand_l", 18), ("hand_r", 18)]
GAZE_LIMITS = (25, 10)   # yaw, pitch
ARMS = {"shoulder_l", "shoulder_r", "upperarm_l", "upperarm_r", "forearm_l", "forearm_r", "hand_l", "hand_r"}


def soft(v, limit_deg):
    """Rotation vectors (N,3) compressed toward the limit."""
    a = np.linalg.norm(v, axis=1)
    L = np.radians(limit_deg)
    s = np.where(a > 1e-9, L * np.tanh(a / L) / np.maximum(a, 1e-12), 1.0)
    return v * s[:, None]


def resample(q, hz, start, end):
    """Unit quaternions (N,4) at hz to RATE between start and end seconds (nlerp)."""
    t = np.arange(start, end, 1.0 / RATE)
    x = t * hz
    i = np.clip(np.floor(x).astype(int), 0, len(q) - 2)
    f = (x - i)[:, None]
    a, b = q[i], q[i + 1].copy()
    b[(a * b).sum(1) < 0] *= -1
    r = a * (1 - f) + b * f
    return r / np.linalg.norm(r, axis=1, keepdims=True)


def rotate(q, v):
    """Rotates vectors v (3,) by quaternions q (N,4) (FQuat's formula)."""
    u = q[:, :3]
    w = q[:, 3:4]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def lean_signal(qs, axis):
    """The chest's up after pelvis * spine * chest turns: toward the sailor's right (axis 0) or forward (axis 1), degrees."""
    q = cmu.quat_mul(cmu.quat_mul(qs["pelvis"], qs["spine"]), qs["chest"])
    up = rotate(q, np.array([0.0, 0.0, 1.0]))
    return np.degrees(np.arcsin(np.clip(up[:, 1 if axis == 0 else 0], -1, 1)))


def onsets(lean):
    """(frame, direction) where the lean starts a move of at least SHIFT_MIN_DEG (+1 toward the right or forward)."""
    k = max(1, int(0.3 * RATE))
    s = np.convolve(np.pad(lean, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    # Turning points with hysteresis: a move starts at the last extreme once the lean has left it by SHIFT_MIN_DEG.
    out = []
    hi_i = lo_i = 0
    direction = 0
    for i in range(1, len(s)):
        if s[i] > s[hi_i]:
            hi_i = i
        if s[i] < s[lo_i]:
            lo_i = i
        if direction <= 0 and s[i] > s[lo_i] + SHIFT_MIN_DEG:
            out.append((lo_i, 1))
            direction, hi_i = 1, i
        elif direction >= 0 and s[i] < s[hi_i] - SHIFT_MIN_DEG:
            out.append((hi_i, -1))
            direction, lo_i = -1, i
    # Leave a second after each onset in the clip.
    n = len(lean)
    return [(f, d) for f, d in out if f < n - RATE]


def bake(row):
    trial = row["trial"]
    subject = trial.split("_")[0]
    skel = cmu.Skeleton(os.path.join(RAW, f"{subject}.asf"))
    frames = cmu.read_amc(os.path.join(RAW, f"{trial}.amc"), skel)
    hz = 60.0 if subject == "77" else 120.0
    dec = 4
    frames = frames[::dec]
    hz /= dec
    J = cmu.joint_rotations(skel, frames)
    D = cmu.deltas(J, hz, LOWPASS_S, HIGHPASS_S)
    start, end = float(row["start_s"]), float(row["end_s"])
    end = min(end, (len(frames) - 2) / hz)
    qs = {j: resample(D[j], hz, start, end) for j in D}
    arms = row["arms"] == "1"
    chans = []
    for name, limit in JOINTS:
        v = cmu.quat_rotvec(qs[name])
        if name in ARMS and not arms:
            v = np.zeros_like(v)
        chans.append(soft(v, limit))
    # The gaze: the head's facing after the neck's and head's turns (yaw left/right, pitch up).
    g = cmu.quat_mul(qs["neck"], qs["head"])
    f = rotate(g, np.array([1.0, 0.0, 0.0]))
    pitch = np.degrees(np.arcsin(np.clip(f[:, 2], -1, 1)))
    yaw = GAZE_LIMITS[0] * np.tanh(np.degrees(np.arctan2(f[:, 1], f[:, 0])) / GAZE_LIMITS[0])
    pitch = GAZE_LIMITS[1] * np.tanh(pitch / GAZE_LIMITS[1])
    n = len(yaw)
    data = np.zeros((n, len(JOINTS) * 3 + 2))
    for k, v in enumerate(chans):
        data[:, 3 * k:3 * k + 3] = np.degrees(v)
    data[:, -2] = yaw
    data[:, -1] = pitch
    # Onsets from the baked (softened) trunk.
    qb = {}
    from scipy.spatial.transform import Rotation
    for k, (name, _) in enumerate(JOINTS[:3]):
        qq = Rotation.from_rotvec(chans[k]).as_quat()
        qb[name] = qq
    lean = lean_signal(qb, 0)
    shifts = sorted([(f, d, 0) for f, d in onsets(lean)] + [(f, d, 1) for f, d in onsets(lean_signal(qb, 1))])
    return {"label": row["label"], "trial": trial, "kind": row["kind"], "arms": arms, "data": data, "onsets": shifts, "lean": lean,
            "notes": row["notes"]}


def main():
    rows = [r for r in csv.DictReader(l for l in open(os.path.join(ROOT, "Tools", "crew", "clips.csv")) if not l.startswith("#"))]
    clips = [bake(r) for r in rows]
    lines = ["// Generated by Tools/crew/bake_idles.py from CMU Graphics Lab motion capture (mocap.cs.cmu.edu; Tools/crew/clips.csv).",
             "// Do not edit: rebake. Values are hundredths of a degree; each frame is the joints' rotation vectors (character",
             "// frame) in CrewClipJointNames order, then the gaze's yaw and pitch.",
             f"static constexpr float CrewClipRate = {RATE:.1f}f;",
             f"static constexpr int32 CrewClipJointCount = {len(JOINTS)};",
             f"static constexpr int32 CrewClipChannels = {len(JOINTS) * 3 + 2};",
             "static const TCHAR* const CrewClipJointNames[] = { " + ", ".join(f'TEXT("{n}")' for n, _ in JOINTS) + " };",
             "static constexpr float CrewClipLimitDeg[] = { " + ", ".join(f"{l:.1f}f" for _, l in JOINTS) + " };",
             f"static constexpr float CrewClipGazeLimitDeg[] = {{ {GAZE_LIMITS[0]:.1f}f, {GAZE_LIMITS[1]:.1f}f }};",
             ""]
    offset = 0
    onset_off = 0
    table, onset_rows, values = [], [], []
    for c in clips:
        n = len(c["data"])
        kind = "ECrewClipKind::Seated" if c["kind"] == "seated" else "ECrewClipKind::Standing"
        table.append(f'\t{{ TEXT("{c["label"]}"), TEXT("{c["trial"]}"), {kind}, {"true" if c["arms"] else "false"}, {n}, {offset}, '
                     f'{onset_off}, {len(c["onsets"])} }},')
        for f, d, a in c["onsets"]:
            onset_rows.append(f"{{ {f}, {d}, {a} }}")
        onset_off += len(c["onsets"])
        offset += n * c["data"].shape[1]
        vals = np.round(c["data"] * 100).astype(int)
        values.append(f"\t// {c['label']}: {c['trial']}, {n / RATE:.1f} s, {c['notes']}")
        for row in vals:
            values.append("\t" + ",".join(str(v) for v in row) + ",")
        print(f"{c['label']:8s} {c['trial']:7s} {n / RATE:5.1f} s  onsets {len(c['onsets']):2d}  "
              f"lean {c['lean'].min():4.1f}..{c['lean'].max():4.1f}  max trunk {np.abs(c['data'][:, 3:9]).max():4.1f} deg  max gaze yaw {np.abs(c['data'][:, -2]).max():4.1f}")
    lines.append("static const FCrewClipInfo CrewClipTable[] = {")
    lines += table
    lines.append("};")
    lines.append("static const FCrewClipOnset CrewClipOnsets[] = { " + ", ".join(onset_rows) + " };")
    lines.append("static const int16 CrewClipValues[] = {")
    lines += values
    lines.append("};")
    with open(OUT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{OUT}: {len(clips)} clips, {offset} values")


if __name__ == "__main__":
    main()
