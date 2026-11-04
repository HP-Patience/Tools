"""Regression tests for the local geometry adapter (stdlib only)."""
import csv
import math
from pathlib import Path
import unittest
from geometry import geometry
from layout import WALLS, CENTER, POOL_INNER, MARGIN, SLOPE, edge_clearance

class GeometryTests(unittest.TestCase):
    def test_reference_dataset(self):
        with (Path(__file__).resolve().parents[1] / 'The_first_10000_Penrose-Staircases.csv').open() as f:
            rows = list(csv.DictReader(f))
        for n in (1, 2, 12, 25, 35, 100, 999, 5000, 10000):
            with self.subTest(n=n):
                data = geometry(n)
                ref = rows[n-1]
                self.assertEqual(data['ratio'], [int(ref[k]) for k in ('a','b','c','d')])
                self.assertAlmostEqual(data['length'], float(ref['len']), places=3)
    def test_valid_drawing(self):
        for n in (1, 12, 25, 35, 100, 5000, 10000):
            data = geometry(n)
            self.assertEqual(len(data['route']), data['steps'])
            self.assertGreater(len(data['polygons']), 5)
            for polygon in data['polygons']:
                self.assertGreaterEqual(len(polygon['points']), 3)
                self.assertIn(polygon['face'], ('top','front','side'))
                self.assertTrue(all(math.isfinite(v) for p in polygon['points'] for v in p))
            self.assertLess(data['bounds'][0], data['bounds'][2])
            self.assertLess(data['bounds'][1], data['bounds'][3])
    def assert_scene_constraints(self, n):
        data = geometry(n)
        scene = data['scene']
        self.assertGreaterEqual(scene['clearance'], MARGIN-1e-7, n)
        self.assertGreater(scene['minWallGap'], 0, n)
        self.assertGreater(scene['scale'], 0, n)
        self.assertGreaterEqual(scene['bounds'][1], 170-1e-7, n)
        self.assertTrue(all(math.isfinite(v) for poly in scene['polygons'] for p in poly['points'] for v in p), n)
        base = scene['footprint']
        for axis in (0,1):
            self.assertAlmostEqual(sum(p[axis] for p in base)/4, CENTER[axis], places=7, msg=str(n))
        for i, a in enumerate(base):
            b = base[(i+1)%4]
            self.assertAlmostEqual(abs((b[1]-a[1])/(b[0]-a[0])), SLOPE, places=7, msg=str(n))
        for p in scene['collar']:
            for i,a in enumerate(POOL_INNER):
                self.assertGreaterEqual(edge_clearance(p,a,POOL_INNER[(i+1)%4]), MARGIN-1e-7, n)
        walls = {p['role']:p['points'] for p in scene['polygons'] if p['role'] in WALLS}
        for a,b in ((walls['front_wall'][-2],base[3]),(walls['front_wall'][-1],base[0]),
                    (walls['right_wall'][-2],base[2]),(walls['right_wall'][-1],base[3])):
            for axis in (0,1):
                self.assertAlmostEqual(a[axis],b[axis],places=6,msg=str(n))
        # Every tread, riser, and wall upper-profile vertex must be preserved
        # under ONE uniform scale + translation (including degenerate B=2).
        scale = scene['scale']
        old0 = data['polygons'][0]['points'][0]
        new0 = scene['polygons'][0]['points'][0]
        shift = [new0[i]-old0[i]*scale for i in (0,1)]
        self.assertEqual(len(data['polygons']),len(scene['polygons']),n)
        for old,new in zip(data['polygons'],scene['polygons']):
            self.assertEqual(len(old['points']),len(new['points']),n)
            upper = len(old['points'])-(2 if old['role'] in WALLS else 0)
            for a,b in zip(old['points'][:upper],new['points'][:upper]):
                for axis in (0,1):
                    self.assertAlmostEqual(a[axis]*scale+shift[axis],b[axis],places=6,msg=str(n))
        for a,b in zip(data['route'],scene['route']):
            for axis in (0,1):
                self.assertAlmostEqual(a[axis]*scale+shift[axis],b[axis],places=6,msg=str(n))
        return scene

    def test_full_scene_range(self):
        minimum_clearance = float('inf')
        minimum_wall_gap = float('inf')
        for n in range(1,10001):
            scene = self.assert_scene_constraints(n)
            minimum_clearance = min(minimum_clearance,scene['clearance'])
            minimum_wall_gap = min(minimum_wall_gap,scene['minWallGap'])
        print(f'\nScene sweep: 10000/10000; min clearance={minimum_clearance:.6f}; min wall gap={minimum_wall_gap:.6f}')

    def test_invalid_numbers(self):
        for n in (0,-1,10001,1.2,'35',True):
            with self.subTest(n=n), self.assertRaises(ValueError):
                geometry(n)
    def test_cache(self):
        self.assertIs(geometry(25), geometry(25))

if __name__ == '__main__':
    unittest.main(verbosity=2)
