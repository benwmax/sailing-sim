"""The Lagoon 42 rebuild's main lines in the drone photo's pixels, through its solved camera (docs/lagoon42-4).

    python3 -I photo_lines_lagoon42.py <out.json> [<out.svg>]

Projects the drawing's lines (both hulls' sheers, the hatches, the window band's bottom and top, the roof's top, edge
and underside, the trampolines' aft edge, the crossbeam and the mast's foot) through match_two_canoes.camera.json and
writes them as {name: [[x px, y px], ...]} in the photo's 1024 x 768 frame. The .svg is the same lines on a clear
canvas of that size, to lay over the photo in any viewer. The photo itself is never needed or stored: only the lines
are written. Pure geometry, no Blender, no numpy.

Frame: the game's body frame (X forward, Y starboard, Z up, metres); the camera json is in Blender's (Y to port).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridgedeck_lagoon42 as B  # noqa: E402
import hull_lagoon42 as H  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402

COLOURS = {"sheer": "#ff3030", "hatch": "#ffffff", "win": "#00e0ff", "roof": "#30ff30", "nose": "#ffd000",
           "cross": "#ffd000", "mast": "#ff00ff"}


def camera(path=os.path.join(HERE, "match_two_canoes.camera.json")):
    """(R, C, f, (W, H)): the rotation (camera to Blender), the camera's place in Blender's frame, the focal length in
    pixels and the photo's size."""
    c = json.load(open(path))
    w, x, y, z = c["rotation_quaternion"]
    R = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    W, Hh = c["resolution"]
    return R, c["location"], c["lens_mm"] / c["sensor_width_mm"] * W, (W, Hh)


def project(cam, p):
    """A game-frame point to the photo's pixel (x right, y down)."""
    R, C, f, (W, Hh) = cam
    b = (p[0] - C[0], -p[1] - C[1], p[2] - C[2])
    cx, cy, cz = (sum(R[i][j] * b[i] for i in range(3)) for j in range(3))   # camera frame: -z ahead
    return (W / 2 + f * cx / -cz, Hh / 2 - f * cy / -cz)


def lines():
    H.solve_depth()
    L = {}
    xs = [-5.56 + (6.39 + 5.56) * k / 39 for k in range(40)]
    for side, nm in ((1, "S"), (-1, "P")):
        L["sheer_out" + nm] = [(x, side * (H.HULL_Y + H.half_beam(x)), H.sheer_z(x)) for x in xs]
        L["sheer_in" + nm] = [(x, side * (H.HULL_Y - H.half_beam(x)), H.sheer_z(x)) for x in xs
                              if x > S.SAL["corner"][0] - 0.1]
        for k, (x0, x1, y0, y1, z0, z1) in enumerate(S.hatches(side * H.HULL_Y)):
            L["hatch%s%d" % (nm, k)] = [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1)]
    rows, _ = S.wall_rows()
    L["win_bottom"] = rows[1] + [rows[1][0]]
    L["win_top"] = rows[2] + [rows[2][0]]
    rr = S.roof_rings()
    n_top = 10                                      # roof_rings: 10 rings on the top, 11 over the edge, 13 under
    for name, k in (("roof_top", n_top - 1), ("roof_edge", n_top + 5), ("roof_under", n_top + 10)):
        L[name] = rr[k] + [rr[k][0]]
    L["nose"] = [(B.nose_x(v, True), v * B.deck_span(B.nose_x(v, True)), B.nose_top_z(v))
                 for v in (-1 + 2 * k / 14 for k in range(15))]
    L["crossbeam"] = [(B.CB["x"], -2.5 + k * 1.25, H.sheer_z(B.CB["x"]) - 0.14) for k in range(5)]
    mx, my, mz = S.SD["measured"]["mast_foot"]
    L["mast"] = [(mx, my, mz), (mx, my, mz + 3.0)]
    return L


def main(out_json, out_svg=None):
    cam = camera()
    px = {k: [[round(c, 1) for c in project(cam, p)] for p in v] for k, v in lines().items()}
    json.dump({"about": "The Lagoon 42 rebuild's lines in the drone photo's pixels (photo_lines_lagoon42.py; "
                        "match_two_canoes.camera.json). No photo data.", "size": list(cam[3]), "lines": px},
              open(out_json, "w"), indent=0)
    if out_svg:
        W, Hh = cam[3]
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (W, Hh)]
        for k, pts in px.items():
            c = COLOURS[next(p for p in COLOURS if k.startswith(p))]
            svg.append('<polyline fill="none" stroke="%s" stroke-width="0.8" points="%s"/>'
                       % (c, " ".join("%.1f,%.1f" % (x, y) for x, y in pts)))
        svg.append("</svg>")
        open(out_svg, "w").write("\n".join(svg))
    print(f"{len(px)} lines to {out_json}" + (f" and {out_svg}" if out_svg else ""))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
