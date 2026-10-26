"""Self-test for patch.py and hui.py: known outputs, and refusal of bad input.

  uv run tools/selftest.py
"""

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import hui
import patch

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "firmware/original/JBLBAR3_1.HUI"
PATCHED = ROOT / "firmware/patched/fix-A/JBLBAR3_1.HUI"
BUILDS = {  # patch.py arguments -> SHA-256 of the output
    (): "9238994226eb5a4d9bdd22d066f8ea17885997f3700eefd0899ac661ca06f395",  # fix A, the published file
    ("60", "--silence", "0x7fffffff"): "ee2d0f239269d1a8bd841b385f04a1d5dcf7bd3e690892753da42a95e7613f89",  # fix B
    ("10", "--silence", "0x7fffffff"): "865ad5fd285bce903bd586e5cd73700f5d6fb4176799a143c96e814aca1e78b1",  # A + B
    ("60", "--ignore-silence"): "317f6e101ea4c17978b90ad0ba7fb7e38d01c35d924b5a6df2e1c2e5af0d17a9",  # fix C
    ("20", "--ignore-silence"): "b1cd6ca6b6b5e45038644bd93e9dc391db372340941f3ac0bdcc3a8799ffc808",  # A + C, published
    ("60",): patch.V49_SHA256,  # stock: identical to the original
    ("60", "--silence", "0xbb80"): patch.V49_SHA256,
}
failures = []


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=ROOT)


def refusal(fn, *args) -> str:
    """The error message fn exits with, or "" if it does not refuse."""
    try:
        fn(*args)
    except SystemExit as e:
        return str(e)
    return ""


with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "JBLBAR3_1.HUI"
    for args, sha in BUILDS.items():
        r = run("tools/patch.py", ORIGINAL, out, *args)
        ok = r.returncode == 0 and hashlib.sha256(out.read_bytes()).hexdigest() == sha
        check(ok, f"build {' '.join(args) or 'default'}")
    refusals = [  # (patch.py arguments, what, text the error must contain)
        ((PATCHED, out), "an already patched file", "not the original"),
        ((ROOT / "README.md", out), "a non-.HUI file", "not the original"),
        ((ORIGINAL, out, "0"), "0 ticks", "1..63"),
        ((ORIGINAL, out, "64"), "64 ticks", "1..63"),
        ((ORIGINAL, out, "10", "--silence", "0"), "threshold 0", "no audio"),
        ((ORIGINAL, out, "10", "--silence", "0x80000000"), "a threshold above 0x7fffffff", "1..0x7fffffff"),
    ]
    for args, what, says in refusals:
        r = run("tools/patch.py", *args)
        check(r.returncode != 0 and r.stderr.startswith("error:") and says in r.stderr, f"refuses {what}: '{says}'")
    bad = bytearray(ORIGINAL.read_bytes())
    bad[0x1000] ^= 1
    (Path(tmp) / "bad.HUI").write_bytes(bad)
    check(run("tools/hui.py", "check", Path(tmp) / "bad.HUI").returncode != 0, "hui.py check catches a flipped bit")

d = ORIGINAL.read_bytes()
body = {i: d[off : off + sz] for i, _, off, sz, _, _ in hui.parts(d)}
bad = bytearray(d)
bad[0x14] ^= 1
check(hui.check(bytes(bad)) == ["file checksum"], "hui.check finds a wrong file checksum alone")
_, _, off1, _, _, _ = list(hui.parts(d))[1]
bad = bytearray(d)
bad[off1] ^= 1
bad[0x14:0x18] = b"\0" * 4  # recompute the file checksum, so only part 1's checksum is wrong
bad[0x14:0x18] = hui.neg_sum32(bytes(bad)).to_bytes(4, "little")
check(hui.check(bytes(bad)) == ["part 1: checksum"], "hui.check finds a wrong part checksum alone")

for site in (patch.SITES[1], patch.IGNORE_SITE):
    part0 = bytearray(body[0])
    part0[site - patch.BASE] ^= 1
    msg = refusal(patch.patch_part0, bytes(part0), 10, True)
    check(f"{site:#x}" in msg, f"patch_part0 refuses a change at {site:#x}")
for o in (patch.SILENCE_SITES[0], patch.SILENCE_SITES[-1] - 4):  # a changed value, a missing command
    part2 = bytearray(body[2])
    part2[o + 3] ^= 1
    check(refusal(patch.set_silence, bytes(part2), 0x7FFFFFFF) != "", f"set_silence refuses a change at part 2 {o:#x}")
check(hui.repack(d, {}) == d, "hui.repack without changes gives the original")

print(f"{len(failures)} failed" if failures else "all passed")
sys.exit(1 if failures else 0)
