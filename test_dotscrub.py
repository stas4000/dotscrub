import os, random, tempfile, unittest
import dotscrub as ds, bench

class T(unittest.TestCase):
    def test_png_roundtrip(self):
        rows = [bytearray(random.Random(y).randbytes(30)) for y in range(7)]
        p = os.path.join(tempfile.mkdtemp(), "a.png"); ds.write_png(p, 10, 7, rows)
        self.assertEqual(ds.load(p), (10, 7, rows))

    def test_tracked_page_is_found_and_cleaned(self):
        rows, planted = bench.page(random.Random(1), True)
        dots = ds.find_dots(bench.W, bench.H, rows); self.assertGreater(len(dots), 100)
        ds.scrub(rows, dots); self.assertEqual(ds.find_dots(bench.W, bench.H, rows), [])

    def test_clean_page_with_highlighter_and_specks_is_left_alone(self):
        rng = random.Random(2)
        for _ in range(3):
            rows, _ = bench.page(rng, False)
            self.assertEqual(ds.find_dots(bench.W, bench.H, rows), [])

if __name__ == "__main__":
    unittest.main()
