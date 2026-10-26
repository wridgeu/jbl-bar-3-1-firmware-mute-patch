"""Build a patched JBL Bar 3.1 V49 firmware that loses less sound after a pause or a signal change.

  uv run tools/patch.py firmware/original/JBLBAR3_1.HUI my_build/JBLBAR3_1.HUI [ticks] [--silence N]

Fix A (default, tested on one unit): the stock firmware mutes for 60 ticks (10 ms each, so 0.6 s) at three
places in the codec monitor. This sets all three to TICKS (or the ticks argument; 60 leaves part 0 as it is).
Nothing else in part 0 changes, except a debug-only log text: a few of its characters are rewritten so that
both Sunplus checksums of part 0 come out unchanged
  - outer: 16-bit word sum of the scrambled part from +0x80 (stored at +0x10),
  - inner: 16-bit word sum of the unscrambled image from +0xd0 (stored at +0xa0 and +0xc0),
which keeps part 0's header byte-identical.

Fix B (opt-in with --silence, experimental): sets the DSP's PCM silence threshold (stock 48000 samples) in the
8 configuration blocks of part 2 that write it. After that many silent samples the DSP reports "silent input",
and the bar mutes and sets the DSP up again. A large value should keep that from happening during pauses;
0 does the opposite (tested: no audio at all), so it is refused.

hui.repack then fixes the container checksums. See NOTES.md.
"""

import argparse
import hashlib
import struct
import sys
from itertools import combinations, product
from pathlib import Path
from typing import NoReturn

import hui

# Mute length in ticks after the codec loses lock, locks again, or sees a different signal. Stock: 60.
# Smaller = sound returns sooner but more clicks may be audible; 0 is not allowed (it means "mute until unmuted").
TICKS = 10

# DSP PCM silence threshold for fix B (experimental), or None to leave part 2 alone. Stock: 0xBB80 (48000).
# 0 is refused: on a real Bar 3.1 it made the DSP report silence at once, and no audio played.
SILENCE = None

V49_SHA256 = "d5d014f18cfb17a4e4f65179cd14d024c7462f7a7c6fd78f65aaf704287bcaa6"
BASE = 0x88006000  # load address of part 0
SITES = (0x8802B67C, 0x8802B90C, 0x8802BA38)  # codec unlock, after lock, signal changed
OLD = 0x2404003C  # addiu a0, zero, 60: the mute() timeout argument at each site
LOG = (0x8805186C, b"codec:unlock,mute on")  # referenced once, as a debug printf format
PRINTABLE = [c for c in range(0x20, 0x7F) if c not in b"%\\"]  # allowed replacements: printable, no format chars

# Part 2 (DSP flash image, big-endian): offsets of the value word after each "81000008" (OS module index 8,
# PCM_AUTODETECT_SILENCE_THRESHOLD). They lie in config blocks (INIT 0/2, PCM, Dolby Digital) that have no
# checksum of their own; the DSP programs (ffffffff + checksum) are not touched.
SILENCE_SITES = (0x10148, 0x103C0, 0x11AB0, 0x11B6C, 0x11F84, 0x12100, 0x1227C, 0x123F8)
SILENCE_CMD, SILENCE_STOCK = 0x81000008, 0xBB80


def fail(msg: str) -> NoReturn:
    sys.exit(f"error: {msg}")


def sum16(b: bytes) -> int:
    return sum(struct.unpack(f"<{len(b) // 2}H", b)) & 0xFFFFFFFF


def word(raw: bytes, o: int) -> int:
    """Unscrambled u32 at offset o of part 0."""
    return struct.unpack("<I", bytes(raw[o + k] ^ hui.key(o + k) for k in range(4)))[0]


def plain_sum(raw: bytes) -> int:
    """Inner checksum: 16-bit word sum of the unscrambled image from 0xd0 to 0x80 + the length stored at 0xc4."""
    p = hui.unscramble(raw)
    return sum16(p[0xD0 : 0x80 + struct.unpack_from("<I", p, 0xC4)[0]])


def compensate(raw: bytearray, d_raw: int, d_plain: int) -> None:
    """Undo sum changes of the scrambled (d_raw) and unscrambled (d_plain) data at once by rewriting characters
    of the log text: first 2 letters at even and 2 at odd offsets (meet in the middle), else any characters."""
    addr, text = LOG
    o0 = addr - BASE
    if bytes(raw[o0 + i] ^ hui.key(o0 + i) for i in range(len(text))) != text:
        fail("log text not found (wrong firmware?)")
    if d_raw == d_plain == 0:
        return
    letters = [o0 + i for i, c in enumerate(text) if chr(c).isalpha()]

    def opts(o):  # (new raw byte, raw sum change, plain sum change) per allowed character
        w = 0x100 if o % 2 else 1
        k = hui.key(o)
        return [(n ^ k, ((n ^ k) - raw[o]) * w, (n - (raw[o] ^ k)) * w) for n in PRINTABLE]

    def table(ps):  # (raw change, plain change) -> new raw bytes, for every way of rewriting positions ps
        t = {}
        for ch in product(*map(opts, ps)):
            t.setdefault((sum(c[1] for c in ch), sum(c[2] for c in ch)), [c[0] for c in ch])
        return t

    lo, hi = [o for o in letters if o % 2 == 0], [o for o in letters if o % 2]
    his = [(h, table(h)) for h in combinations(hi, 2)]
    for los in combinations(lo, 2):
        t = table(los)
        for h, th in his:
            for (r, p), new in th.items():
                hit = t.get((d_raw - r, d_plain - p))
                if hit:
                    for o, b in zip(los + h, hit + new, strict=True):
                        raw[o] = b
                    return

    def reach(ps):  # every reachable (raw change, plain change) -> fewest rewrites [(offset, new raw byte)]
        s = {(0, 0): []}
        for o in ps:
            for (r, p), path in list(s.items()):
                for b, dr, dp in opts(o):
                    k = (r + dr, p + dp)
                    if k not in s or len(s[k]) > len(path) + 1:
                        s[k] = path + [(o, b)]
        return s

    # 2 + 2 letters was not enough: allow any number of rewrites anywhere in the text
    every = range(o0, o0 + len(text))
    lo_s, hi_s = reach(o for o in every if o % 2 == 0), reach(o for o in every if o % 2)
    for (r, p), path in hi_s.items():
        hit = lo_s.get((d_raw - r, d_plain - p))
        if hit is not None:
            for o, b in hit + path:
                raw[o] = b
            return
    fail(f"no way to keep both checksums for this tick value (sum deltas {d_raw}, {d_plain}); try another")


