"""Script-built sailing sounds for the sailing-sim pack.

Loops are generated so the last sample flows into the first (circular FFT noise,
periodic modulators, events wrapped round the loop end), so loop points are the
whole file. One-shots are peak-normalised to -1 dBFS, loops to -20 dBFS RMS.
Usage: python3 synth.py OUTDIR
"""
import sys, os, wave, json
import numpy as np

SR = 48000
rng = np.random.default_rng(22)  # J/22
OUT = sys.argv[1]
MANIFEST = []

def write(rel, x, kind, use, loop=False):
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean() if loop else x
    if loop:
        # tame transient-heavy loops (flogging, ratchets) so every loop sits near -20 dBFS RMS
        x = x / (np.max(np.abs(x)) + 1e-12)
        drive = 1.0
        while 20*np.log10(np.max(np.abs(np.tanh(drive*x))) / np.sqrt(np.mean(np.tanh(drive*x)**2))) > 15 and drive < 12:
            drive *= 1.25
        if drive > 1.0:
            x = np.tanh(drive*x)
        rms = np.sqrt(np.mean(x**2)) + 1e-12
        x = x * (10**(-20/20) / rms)
        pk = np.max(np.abs(x))
        if pk > 10**(-1/20):
            x = x * (10**(-1/20) / pk)
    else:
        x = x * (10**(-1/20) / (np.max(np.abs(x)) + 1e-12))
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    MANIFEST.append(dict(file=rel, kind=kind, use=use, loop=loop, seconds=round(len(x)/SR, 3),
                         loop_start=0 if loop else None, loop_end=len(x) if loop else None))

def freqs(n):
    return np.fft.rfftfreq(n, 1/SR)

def shaped(n, mag):
    """Periodic noise of length n with magnitude response mag(f)."""
    X = np.fft.rfft(rng.standard_normal(n))
    f = freqs(n)
    y = np.fft.irfft(X * mag(f), n)
    return y / (np.std(y) + 1e-12)

def band(lo, hi, slope=4):
    def m(f):
        f = np.maximum(f, 1e-3)
        return 1/np.sqrt(1+(lo/f)**(2*slope)) / np.sqrt(1+(f/hi)**(2*slope))
    return m

def pinkish(alpha=1.0):
    return lambda f: 1/np.maximum(f, 20)**(alpha/2)

def lfo(n, max_hz, lo=0.0, hi=1.0):
    """Smooth periodic random modulator scaled to [lo, hi]."""
    y = shaped(n, lambda f: (f > 0) * (f <= max_hz) * 1.0)
    y = (y - y.min()) / (y.max() - y.min() + 1e-12)
    return lo + (hi - lo) * y

def wrap_add(buf, ev, pos):
    n = len(buf); idx = (np.arange(len(ev)) + pos) % n
    np.add.at(buf, idx, ev)

def env(n, a, d):
    t = np.arange(n)/SR
    e = np.minimum(1, t/max(a, 1e-4)) * np.exp(-t/d)
    return e

def modal(dur, modes, exc_len=0.003, exc_band=(200, 8000)):
    """Struck resonant body: modes = [(freq, decay_s, gain)]."""
    n = int(dur*SR); t = np.arange(n)/SR
    y = np.zeros(n)
    for f, d, g in modes:
        y += g * np.sin(2*np.pi*f*t + rng.uniform(0, 6.28)) * np.exp(-t/d)
    m = int(exc_len*SR)
    exc = np.zeros(n); exc[:m] = rng.standard_normal(m) * np.hanning(m)
    exc = np.fft.irfft(np.fft.rfft(exc) * band(*exc_band)(freqs(n)), n)
    return y * env(n, 0.0005, dur) + 0.6*exc/ (np.max(np.abs(exc))+1e-12) * np.max(np.abs(y))

def fade(x, fi=0.002, fo=0.05):
    n = len(x); a = int(fi*SR); b = int(fo*SR)
    x = x.copy(); x[:a] *= np.linspace(0, 1, a); x[n-b:] *= np.linspace(1, 0, b)
    return x

# ---------------------------------------------------------------- wind in rigging
def wind(seconds, cutoff, gust_amt, whistle_amt, wire_hz, name, use):
    n = int(seconds*SR)
    gust = lfo(n, 0.25, 1-gust_amt, 1.0)
    flutter = lfo(n, 3.0, 0.85, 1.0)
    body = shaped(n, lambda f: pinkish(1.3)(f) * band(30, cutoff, 2)(f)) * gust * flutter
    whist = np.zeros(n)
    for k, (f0, g) in enumerate(wire_hz):
        tone = shaped(n, lambda f, f0=f0: np.exp(-0.5*((f-f0)/(f0*0.012))**2))
        whist += g * tone * lfo(n, 0.4, 0, 1)**2 * gust**3
    write(f'Wind/{name}.wav', body + whistle_amt*whist, 'loop', use, loop=True)

