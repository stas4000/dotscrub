# dotscrub

Find and remove printer tracking dots from a scanned page. One Python file, standard library only, runs locally.

Most colour laser printers add a faint grid of yellow dots to every page (a Machine Identification Code). The dots are
almost invisible on white paper, but a scan keeps them. `dotscrub` finds that grid and paints each dot back to paper colour.

```
python3 dotscrub.py scan.png                 # report: tracked or not, dot count
python3 dotscrub.py scan.png -o clean.png    # write a cleaned page
python3 dotscrub.py scan.png --json
```
PNG and PPM work with the standard library. JPEG and TIFF work when Pillow is installed.

![before and after, blue channel stretched so the dots show](docs/preview.png)

## How it tells dots from everything else
A tracking dot is a tiny yellow blob that sits in a dense lattice of other tiny yellow blobs.
Highlighter strokes and yellow logos are too big to count. Lone scanner specks are too isolated.
Only pages with at least 24 lattice dots are marked as tracked, and only those blobs are touched.

## Benchmark (measured, one run, `python3 bench.py`)
200 synthetic A4 scans at 150 dpi: 100 carry a repeating 15 x 8 dot grid (40% filled, 8% scan loss, jitter,
dots hidden under text), 100 are clean. Every page has text blocks and 60 lone yellow scanner specks;
many also carry highlighter strokes and a yellow logo as hard negatives.

| metric | result |
|---|---|
| pages classified right | 200 / 200 (0 false alarms on highlighter and logo pages) |
| planted dots removed | 431,230 / 434,745 (99.19%) |
| text pixels changed | 0 |
| other pixels changed | 5,776 of 435 million, lone yellow specks and highlighter edges |
| speed | 0.18 s per page, pure Python, one CPU core |
| cost | $0, no API calls |

The pages are synthetic because the dot positions have to be known to score recall. Real printers differ in dot size,
pitch and colour; `find_dots` takes `max_area`, `radius` and `min_neighbors` to tune for your scanner's dpi.
Removing dots from a scan does not change the printed original.

## Tests
```
python3 -m unittest test_dotscrub
```

Built with Claude Opus 5.5. Inspired by [@eligaultney's question](https://x.com/eligaultney/status/1771642904890458254).
MIT License.