def set_ticks(part0: bytes, ticks: int) -> bytes:
    """Fix A: set the three codec-monitor mute timeouts, keeping both Sunplus checksums of part 0."""
    raw = bytearray(part0)
    offs = [s - BASE for s in SITES]
    for o in offs:
        if word(raw, o) != OLD:
            fail(f"{BASE + o:#x}: expected {OLD:#010x}, found {word(raw, o):#010x}")
    before, before_p = sum16(raw[0x80:]), plain_sum(raw)
    if before != struct.unpack_from("<I", raw, 0x10)[0] or [word(raw, 0xA0), word(raw, 0xC0)] != [before_p] * 2:
        fail("part 0 checksums are not as expected")
    for o in offs:  # the timeout is the low halfword of the instruction
        raw[o : o + 2] = bytes(b ^ hui.key(o + k) for k, b in enumerate(struct.pack("<H", ticks)))
    compensate(raw, before - sum16(raw[0x80:]), before_p - plain_sum(raw))
    if sum16(raw[0x80:]) != before or plain_sum(raw) != before_p:
        fail("checksum compensation went wrong")
    return bytes(raw)


def set_silence(part2: bytes, value: int) -> bytes:
    """Fix B: write value into every silence-threshold command of the DSP image."""
    p = bytearray(part2)
    cmds = [o for o in range(0, len(p), 4) if struct.unpack_from(">I", p, o)[0] == SILENCE_CMD]
    if [o + 4 for o in cmds] != list(SILENCE_SITES):
        fail(f"part 2: silence threshold commands at {[hex(o) for o in cmds]}, expected 8 known ones")
    for o in SILENCE_SITES:
        if struct.unpack_from(">I", p, o)[0] != SILENCE_STOCK:
            fail(f"part 2 {o:#x}: silence threshold is not the stock {SILENCE_STOCK:#x}")
        struct.pack_into(">I", p, o, value)
    return bytes(p)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="original firmware/original/JBLBAR3_1.HUI (V49)")
    ap.add_argument("dst", type=Path, help="output file; name it JBLBAR3_1.HUI on the USB stick")
    ap.add_argument("ticks", type=int, nargs="?", default=TICKS,
                    help=f"mute length in ticks (default {TICKS}, stock 60)")
    ap.add_argument("--silence", type=lambda s: int(s, 0), default=SILENCE, metavar="N",
                    help="fix B: DSP silence threshold in samples, e.g. 0x7fffffff (stock 48000; default: leave as is)")
    a = ap.parse_args()
    if not 0 < a.ticks < 64:  # above 63 the log text cannot balance the checksums
        fail("ticks must be 1..63 (0 means mute until something unmutes)")
    if a.silence == 0:
        fail("--silence 0 makes the DSP report silence at once: tested on a Bar 3.1, it plays no audio at all")
    if a.silence is not None and not 0 < a.silence <= 0x7FFFFFFF:  # the DSP might compare it as signed
        fail("--silence must be 1..0x7fffffff")
    if a.dst.name != "JBLBAR3_1.HUI":
        print(f"note: the updater only looks for JBLBAR3_1.HUI; rename {a.dst.name} on the USB stick")

    d = a.src.read_bytes()
    if hashlib.sha256(d).hexdigest() != V49_SHA256:
        fail(f"{a.src} is not the original V49 JBLBAR3_1.HUI")
    body = {i: d[off : off + sz] for i, _, off, sz, _, _ in hui.parts(d)}
    bodies = {0: set_ticks(body[0], a.ticks)}
    if a.silence is not None:
        bodies[2] = set_silence(body[2], a.silence)
    new = hui.repack(d, bodies)
    if hui.check(new):
        fail("output fails its container checksums")
    a.dst.parent.mkdir(parents=True, exist_ok=True)
    a.dst.write_bytes(new)
    o = LOG[0] - BASE
    log = bytes(bodies[0][o + i] ^ hui.key(o + i) for i in range(len(LOG[1])))
    changed = sum(x != y for x, y in zip(d, new, strict=True))
    silence = "stock" if a.silence is None else f"{a.silence:#x}"
    print(f"{a.dst}: mute {a.ticks} ticks, log text {log!r}; DSP silence threshold {silence}; {changed} bytes changed")


if __name__ == "__main__":
    main()