wind(20, 700, 0.5, 0.8, [(310, 1.0), (465, 0.5), (620, 0.3)], 'wind_rigging_light_loop',
     'Apparent wind 5-10 kn: soft wind with faint shroud hum')
wind(20, 1400, 0.6, 1.4, [(420, 1.0), (640, 0.7), (850, 0.4), (1270, 0.2)], 'wind_rigging_moderate_loop',
     'Apparent wind 10-18 kn: steady wind, audible shroud and stay whistle')
wind(20, 3000, 0.7, 1.8, [(560, 1.0), (840, 0.8), (1130, 0.6), (1700, 0.35), (2250, 0.2)], 'wind_rigging_strong_loop',
     'Apparent wind 18 kn+: gusty roar with singing rigging')

# ---------------------------------------------------------------- halyard slap
for i in range(6):
    base = rng.uniform(260, 420)
    modes = [(base*r*rng.uniform(0.98, 1.02), d, g) for r, d, g in
             [(1, 0.9, 1.0), (2.76, 0.6, 0.6), (5.40, 0.35, 0.4), (8.93, 0.2, 0.25), (13.3, 0.12, 0.15)]]
    modes += [(rng.uniform(1800, 3400), 0.08, 0.3)]
    y = modal(1.6, modes, exc_len=0.004)
    thwack = shaped(int(0.06*SR), band(150, 2500)) * env(int(0.06*SR), 0.0005, 0.012)
    y[:len(thwack)] += 0.8*thwack*np.max(np.abs(y))
    write(f'Rigging/halyard_slap_{i+1:02d}.wav', fade(y, 0.0005, 0.2), 'one-shot',
          'Halyard or wire slapping an aluminium mast (randomise, pitch +-5%)')

def marina_slaps(seconds):
    n = int(seconds*SR); buf = np.zeros(n)
    t = 0.0
    while t < seconds:
        t += rng.exponential(0.7)
        base = rng.choice([280, 330, 370, 410, 455]) * rng.uniform(0.97, 1.03)
        modes = [(base*r, d, g) for r, d, g in [(1, 1.0, 1), (2.76, 0.6, 0.5), (5.4, 0.3, 0.3)]]
        ev = modal(1.4, modes) * rng.uniform(0.1, 1.0)
        ev = np.fft.irfft(np.fft.rfft(ev) * band(150, 2500, 2)(freqs(len(ev))), len(ev))  # distance
        wrap_add(buf, ev, int(t*SR) % n)
    bed = shaped(n, lambda f: pinkish(1.4)(f)*band(40, 900, 2)(f)) * lfo(n, 0.2, 0.5, 1) * 0.05
    write('Rigging/marina_halyards_distant_loop.wav', buf/np.max(np.abs(buf)) + bed, 'loop',
          'Marina ambience: many masts tinkling in the breeze (layer under marina bed)', loop=True)
marina_slaps(24)

# ---------------------------------------------------------------- sail luff / flog
def sail(seconds, rate, rate_jit, crack, name, use, bright):
    n = int(seconds*SR); buf = np.zeros(n)
    cycles = int(seconds*rate)
    period = n / cycles
    for c in range(cycles):
        p = int(c*period + rng.uniform(-rate_jit, rate_jit)*period)
        L = int(period*1.2)
        a = rng.uniform(0.6, 1.0)
        ev = shaped(L, lambda f: band(120, bright, 2)(f)) * env(L, 0.002, period/SR*0.25) * a
        if crack and rng.random() < crack:
            m = int(0.02*SR)
            ev[:m] += 3*rng.standard_normal(m)*np.exp(-np.arange(m)/(0.002*SR))
        wrap_add(buf, ev, p % n)
    buf *= lfo(n, 0.3, 0.6, 1.0)
    write(f'Sails/{name}.wav', buf, 'loop', use, loop=True)

sail(12, 4.5, 0.1, 0.0, 'sail_luff_light_loop', 'Luffing sail, light air or slightly pinched (blend with trim error)', 2500)
sail(12, 7.0, 0.15, 0.25, 'sail_luff_moderate_loop', 'Luffing sail in 10-15 kn, head to wind or eased too far', 4000)
sail(12, 11.0, 0.2, 0.6, 'sail_flog_strong_loop', 'Violent flogging: tacking through the wind or sheet let fly in a breeze', 7000)

