#!/usr/bin/env python3
"""dotscrub: find and remove printer tracking dots (yellow MIC grids) from scanned pages.

Standard library only. Reads/writes PNG and PPM; JPEG works if Pillow is installed.
MIT License. Built with Claude Opus 5.5.
"""
import argparse, json, struct, sys, time, zlib

# ---------- image IO (8-bit RGB) ----------

def _unfilter(raw, w, h, bpp):
    stride = w * bpp
    out, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]; line = bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        if f == 1:
            for x in range(bpp, stride): line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                line[x] = (line[x] + ((line[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out.append(line); prev = line
    return out

def read_png(data):
    pos, idat, w = 8, b"", None
    while pos < len(data):
        n, = struct.unpack(">I", data[pos:pos + 4]); t = data[pos + 4:pos + 8]; body = data[pos + 8:pos + 8 + n]
        if t == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise ValueError("PNG must be 8-bit RGB/RGBA, non-interlaced")
        elif t == b"IDAT": idat += body
        pos += 12 + n
    bpp = 3 if ctype == 2 else 4
    rows = _unfilter(zlib.decompress(idat), w, h, bpp)
    if bpp == 4:
        rows = [bytearray(b for i, b in enumerate(r) if i % 4 != 3) for r in rows]
    return w, h, rows

def write_png(path, w, h, rows):
    def chunk(t, b): return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    raw = b"".join(b"\0" + bytes(r) for r in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

def load(path):
    with open(path, "rb") as f: data = f.read()
    if data[:8] == b"\x89PNG\r\n\x1a\n": return read_png(data)
    if data[:2] == b"P6":
        parts = data.split(maxsplit=4); w, h = int(parts[1]), int(parts[2]); px = parts[4]
        return w, h, [bytearray(px[y * w * 3:(y + 1) * w * 3]) for y in range(h)]
    try:
        from PIL import Image  # optional, only for JPEG/TIFF scans
    except ImportError:
        sys.exit("dotscrub: PNG or PPM input (install Pillow for JPEG/TIFF)")
    im = Image.open(path).convert("RGB"); w, h = im.size; b = im.tobytes()
    return w, h, [bytearray(b[y * w * 3:(y + 1) * w * 3]) for y in range(h)]

# ---------- detection ----------

HI = bytes(1 if v > 150 else 0 for v in range(256))
LO = bytes(1 if v < 235 else 0 for v in range(256))

def yellow_pixels(w, rows, gap=18):
    """(x, y) of faint-to-strong yellow pixels: bright red and green, blue clearly lower."""
    hits = set()
    for y, row in enumerate(rows):
        r, g, b = bytes(row[0::3]), bytes(row[1::3]), bytes(row[2::3])
        m = int.from_bytes(r.translate(HI), "big") & int.from_bytes(g.translate(HI), "big") & int.from_bytes(b.translate(LO), "big")
        if not m: continue
        cand = m.to_bytes(w, "big")
        x = cand.find(1)
        while x != -1:
            if min(r[x], g[x]) - b[x] >= gap and abs(r[x] - g[x]) < 70: hits.add((x, y))
            x = cand.find(1, x + 1)
    return hits

def blobs(pixels):
    seen, out = set(), []
    for p in pixels:
        if p in seen: continue
        stack, blob = [p], []; seen.add(p)
        while stack:
            x, y = stack.pop(); blob.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pixels and q not in seen: seen.add(q); stack.append(q)
        out.append(blob)
    return out

def find_dots(w, h, rows, max_area=16, radius=40, min_neighbors=3, min_dots=24):
    """Tracking dots are tiny yellow blobs that sit in a dense lattice. Big yellow shapes
    (highlighter, logos) are too large; scanner specks are too lonely."""
    tiny = [b for b in blobs(yellow_pixels(w, rows)) if len(b) <= max_area]
    cent = [(sum(p[0] for p in b) / len(b), sum(p[1] for p in b) / len(b)) for b in tiny]
    grid = {}
    for i, (cx, cy) in enumerate(cent): grid.setdefault((int(cx // radius), int(cy // radius)), []).append(i)
    keep = []
    for i, (cx, cy) in enumerate(cent):
        gx, gy, n = int(cx // radius), int(cy // radius), 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j != i and (cent[j][0] - cx) ** 2 + (cent[j][1] - cy) ** 2 <= radius * radius: n += 1
        if n >= min_neighbors: keep.append(tiny[i])
    return keep if len(keep) >= min_dots else []

def scrub(rows, dots):
    """Paint each dot with the paper colour around it."""
    for blob in dots:
        xs = [p[0] for p in blob]; ys = [p[1] for p in blob]; own = set(blob); ring = []
        for y in range(min(ys) - 2, max(ys) + 3):
            if not 0 <= y < len(rows): continue
            for x in range(min(xs) - 2, max(xs) + 3):
                if (x, y) not in own and 0 <= x * 3 < len(rows[y]):
                    px = rows[y][x * 3:x * 3 + 3]
                    if px[2] >= min(px[0], px[1]) - 10: ring.append(px)
        fill = [sorted(c[k] for c in ring)[len(ring) // 2] for k in range(3)] if ring else [255, 255, 255]
        for x, y in blob: rows[y][x * 3:x * 3 + 3] = bytes(fill)
    return len(dots)

def main(argv=None):
    ap = argparse.ArgumentParser(description="Find and remove printer tracking dots from scanned pages.")
    ap.add_argument("scan"); ap.add_argument("-o", "--out", help="write the cleaned page as PNG")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    t = time.perf_counter(); w, h, rows = load(a.scan); dots = find_dots(w, h, rows)
    rep = {"file": a.scan, "tracking_dots": len(dots), "tracked": bool(dots)}
    if a.out: scrub(rows, dots); write_png(a.out, w, h, rows); rep["cleaned"] = a.out
    rep["seconds"] = round(time.perf_counter() - t, 2)
    if a.json: print(json.dumps(rep))
    else:
        print(f"{a.scan}: " + (f"{len(dots)} tracking dots found" if dots else "no tracking dots found")
              + (f", cleaned page written to {a.out}" if a.out else "") + f" ({rep['seconds']}s)")
    return 1 if dots and not a.out else 0

if __name__ == "__main__":
    sys.exit(main())
