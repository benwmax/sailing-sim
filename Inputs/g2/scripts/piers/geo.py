"""Transverse Mercator (Kruger series, GRS80) without pyproj: UTM 15N (EPSG:26915), WGS84/NAD83 lon/lat and the sim's
Galveston local frame (+proj=tmerc +lat_0=29.5446 +lon_0=-95.0193 +k=1, NAD83). Accurate to well under a millimetre."""
import math, numpy as np
a = 6378137.0; f = 1 / 298.257222101
n = f / (2 - f)
A = a / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
AL = [n/2 - 2*n**2/3 + 5*n**3/16 + 41*n**4/180, 13*n**2/48 - 3*n**3/5 + 557*n**4/1440, 61*n**3/240 - 103*n**4/140, 49561*n**4/161280]
BE = [n/2 - 2*n**2/3 + 37*n**3/96 - n**4/360, n**2/48 + n**3/15 - 437*n**4/1440, 17*n**3/480 - 37*n**4/840, 4397*n**4/161280]
DE = [2*n - 2*n**2/3 - 2*n**3 + 116*n**4/45, 7*n**2/3 - 8*n**3/5 - 227*n**4/45, 56*n**3/15 - 136*n**4/35, 4279*n**4/630]
e2n = 2 * math.sqrt(n) / (1 + n)

def _fwd(lon, lat, lon0):
    lat = np.radians(np.asarray(lat, float)); dl = np.radians(np.asarray(lon, float) - lon0)
    t = np.sinh(np.arctanh(np.sin(lat)) - e2n * np.arctanh(e2n * np.sin(lat)))
    xi_ = np.arctan2(t, np.cos(dl)); eta_ = np.arctanh(np.sin(dl) / np.sqrt(1 + t * t))
    xi, eta = xi_.copy(), eta_.copy()
    for j, al in enumerate(AL, 1):
        xi = xi + al * np.sin(2*j*xi_) * np.cosh(2*j*eta_); eta = eta + al * np.cos(2*j*xi_) * np.sinh(2*j*eta_)
    return A * eta, A * xi

def _inv(x, y, lon0):
    xi = np.asarray(y, float) / A; eta = np.asarray(x, float) / A
    xi_, eta_ = xi.copy(), eta.copy()
    for j, be in enumerate(BE, 1):
        xi_ = xi_ - be * np.sin(2*j*xi) * np.cosh(2*j*eta); eta_ = eta_ - be * np.cos(2*j*xi) * np.sinh(2*j*eta)
    chi = np.arcsin(np.sin(xi_) / np.cosh(eta_))
    lat = chi.copy()
    for j, d in enumerate(DE, 1):
        lat = lat + d * np.sin(2*j*chi)
    lon = lon0 + np.degrees(np.arctan2(np.sinh(eta_), np.cos(xi_)))
    return lon, np.degrees(lat)

UTM_LON0, K0 = -93.0, 0.9996
def ll2utm(lon, lat):
    x, y = _fwd(lon, lat, UTM_LON0); return 500000 + K0 * x, K0 * y
def utm2ll(E, N):
    return _inv((np.asarray(E, float) - 500000) / K0, np.asarray(N, float) / K0, UTM_LON0)

LAT0, LON0 = 29.5446, -95.0193
_Y0 = float(_fwd(LON0, LAT0, LON0)[1])
def ll2local(lon, lat):
    """-> (east, north) in the sim frame (sim_east, sim_north)."""
    x, y = _fwd(lon, lat, LON0); return x, y - _Y0
def local2ll(east, north):
    return _inv(np.asarray(east, float), np.asarray(north, float) + _Y0, LON0)

def convergence_deg(lon, lat):
    """UTM grid convergence: true azimuth = grid azimuth + this."""
    E, N = ll2utm(lon, lat); E2, N2 = ll2utm(lon, lat + 1e-4)
    return -math.degrees(math.atan2(float(E2 - E), float(N2 - N)))
