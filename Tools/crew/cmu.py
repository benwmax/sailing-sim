"""Crew C1b: reads CMU Graphics Lab motion capture (ASF skeleton, AMC motion: mocap.cs.cmu.edu) into each joint's
rotation about itself in the character frame SK_Sailor's stances use (CrewPose.h: X the way the sailor faces, Y to
their right, Z up), so a clip's motion means the same as a stance's joint rotations.

ASF/AMC: a bone's rotation in its parent is C M C^-1, C its axis (ASF "axis ... XYZ") and M the AMC degrees of freedom
(R = Rz Ry Rx); every bone's frame is the world's at rest. CMU is right-handed, Y up, and the subject faces +Z (the left
hip is +X). The character frame is left-handed (Unreal), so a rotation R becomes P R P^T with P the change of axes
(det -1): numerically the same turn of the same limb, which FQuat then reproduces from its components.
"""
import numpy as np

# CMU (x left, y up, z forward) -> character (X forward, Y right, Z up).
P = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_xyz(deg):
    x, y, z = np.radians(deg)
    return rz(z) @ ry(y) @ rx(x)


class Skeleton:
    def __init__(self, path):
        self.axis = {}      # bone -> C
        self.dof = {}       # bone -> ['rx', ...]
        self.direction = {}
        self.length = {}
        self.parent = {}
        self.root_order = []
        self.root_axis = np.eye(3)
        section = None
        cur = None
        hierarchy = []
        for raw in open(path):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(":"):
                section = line.split()[0]
                continue
            tok = line.split()
            if section == ":root":
                if tok[0] == "order":
                    self.root_order = [t.lower() for t in tok[1:]]
            elif section == ":bonedata":
                if tok[0] == "begin":
                    cur = {}
                elif tok[0] == "end":
                    name = cur["name"]
                    self.axis[name] = euler_xyz([float(v) for v in cur["axis"][:3]])
                    self.dof[name] = cur.get("dof", [])
                    self.direction[name] = np.array([float(v) for v in cur["direction"]])
                    self.length[name] = float(cur["length"][0])
                    cur = None
                elif cur is not None and tok[0] in ("name", "direction", "length", "axis", "dof"):
                    cur[tok[0]] = tok[1] if tok[0] == "name" else tok[1:]
            elif section == ":hierarchy":
                if tok[0] in ("begin", "end"):
                    continue
                for child in tok[1:]:
                    self.parent[child] = tok[0]


def read_amc(path, skel):
    """Frames: list of {bone: values}."""
    frames = []
    cur = None
    for raw in open(path):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(":"):
            continue
        tok = line.split()
        if len(tok) == 1 and tok[0].isdigit():
            cur = {}
            frames.append(cur)
            continue
        if cur is not None:
            cur[tok[0]] = [float(v) for v in tok[1:]]
    return frames


def local_rotation(skel, bone, values):
    """The bone's rotation about itself in its parent's (rest = world) axes, CMU coordinates."""
    if bone == "root":
        rot = {}
        for name, v in zip(skel.root_order, values):
            rot[name] = v
        return euler_xyz([rot.get("rx", 0.0), rot.get("ry", 0.0), rot.get("rz", 0.0)])
    d = {"rx": 0.0, "ry": 0.0, "rz": 0.0}
    for name, v in zip(skel.dof.get(bone, []), values):
        if name in d:
            d[name] = v
    C = skel.axis[bone]
    return C @ euler_xyz([d["rx"], d["ry"], d["rz"]]) @ C.T


def root_height(skel, frame):
    vals = frame.get("root", [0] * 6)
    return vals[skel.root_order.index("ty")] if "ty" in skel.root_order else 0.0


