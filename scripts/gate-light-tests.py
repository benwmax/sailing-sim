#!/usr/bin/env python3
"""The tests a scoped gate runs when the heavy set (gate-heavy-tests.txt) already passed on these physics inputs.

usage: gate-light-tests.py <tests-all.txt> <gate-heavy-tests.txt> <test source dir>
       gate-light-tests.py --self-test

The last full run's list (tests-all.txt) less the heavy prefixes, plus every test declared in the sources that the list
doesn't have yet: a test added since the last full run used to wait for the next one (#476's CameraAboveWater, Nov 4).
Prints the names joined by '+', the filter scripts/test.sh takes.
"""
import pathlib, re, sys, tempfile

DECL = re.compile(r'IMPLEMENT_[A-Z_]*AUTOMATION_TEST\s*\([^"]*"([^"]+)"', re.S)

def declared(src_dir):
    names = []
    for p in sorted(pathlib.Path(src_dir).rglob('*.cpp')):
        names += DECL.findall(p.read_text(encoding='utf-8', errors='replace'))
    return names

def light(listed, heavy, decl):
    def is_heavy(n): return any(n.startswith(h) for h in heavy)
    out = [n for n in listed if not is_heavy(n)]
    seen = set(listed)
    for n in decl:
        # A prefix the sources paste names onto ("SailingSim.Physics.LongWaves." #Name) is covered by any listed name under it.
        under = n if n.endswith('.') else n + '.'
        if n in seen or is_heavy(n) or any(l.startswith(under) for l in listed): continue
        out.append(n); seen.add(n)
    return out

def read_lines(path):
    return [l.strip() for l in open(path, encoding='utf-8') if l.strip() and not l.startswith('#')]

def self_test():
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / 'Tests.cpp'
        src.write_text('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOld, "SailingSim.Smoke.Old", Flags)\n'
                       'IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNew,\n\t"SailingSim.Smoke.BrandNew", Flags)\n'
                       'IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHeavy, "SailingSim.Physics.PolarGate", Flags)\n'
                       'IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPasted, "SailingSim.Physics.Waves." #Name, Flags)\n')
        got = light(['SailingSim.Smoke.Old', 'SailingSim.Physics.PolarGate', 'SailingSim.Physics.Waves.Golden'],
                    ['SailingSim.Physics.PolarGate'], declared(d))
    want = ['SailingSim.Smoke.Old', 'SailingSim.Physics.Waves.Golden', 'SailingSim.Smoke.BrandNew']
    if got != want:
        print('self-test FAILED: %s, wanted %s' % (got, want)); return 1
    print('self-test ok: a test declared since the last full run is picked up; the heavy set stays out')
    return 0

if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']: sys.exit(self_test())
    listed, heavy = read_lines(sys.argv[1]), read_lines(sys.argv[2])
    print('+'.join(light(listed, heavy, declared(sys.argv[3]))))
