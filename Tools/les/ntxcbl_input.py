"""Water W6 LES pilot: initial profiles and geostrophic wind for ntxcbl.ini (MicroHH input netCDF).
A well-mixed layer to 1.5 km at 306 K (a hot North Texas afternoon's potential temperature), a 1.5 K inversion over 100 m,
then 4 K/km; the wind starts at its geostrophic value, 13 kn (6.7 m/s) from the south, at every height."""
import netCDF4 as nc
import numpy as np

kmax, zsize = 120, 3000.0
with open("ntxcbl.ini") as f:
    for line in f:
        k, _, v = line.partition("=")
        if k.strip() == "ktot":
            kmax = int(v)
        if k.strip() == "zsize":
            zsize = float(v)
dz = zsize / kmax
z = np.linspace(0.5 * dz, zsize - 0.5 * dz, kmax)

h, dth, dthz, gamma, th0 = 1500.0, 1.5, 100.0, 0.004, 306.0
th = np.where(z <= h - 0.5 * dthz, th0,
              np.where(z <= h + 0.5 * dthz, th0 + dth / dthz * (z - (h - 0.5 * dthz)), th0 + dth + gamma * (z - (h + 0.5 * dthz))))
ug = np.zeros(kmax)
vg = np.full(kmax, 13.0 * 0.514444)     # from the south: blowing toward +y (north)

f = nc.Dataset("ntxcbl_input.nc", mode="w", datamodel="NETCDF4", clobber=True)
f.createDimension("z", kmax)
f.createVariable("z", "f8", ("z",))[:] = z
g = f.createGroup("init")
for name, data in (("u", ug), ("v", vg), ("th", th), ("u_geo", ug), ("v_geo", vg)):
    g.createVariable(name, "f8", ("z",))[:] = data
f.close()
print(f"ntxcbl_input.nc: {kmax} levels of {dz:.1f} m, mixed layer {h:.0f} m at {th0} K, wind {vg[0]:.2f} m/s from the south")
