#!/usr/bin/env python3
"""Benchmark: synthetic scans with planted tracking-dot grids and hard negatives.
Every page has text, scanner specks; many have highlighter strokes and a yellow logo."""
import json, random, time
import dotscrub as ds

W, H, PITCH = 1240, 1754, 8            # A4 at 150 dpi, dot pitch ~1.35 mm

def page(rng, tracked):
    rows = [bytearray((250 - (y % 7 == 0), 249, 245) * W) for y in range(H)]   # paper tint
    ink = set()
    def rect(x0, y0, x1, y1, c, mark=False):
        for y in range(max(0, y0), min(H, y1)):
            rows[y][x0 * 3:x1 * 3] = bytes(c) * (x1 - x0)
            if mark: ink.update((x, y) for x in range(x0, x1))
    y = 120
    while y < H - 120:                                  # text lines of word-blocks
        x = 100
        while x < W - 160:
            wlen = rng.randint(20, 90); rect(x, y, x + wlen, y + 14, (40, 40, 45), True); x += wlen + rng.randint(8, 16)
        y += rng.randint(30, 44)
    for _ in range(rng.randint(0, 4)):                  # highlighter strokes (hard negative)
        hx, hy = rng.randint(100, 700), rng.randint(120, H - 200)
        for yy in range(hy, hy + 22):
            for xx in range(hx, hx + rng.randint(200, 420) if yy == hy else hx + 300):
                if xx < W and (xx, yy) not in ink: rows[yy][xx * 3:xx * 3 + 3] = b"\xfa\xf0\x78"
    if rng.random() < 0.5:                              # yellow logo (hard negative)
        cx, cy, r = rng.randint(900, 1100), 70, 40
        for yy in range(cy - r, cy + r):
            for xx in range(cx - r, cx + r):
                if (xx - cx) ** 2 + (yy - cy) ** 2 < r * r: rows[yy][xx * 3:xx * 3 + 3] = b"\xf5\xd0\x20"
    for _ in range(60):                                 # lone scanner specks (hard negative)
        sx, sy = rng.randrange(W), rng.randrange(H); rows[sy][sx * 3:sx * 3 + 3] = b"\xfc\xf6\xb4"
    planted = []
    if tracked:
        bits = [[rng.random() < 0.4 for _ in range(15)] for _ in range(8)]
        for ty in range(0, H, 8 * PITCH + 48):
            for tx in range(0, W, 15 * PITCH + 40):
                for r in range(8):
                    for c in range(15):
                        if not bits[r][c] or rng.random() < 0.08: continue    # scan loss
                        x, y = tx + c * PITCH + rng.randint(-1, 1), ty + r * PITCH + rng.randint(-1, 1)
                        px = [(x + dx, y + dy) for dx in (0, 1) for dy in (0, 1) if 0 <= x + dx < W and 0 <= y + dy < H]
                        if not px or any(p in ink for p in px): continue      # hidden under toner
                        col = bytes((rng.randint(248, 255), rng.randint(244, 252), rng.randint(150, 205)))
                        for qx, qy in px: rows[qy][qx * 3:qx * 3 + 3] = col
                        planted.append(px)
    return rows, planted

def main(n=200, seed=7):
    rng = random.Random(seed); res = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "dots": 0, "dots_removed": 0,
                                      "wrong_pixels": 0, "seconds": 0.0, "pages": n}
    preview = None
    for i in range(n):
        tracked = i % 2 == 0
        rows, planted = page(rng, tracked)
        before = [bytes(r) for r in rows]
        t = time.perf_counter(); dots = ds.find_dots(W, H, rows); ds.scrub(rows, dots); res["seconds"] += time.perf_counter() - t
        hit = bool(dots)
        res["tp" if tracked and hit else "fn" if tracked else "fp" if hit else "tn"] += 1
        dot_px = {p for d in planted for p in d}
        for d in planted:
            res["dots"] += 1
            px = [rows[y][x * 3:x * 3 + 3] for x, y in d]
            res["dots_removed"] += all(min(p[0], p[1]) - p[2] < 18 for p in px)
        for y in range(H):
            if rows[y] != before[y]:
                res["wrong_pixels"] += sum(1 for x in range(W) if rows[y][x * 3:x * 3 + 3] != before[y][x * 3:x * 3 + 3] and (x, y) not in dot_px)
        if tracked and preview is None: preview = (before, [bytes(r) for r in rows])
    res["seconds_per_page"] = round(res["seconds"] / n, 2); res["seconds"] = round(res["seconds"], 1)
    res["dot_recall"] = round(res["dots_removed"] / max(1, res["dots"]), 4)
    json.dump(res, open("bench.json", "w"), indent=1); print(json.dumps(res))
    # preview: 300x180 crop, blue channel stretched (the blue-light trick), before | after, 3x
    b, a = preview; x0, y0, cw, chh, s = 20, 20, 300, 180, 3
    out = []
    for y in range(chh * s):
        line = bytearray()
        for src in (b, a):
            for x in range(cw * s):
                p = src[y0 + y // s][(x0 + x // s) * 3:(x0 + x // s) * 3 + 3]
                v = max(0, min(255, (p[2] - 140) * 3))
                line += bytes((v, v, v))
            line += b"\xe0\x40\x40" * 6
        out.append(line)
    ds.write_png("docs/preview.png", (cw * s + 6) * 2, chh * s, out)

if __name__ == "__main__":
    main()
