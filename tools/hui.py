"""Unpack / repack / check a JBL Bar 3.1 .HUI firmware container.

Layout (little-endian):
  0x00 'HUI ', version=1, part count, table offset (0x30), file size
  0x14 file checksum: makes the u32 word sum of the whole file 0 (computed with this slot zeroed)
  0x30 table, 0x20 bytes per part: type, 0, offset, size, checksum (u32 word sum of part + checksum = 0)

  uv run tools/hui.py check  JBLBAR3_1.HUI
  uv run tools/hui.py unpack JBLBAR3_1.HUI outdir           -> outdir/part<i>_type<t>.bin
  uv run tools/hui.py repack JBLBAR3_1.HUI outdir new.HUI   (keeps header/table, swaps part bodies, fixes checksums)
"""

import struct
import sys
from pathlib import Path


def key(i: int) -> int:
    """XOR key of part 0 at offset i (Sunplus STK scramble "mode 3"); applying it twice restores the data."""
    return 0xA5 ^ (i & 0x54)


def unscramble(raw: bytes) -> bytes:
    return bytes(b ^ key(i) for i, b in enumerate(raw))


def neg_sum32(b: bytes) -> int:
    if len(b) % 4:
        raise ValueError("length must be a multiple of 4")
    return -sum(struct.unpack(f"<{len(b) // 4}I", b)) & 0xFFFFFFFF


def parts(d: bytes):
    """Yield (index, type, offset, size, checksum, table row offset) for each part."""
    magic, _ver, count, table, size = struct.unpack_from("<4sIIII", d, 0)
    if magic != b"HUI " or size != len(d):
        raise ValueError("not a .HUI file, or truncated")
    for i in range(count):
        t, _, off, sz, ck = struct.unpack_from("<IIIII", d, table + i * 0x20)
        if off + sz > len(d):
            raise ValueError(f"part {i} lies outside the file")
        yield i, t, off, sz, ck, table + i * 0x20


def check(d: bytes) -> list[str]:
    errs = [f"part {i}: checksum" for i, _, off, sz, ck, _ in parts(d) if neg_sum32(d[off : off + sz]) != ck]
    if neg_sum32(d[:0x14] + b"\0" * 4 + d[0x18:]) != struct.unpack_from("<I", d, 0x14)[0]:
        errs.append("file checksum")
    return errs


def repack(d: bytes, bodies: dict[int, bytes]) -> bytes:
    out = bytearray(d)
    for i, _, off, sz, _, row in parts(d):
        body = bodies.get(i, d[off : off + sz])
        if len(body) != sz:
            raise ValueError(f"part {i}: size changed ({len(body)} != {sz}); resizing is not supported")
        out[off : off + sz] = body
        struct.pack_into("<I", out, row + 0x10, neg_sum32(body))
    struct.pack_into("<I", out, 0x14, 0)
    struct.pack_into("<I", out, 0x14, neg_sum32(bytes(out)))
    return bytes(out)


def main(args: list[str]) -> None:
    if not args or len(args) != {"check": 2, "unpack": 3, "repack": 4}.get(args[0]):
        sys.exit(__doc__)
    cmd, src, *rest = args
    d = Path(src).read_bytes()
    if cmd == "check":
        errs = check(d)
        print("OK" if not errs else "\n".join(errs))
        sys.exit(1 if errs else 0)
    out = Path(rest[0])
    if cmd == "unpack":
        out.mkdir(parents=True, exist_ok=True)
        for i, t, off, sz, ck, _ in parts(d):
            (out / f"part{i}_type{t}.bin").write_bytes(d[off : off + sz])
            print(f"part{i} type{t} off={off:#x} size={sz:#x} ck={ck:#010x}")
    else:
        new = repack(d, {i: (out / f"part{i}_type{t}.bin").read_bytes() for i, t, *_ in parts(d)})
        Path(rest[1]).write_bytes(new)
        print(f"wrote {rest[1]}; identical to source: {new == d}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, struct.error) as e:
        sys.exit(f"error: {e}")
