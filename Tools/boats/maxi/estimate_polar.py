"""The maxi's estimated reference polar (FleetReferencePolar, EBoatType::Maxi): no published polar exists for a made-up
boat, so the fleet's two measured keelboat polars (the Catalina 30's ORC certificate US 3522 and the J/22's ORC
one-design polar) are scaled to her.

Method, per reference boat and point:
  1. Froude scaling: speeds by sqrt(LWL_maxi / LWL_ref), the wind by the same factor (the same Froude number for both).
  2. Power: the wind's dynamic pressure against the boat's weight goes as SA / volume^(2/3) (SA/D), so the reference is
     read at a wind sqrt(SA/D_maxi / SA/D_ref) stronger.
  3. Reynolds: Froude scaling keeps the friction coefficient fixed, but ITTC-57's Cf at the maxi's Reynolds number (1e8)
     is about 0.6 of a small boat's; the speed rises by (Cf_ref / Cf_maxi)^(share / 2), share being the friction's part
     of the drag at that Froude number (0.85 below Fn 0.25 down to 0.3 past 0.5).
The two scaled polars are averaged. Checked the same way from the Catalina 30 to the J/22: the scaled speeds match the
J/22's ORC polar to 4% on average (each point within 10 to 17%), so the method is good to about 15% between keelboats;
the maxi sits far outside the fleet (displacement-length 43 against 151 and 317), so the test allows 30%.

Run: python3 Tools/boats/maxi/estimate_polar.py
"""
import math

ANGLES = [52, 60, 90, 120, 150]  # 120 and 150 with the spinnaker (the references' downwind numbers are with it)
# Catalina 30 ORC certificate US 3522 (Fleet.cpp) and the J/22's ORC polar (PolarReference.cpp; spinnaker downwind).
C30 = {6: [4.51, 4.76, 4.83, 4.57, 3.61], 10: [5.8, 5.99, 6.18, 6.17, 5.38], 16: [6.33, 6.51, 6.82, 7.11, 6.7]}
J22 = {6: [4.3, 4.6, 4.9, 4.6, 3.6], 10: [5.6, 5.8, 6.1, 6.1, 5.4], 15: [6.03, 6.23, 6.75, 7.4, 6.68]}
# LWL m, sail area (main + jib) m^2, sailing displacement volume m^3 (fresh water, crew aboard).
BOATS = {"j22": (5.79, 20.7 + 9.2, 1.052), "c30": (7.62, 22.57 + 32.85, 5.027), "maxi": (29.6, 335.0 + 245.0, 40.165)}
NU = 1.14e-6  # m^2/s, kinematic viscosity of fresh water at 15 C
KNOT = 0.514444


def interp(table, tws, i):
    keys = sorted(table)
    pts = [(0.0, 0.0)] + [(k, table[k][i]) for k in keys]
    if tws >= keys[-1]:
        (a, va), (b, vb) = pts[-2], pts[-1]
        return vb + 0.3 * (vb - va) / (b - a) * (tws - b)  # past the table: speeds level off
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if a <= tws <= b:
            return va + (vb - va) * (tws - a) / (b - a)


def sad(b):
    L, S, V = BOATS[b]
    return S / V ** (2.0 / 3.0)


def cf(v_kn, L):
    return 0.075 / (math.log10(max(v_kn * KNOT * L / NU, 1e5)) - 2.0) ** 2


def friction_share(fn):
    pts = [(0.0, 0.9), (0.25, 0.85), (0.35, 0.65), (0.40, 0.5), (0.45, 0.38), (0.5, 0.3), (9.0, 0.3)]
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if a <= fn <= b:
            return va + (vb - va) * (fn - a) / (b - a)


def scaled(ref, table, to, tws, i):
    s = math.sqrt(BOATS[to][0] / BOATS[ref][0])
    q = math.sqrt(sad(to) / sad(ref))
    v_ref = interp(table, tws / s * q, i)
    v = s * v_ref
    fn = v_ref * KNOT / math.sqrt(9.81 * BOATS[ref][0])
    return v * (cf(v_ref, BOATS[ref][0]) / cf(v, BOATS[to][0])) ** (friction_share(fn) / 2.0)


def main():
    check = [interp(J22, w, i) / scaled("c30", C30, "j22", w, i) for w in (6, 10, 15) for i in range(len(ANGLES))]
    print("check, Catalina 30 -> J/22: actual / estimate mean %.3f, range %.3f-%.3f" % (sum(check) / len(check), min(check), max(check)))
    print("maxi, TWA", ANGLES)
    for w in (6, 10, 16):
        row = [0.5 * (scaled("c30", C30, "maxi", w, i) + scaled("j22", J22, "maxi", w, i)) for i in range(len(ANGLES))]
        print("%2d kn: { %s }" % (w, ", ".join("%.1f" % v for v in row)))


if __name__ == "__main__":
    main()