for i in range(3):
    L = int(0.35*SR)
    y = shaped(L, band(100, 6000, 2)) * env(L, 0.001, 0.05)
    m = int(0.015*SR); y[:m] += 4*rng.standard_normal(m)*np.exp(-np.arange(m)/(0.0015*SR))
    write(f'Sails/sail_fill_snap_{i+1:02d}.wav', fade(y, 0.0003, 0.1), 'one-shot',
          'Sail filling with a snap after a tack or gybe')

# ---------------------------------------------------------------- winch
def click(var):
    modes = [(rng.uniform(2200, 2800)*var, 0.012, 1), (rng.uniform(4800, 5600)*var, 0.008, 0.6),
             (rng.uniform(7800, 9000)*var, 0.005, 0.4), (rng.uniform(900, 1200)*var, 0.02, 0.3)]
    return modal(0.08, modes, exc_len=0.0008, exc_band=(1500, 15000))

for i in range(4):
    write(f'Winch/winch_click_{i+1:02d}.wav', fade(click(rng.uniform(0.9, 1.1)), 0.0002, 0.01), 'one-shot',
          'Single winch pawl click')

def ratchet(seconds, rate, name, use):
    n = int(seconds*SR); buf = np.zeros(n)
    k = int(seconds*rate); per = n/k
    drum = shaped(n, band(150, 900, 2)) * 0.03
    for j in range(k):
        c = click(1.0) * rng.uniform(0.7, 1.0)
        wrap_add(buf, c, int(j*per + rng.uniform(-0.05, 0.05)*per) % n)
    write(f'Winch/{name}.wav', buf + drum, 'loop', use, loop=True)
ratchet(4, 14, 'winch_ratchet_tailing_loop', 'Winch turning while tailing a sheet (pitch/rate up with speed)')
ratchet(4, 6, 'winch_ratchet_slow_loop', 'Winch turned slowly with a handle under load')

# ---------------------------------------------------------------- sheets and blocks
def rope_run(seconds, speed, loop, name, use):
    n = int(seconds*SR)
    fr = shaped(n, band(800, 6000*speed, 2)) * lfo(n, 8, 0.4, 1.0)
    ticks = np.zeros(n); k = int(seconds*30*speed); per = n/max(k, 1)
    for j in range(k):
        ev = modal(0.03, [(rng.uniform(1500, 2500), 0.006, 1)], exc_len=0.0005)
        wrap_add(ticks, ev*0.3, int(j*per) % n)
    y = fr + ticks*3
    if not loop:
        y *= np.concatenate([np.linspace(0, 1, int(0.05*SR)), np.ones(n-int(0.45*SR)), np.linspace(1, 0, int(0.4*SR))])
    write(f'Rigging/{name}.wav', y, 'loop' if loop else 'one-shot', use, loop=loop)
rope_run(1.6, 1.0, False, 'sheet_ease_through_block_01', 'Sheet eased quickly through a block')
rope_run(2.4, 0.6, False, 'sheet_ease_through_block_02', 'Sheet eased slowly through a block')
rope_run(6, 1.0, True, 'sheet_running_block_loop', 'Sheet running continuously through a block (gybe, letting fly)')

# ---------------------------------------------------------------- water
def bubbles(n, rate, fmin, fmax, amp=1.0):
    buf = np.zeros(n); count = int(n/SR*rate)
    for _ in range(count):
        f0 = np.exp(rng.uniform(np.log(fmin), np.log(fmax)))
        d = 0.6/f0*rng.uniform(4, 12)
        L = int(min(d*5, 0.2)*SR)+16; t = np.arange(L)/SR
        ev = np.sin(2*np.pi*f0*(t + 0.5*1.2*t*t/d)) * np.exp(-t/d) * rng.uniform(0.2, 1)*amp
        wrap_add(buf, ev, rng.integers(0, n))
    return buf

def hull(seconds, kn, name):
    n = int(seconds*SR)
    s = kn/6.0
    swell = lfo(n, 0.35+0.1*s, 0.4, 1.0)
    rush = shaped(n, lambda f: pinkish(0.8)(f)*band(60, 1500+2500*s, 2)(f)) * swell
    hiss = shaped(n, band(1500, 9000, 2)) * swell**2 * 0.4*s
    bub = bubbles(n, 150+500*s, 400, 4000)
    bub = bub/ (np.std(bub)+1e-12) * 0.35
    write(f'Water/{name}.wav', rush + hiss + bub*swell, 'loop',
          f'Hull wash / bow wave at about {kn} kn boat speed (crossfade between speeds)', loop=True)