# SK_Sailor's joints from CMU's bones (rotations along a chain compose: the parent's first).
JOINTS = {
    "pelvis": ["root"],
    "spine": ["lowerback", "upperback"],
    "chest": ["thorax"],
    "neck": ["lowerneck", "upperneck"],
    "head": ["head"],
    "shoulder_l": ["lclavicle"],
    "shoulder_r": ["rclavicle"],
    "upperarm_l": ["lhumerus"],
    "upperarm_r": ["rhumerus"],
    "forearm_l": ["lradius"],
    "forearm_r": ["rradius"],
    "hand_l": ["lwrist", "lhand"],
    "hand_r": ["rwrist", "rhand"],
}


def joint_rotations(skel, frames):
    """{joint: array (frames, 3, 3)} in the character frame."""
    out = {}
    for joint, bones in JOINTS.items():
        mats = np.empty((len(frames), 3, 3))
        for i, f in enumerate(frames):
            R = np.eye(3)
            for b in bones:
                if b in f or b == "root":
                    R = R @ local_rotation(skel, b, f.get(b, [0.0] * 6))
            mats[i] = P @ R @ P.T
        out[joint] = mats
    return out


def to_quat(R):
    """(N,3,3) -> (N,4) x, y, z, w (FQuat's component order), w >= 0."""
    from scipy.spatial.transform import Rotation
    q = Rotation.from_matrix(R).as_quat()
    q[q[:, 3] < 0] *= -1
    return q


def rotvec(R):
    from scipy.spatial.transform import Rotation
    return Rotation.from_matrix(R).as_rotvec()


def from_rotvec(v):
    from scipy.spatial.transform import Rotation
    return Rotation.from_rotvec(v).as_matrix()


def mean_rotation(R):
    from scipy.spatial.transform import Rotation
    return Rotation.from_matrix(R).mean().as_matrix()


def quat_smooth(q, sigma):
    """Gaussian-weighted mean of unit quaternions (N,4) over sigma samples (sign-aligned to each centre), normalized."""
    n = len(q)
    if sigma <= 0:
        return q.copy()
    half = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2)
    out = np.empty_like(q)
    for i in range(n):
        a, b = max(0, i - half), min(n, i + half + 1)
        w = k[a - i + half:b - i + half]
        seg = q[a:b].copy()
        seg[(seg @ q[i]) < 0] *= -1
        m = (seg * w[:, None]).sum(0)
        out[i] = m / np.linalg.norm(m)
    return out


def quat_mul(a, b):
    ax, ay, az, aw = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bx, by, bz, bw = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], -1)


def quat_inv(a):
    return a * np.array([-1, -1, -1, 1.0])


def quat_rotvec(q):
    q = q * np.where(q[..., 3:4] < 0, -1.0, 1.0)
    s = np.linalg.norm(q[..., :3], axis=-1)
    ang = 2 * np.arctan2(s, q[..., 3])
    with np.errstate(invalid="ignore", divide="ignore"):
        f = np.where(s > 1e-9, ang / np.maximum(s, 1e-12), 2.0)
    return q[..., :3] * f[..., None]


def remove_heading(Rpelvis):
    """The pelvis without its turn about the vertical (character Z): the subject's heading is not a crew motion."""
    out = np.empty_like(Rpelvis)
    for i, R in enumerate(Rpelvis):
        f = R[:, 0]
        yaw = np.arctan2(f[1], f[0])
        c, s = np.cos(-yaw), np.sin(-yaw)
        out[i] = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ R
    return out


def deltas(J, hz, lowpass_s=0.06, highpass_s=4.0):
    """{joint: (N,4)} the motion about a slowly moving posture: R = Delta * Slow, jitter smoothed away."""
    out = {}
    for j, R in J.items():
        if j == "pelvis":
            R = remove_heading(R)
        q = to_quat(R)
        for i in range(1, len(q)):
            if q[i] @ q[i - 1] < 0:
                q[i] *= -1
        fast = quat_smooth(q, lowpass_s * hz)
        slow = quat_smooth(q, highpass_s * hz)
        d = quat_mul(fast, quat_inv(slow))
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        out[j] = d
    return out
