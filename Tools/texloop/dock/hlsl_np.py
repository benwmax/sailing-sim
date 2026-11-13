"""Run a branch of M_WorldSurface's HLSL (scripts/make_materials.py WORLD_SURFACE_CODE) on numpy arrays, so the dock
swatches are rendered from the shader text itself, not a hand port that can drift (docs/texloop-dock).

A small translator for the subset the world patterns use: declarations (`float a = x, b = y;`), swizzles .x .y .z .rgb,
float2/float3 constructors, the intrinsics below, and `if` blocks on uniform conditions (the ramp's UV1 flag). Every
scalar is an (H, W, 1) array so it broadcasts against float3s.

    from hlsl_np import branch, run
    code = branch(world_code, 1)                 # the body of `if (Pattern > 0.5 && Pattern < 1.5) { ... }`
    out = run(code, env)                         # env: the preamble's variables; returns the namespace after the run
"""
import re
import subprocess

import numpy as np

SHAPE = [None]


def _arr(x):
    x = np.asarray(x, dtype=float)
    if x.ndim == 0:
        return np.full(tuple(SHAPE[0]) + (1,), float(x))
    return x


def F(*args):
    if all(np.ndim(a) == 0 for a in args):
        return np.array([float(a) for a in args])
    return np.concatenate([_arr(a) for a in args], -1)


def saturate(x): return np.clip(x, 0.0, 1.0)
def frac(x): return x - np.floor(x)
def lerp(a, b, t): return a + (b - a) * t
def step(a, x): return (np.asarray(x) >= np.asarray(a)).astype(float)
def smoothstep(a, b, x):
    t = saturate((np.asarray(x, float) - a) / (np.asarray(b, float) - a))
    return t * t * (3.0 - 2.0 * t)
def dot(a, b): return np.sum(np.asarray(a) * np.asarray(b), -1, keepdims=True)
def length(a): return np.sqrt(dot(a, a))
def normalize(a): return a / np.maximum(length(a), 1e-9)
def fwidth(x):
    x = np.asarray(x, float)
    return np.abs(np.gradient(x, axis=0)) + np.abs(np.gradient(x, axis=1))


NS = dict(F=F, saturate=saturate, frac=frac, lerp=lerp, step=step, smoothstep=smoothstep, dot=dot, length=length,
          normalize=normalize, fwidth=fwidth, sin=np.sin, cos=np.cos, exp=np.exp, floor=np.floor, abs=np.abs,
          sqrt=np.sqrt, sign=np.sign, atan2=np.arctan2, fmod=np.fmod, pow=lambda a, b: np.power(np.abs(a), b) * np.where((np.asarray(a) < 0) & (np.asarray(b) % 2 == 1), -1, 1),
          min=np.minimum, max=np.maximum, np=np)

DECL = re.compile(r"^(?:const\s+)?(?:float[234]?|bool|int|half[234]?)\s+")
SWZ = {"x": "[...,0:1]", "y": "[...,1:2]", "z": "[...,2:3]", "rgb": "", "xy": "[...,0:2]"}


def _split_top(s, sep=","):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _ternary(e):
    """`lhs = cond ? a : b` (one level, at the top of the expression) as np.where."""
    depth, q, col = 0, -1, -1
    for k, ch in enumerate(e):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and ch == "?" and q < 0:
            q = k
        elif depth == 0 and ch == ":" and q >= 0:
            col = k
            break
    if q < 0 or col < 0:
        return e
    m = re.match(r"^(\s*[A-Za-z_]\w*\s*(?:[-+*/]?=)(?!=))(.*)$", e[:q], re.S)
    lhs, cond = (m.group(1), m.group(2)) if m else ("", e[:q])
    return f"{lhs} np.where({cond.strip()}, {e[q + 1:col].strip()}, {e[col + 1:].strip()})"


def _expr(e):
    e = _ternary(e)
    e = re.sub(r"\bfloat[234]\s*\(", "F(", e)
    e = re.sub(r"\b([A-Za-z_]\w*)\.(rgb|xy|x|y|z)\b", lambda m: m.group(1) + SWZ[m.group(2)], e)
    e = re.sub(r"(\d)\.(?=\D|$)", r"\1.0", e)
    e = e.replace("&&", " and ").replace("||", " or ")
    return e


def translate(code):
    code = re.sub(r"//[^\n]*", "", code)
    lines, ind, cur = [], 0, ""
    pend_else = False
    for ch in code:
        if ch == ";":
            st = cur.strip(); cur = ""
            if st.startswith("return"):
                continue
            if DECL.match(st):
                st = DECL.sub("", st)
                for part in _split_top(st):
                    lines.append("    " * ind + _expr(part.strip()))
            else:
                lines.append("    " * ind + _expr(st))
        elif ch == "{":
            st = " ".join(cur.split()); cur = ""
            m = re.match(r"^(else\s+)?if\s*\((.*)\)$", st)
            if m:
                kw = "elif" if m.group(1) else "if"
                cond = " & ".join(f"({_expr(x)})" for x in m.group(2).split("&&"))
                lines.append("    " * ind + f"{kw} np.all({cond}):")
            elif st == "else":
                lines.append("    " * ind + "else:")
            else:
                raise ValueError("block: " + st)
            ind += 1
        elif ch == "}":
            if cur.strip():
                raise ValueError("dangling: " + cur)
            lines.append("    " * ind + "pass")
            ind -= 1
        else:
            cur += ch
    return "\n".join(lines)


def branch(code, opener):
    """The body (inside the braces) of the block whose opening line starts with `opener` (exact text)."""
    i = code.index(opener)
    j = code.index("{", i)
    depth, k = 0, j
    while True:
        if code[k] == "{":
            depth += 1
        elif code[k] == "}":
            depth -= 1
            if depth == 0:
                return code[j + 1:k]
        k += 1


def world_code(rev=None):
    """WORLD_SURFACE_CODE from scripts/make_materials.py, at a git revision (None: the working tree)."""
    import os
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if rev:
        src = subprocess.run(["git", "-C", repo, "show", f"{rev}:scripts/make_materials.py"], capture_output=True, text=True, check=True).stdout
    else:
        src = open(os.path.join(repo, "scripts", "make_materials.py"), encoding="utf-8").read()
    a = src.index('WORLD_SURFACE_CODE = """') + len('WORLD_SURFACE_CODE = """')
    return src[a:src.index('"""', a)]


def run(code, env):
    SHAPE[0] = env["uv"].shape[:2]
    ns = dict(NS)
    ns.update(env)
    exec(compile(translate(code), "<hlsl>", "exec"), ns)
    return ns
