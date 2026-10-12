"""Harmonic tide and tidal-current prediction (Schureman / Doodson), the way NOAA's tables are made.

Height(t) = Z0 + sum f_i A_i cos(V_i(t) + u_i(t) - kappa_i), with kappa the Greenwich phase NOAA publishes,
V the equilibrium argument computed directly from the astronomical longitudes at t, and f, u the nodal factors.
"""
import datetime as dt
import math

# Doodson-style multipliers of (T, s, h, p, N', p1) and a phase offset in degrees, where T is the hour angle of the
# mean sun at Greenwich (180 + 15 * UT hours). Nodal group says which f, u formula applies.
CONSTITUENTS = {
    "M2": ((2, -2, 2, 0, 0, 0), 0, "M2"), "S2": ((2, 0, 0, 0, 0, 0), 0, None), "N2": ((2, -3, 2, 1, 0, 0), 0, "M2"),
    "K1": ((1, 0, 1, 0, 0, 0), -90, "K1"), "M4": ((4, -4, 4, 0, 0, 0), 0, "M2^2"), "O1": ((1, -2, 1, 0, 0, 0), 90, "O1"),
    "M6": ((6, -6, 6, 0, 0, 0), 0, "M2^3"), "MK3": ((3, -2, 3, 0, 0, 0), -90, "M2K1"), "S4": ((4, 0, 0, 0, 0, 0), 0, None),
    "MN4": ((4, -5, 4, 1, 0, 0), 0, "M2^2"), "NU2": ((2, -3, 4, -1, 0, 0), 0, "M2"), "S6": ((6, 0, 0, 0, 0, 0), 0, None),
    "MU2": ((2, -4, 4, 0, 0, 0), 0, "M2"), "2N2": ((2, -4, 2, 2, 0, 0), 0, "M2"), "OO1": ((1, 2, 1, 0, 0, 0), -90, "OO1"),
    "LAM2": ((2, -1, 0, 1, 0, 0), 180, "M2"), "S1": ((1, 0, 0, 0, 0, 0), 0, None), "M1": ((1, -1, 1, 1, 0, 0), -90, "M1"),
    "J1": ((1, 1, 1, -1, 0, 0), -90, "J1"), "MM": ((0, 1, 0, -1, 0, 0), 0, "Mm"), "SSA": ((0, 0, 2, 0, 0, 0), 0, None),
    "SA": ((0, 0, 1, 0, 0, 0), 0, None), "MSF": ((0, 2, -2, 0, 0, 0), 0, "MSf"), "MF": ((0, 2, 0, 0, 0, 0), 0, "Mf"),
    "RHO": ((1, -3, 3, -1, 0, 0), 90, "O1"), "Q1": ((1, -3, 1, 1, 0, 0), 90, "O1"), "T2": ((2, 0, -1, 0, 0, 1), 0, None),
    "R2": ((2, 0, 1, 0, 0, -1), 180, None), "2Q1": ((1, -4, 1, 2, 0, 0), 90, "O1"), "P1": ((1, 0, -1, 0, 0, 0), 90, None),
    "2SM2": ((2, 2, -2, 0, 0, 0), 0, "MSf"), "M3": ((3, -3, 3, 0, 0, 0), 0, "M3"), "L2": ((2, -1, 2, -1, 0, 0), 180, "M2"),
    "2MK3": ((3, -4, 3, 0, 0, 0), 90, "2MK3"), "K2": ((2, 0, 2, 0, 0, 0), 0, "K2"), "M8": ((8, -8, 8, 0, 0, 0), 0, "M2^4"),
    "MS4": ((4, -2, 2, 0, 0, 0), 0, "M2"),
}


def astro(t):
    """Mean longitudes (degrees) at a UTC datetime: T (solar hour angle), s, h, p, N, p1."""
    j2000 = dt.datetime(2000, 1, 1, 12, tzinfo=dt.timezone.utc)
    d = (t - j2000).total_seconds() / 86400.0
    c = d / 36525.0
    s = 218.3164477 + 481267.88123421 * c
    h = 280.4664567 + 36000.7697489 * c
    p = 83.3532465 + 4069.0137287 * c
    n = 125.0445479 - 1934.1362891 * c
    p1 = 282.9373 + 1.71946 * c
    ut = t.hour + t.minute / 60.0 + t.second / 3600.0
    T = 180.0 + 15.0 * ut
    return T, s, h, p, n, p1


def nodal(group, n_deg):
    n = math.radians(n_deg)
    c, s2 = math.cos, math.sin
    fm2 = 1.0004 - 0.0373 * c(n) + 0.0002 * c(2 * n); um2 = -2.14 * s2(n)
    fk1 = 1.0060 + 0.1150 * c(n) - 0.0088 * c(2 * n) + 0.0006 * c(3 * n); uk1 = -8.86 * s2(n) + 0.68 * s2(2 * n) - 0.07 * s2(3 * n)
    fo1 = 1.0089 + 0.1871 * c(n) - 0.0147 * c(2 * n) + 0.0014 * c(3 * n); uo1 = 10.80 * s2(n) - 1.34 * s2(2 * n) + 0.19 * s2(3 * n)
    table = {
        None: (1.0, 0.0), "M2": (fm2, um2), "K1": (fk1, uk1), "O1": (fo1, uo1),
        "K2": (1.0241 + 0.2863 * c(n) + 0.0083 * c(2 * n) - 0.0015 * c(3 * n), -17.74 * s2(n) + 0.68 * s2(2 * n) - 0.04 * s2(3 * n)),
        "J1": (1.1029 + 0.1676 * c(n) - 0.0170 * c(2 * n) + 0.0016 * c(3 * n), -12.94 * s2(n) + 1.34 * s2(2 * n) - 0.19 * s2(3 * n)),
        "OO1": (1.1027 + 0.6504 * c(n) + 0.0317 * c(2 * n) - 0.0014 * c(3 * n), -36.68 * s2(n) + 4.02 * s2(2 * n) - 0.57 * s2(3 * n)),
        "M1": (fo1, uo1), "Mm": (1.0 - 0.1300 * c(n) + 0.0013 * c(2 * n), 0.0),
        "Mf": (1.0429 + 0.4135 * c(n) - 0.004 * c(2 * n), -23.74 * s2(n) + 2.68 * s2(2 * n) - 0.38 * s2(3 * n)),
        "MSf": (fm2, -um2), "M2^2": (fm2 ** 2, 2 * um2), "M2^3": (fm2 ** 3, 3 * um2), "M2^4": (fm2 ** 4, 4 * um2),
        "M2K1": (fm2 * fk1, um2 + uk1), "2MK3": (fm2 ** 2 * fk1, 2 * um2 - uk1), "M3": (fm2 ** 1.5, 1.5 * um2),
    }
    return table[group]


def predict(constituents, z0, t):
    """constituents: list of (name, amplitude, phase_gmt_deg)."""
    T, s, h, p, n, p1 = astro(t)
    args = (T, s, h, p, n, p1)
    total = z0
    for name, amp, kappa in constituents:
        key = name.upper()
        if key not in CONSTITUENTS or amp == 0.0:
            continue
        mult, offset, group = CONSTITUENTS[key]
        v = sum(m * a for m, a in zip(mult, args)) + offset
        f, u = nodal(group, n)
        total += f * amp * math.cos(math.radians(v + u - kappa))
    return total