for kn in (1, 3, 5, 7):
    hull(16, kn, f'hull_wash_{kn}kn_loop')

def lap(seconds, name, use, density):
    n = int(seconds*SR); buf = np.zeros(n); t = 0.0
    while t < seconds:
        t += rng.exponential(1.0/density)
        L = int(0.5*SR)
        thunk = shaped(L, band(60, 400, 2)) * env(L, 0.01, 0.08)
        sl = bubbles(L, 120, 300, 2500) * np.exp(-np.arange(L)/(0.15*SR))
        ev = (thunk + 0.6*sl/(np.std(sl)+1e-12)) * rng.uniform(0.3, 1)
        wrap_add(buf, ev, int(t*SR) % n)
    bed = shaped(n, lambda f: pinkish(1)(f)*band(80, 2500, 2)(f))*0.15
    write(f'Water/{name}.wav', buf/np.std(buf) + bed, 'loop', use, loop=True)
lap(20, 'water_lapping_hull_calm_loop', 'Boat at rest or in the slip: small wavelets lapping the hull', 1.6)
lap(20, 'water_lapping_hull_choppy_loop', 'Drifting or hove-to in chop: frequent slaps under the bow', 4.0)
lap(20, 'water_lapping_dock_loop', 'Water lapping pilings and the dock at Rush Creek', 2.5)

# ---------------------------------------------------------------- dock / boat creaks
for i in range(5):
    dur = rng.uniform(0.5, 1.3); n = int(dur*SR)
    rate = np.linspace(rng.uniform(25, 45), rng.uniform(50, 110), n)
    ph = np.cumsum(rate/SR)
    imp = np.zeros(n); idx = np.nonzero(np.diff(np.floor(ph)))[0]
    imp[idx] = rng.uniform(0.5, 1, len(idx))
    body = np.zeros(n); t = np.arange(int(0.05*SR))/SR
    k = sum(np.sin(2*np.pi*f*t)*np.exp(-t/0.008) for f in rng.uniform(250, 1400, 4))
    y = np.convolve(imp, k)[:n] * np.hanning(n)**0.5
    write(f'Dock/dock_creak_{i+1:02d}.wav', fade(y, 0.01, 0.05), 'one-shot',
          'Dock line or wooden dock creaking as the boat surges in the slip')

for i in range(3):
    n = int(rng.uniform(0.4, 0.9)*SR)
    y = shaped(n, band(400, 3000, 2)) * np.sin(np.linspace(0, np.pi, n))**2
    y *= 1 + 0.8*np.sin(2*np.pi*np.cumsum(np.linspace(18, 40, n))/SR)
    write(f'Dock/fender_squeak_{i+1:02d}.wav', fade(y), 'one-shot', 'Fender squeezed between hull and dock')

# ---------------------------------------------------------------- outboard (2-stroke)
def outboard(seconds, rpm, name, use, load):
    n = int(seconds*SR); fire = rpm/60.0
    k = int(round(seconds*fire)); per = n/k
    buf = np.zeros(n)
    pulse_len = int(per*1.5)
    for j in range(k):
        ev = shaped(pulse_len, band(60, 1200+2000*load, 2)) * env(pulse_len, 0.0008, per/SR*0.3)
        ev *= rng.uniform(0.75, 1.0) * (0.3 if rng.random() < 0.04*(1-load) else 1)  # idle misfire
        wrap_add(buf, ev, int(j*per + rng.uniform(-0.04, 0.04)*per) % n)
    whine = shaped(n, lambda f: np.exp(-0.5*((f-fire*6)/(fire*0.3))**2)) * 0.15*load
    gurgle = bubbles(n, 300, 150, 900); gurgle = gurgle/(np.std(gurgle)+1e-12)*0.25
    write(f'Engines/{name}.wav', buf/np.std(buf) + whine + gurgle, 'loop', use, loop=True)
outboard(8, 900, 'outboard_idle_loop', 'Small 2-stroke outboard idling in neutral (instructor or club launch)', 0.1)
outboard(8, 2400, 'outboard_lowspeed_loop', 'Outboard in gear at low speed, motoring out of the slip', 0.5)
outboard(8, 5000, 'outboard_running_loop', 'Outboard near full throttle (passing ski boats and launches)', 1.0)

json.dump(MANIFEST, open(os.path.join(OUT, 'synth_manifest.json'), 'w'), indent=1)
print(len(MANIFEST), 'files')
