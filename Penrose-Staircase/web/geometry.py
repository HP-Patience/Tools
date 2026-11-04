"""Headless adapter for F. Lehr's unmodified GPL Penrose viewer.
Execute its drawing functions into vector polygons, never Tk or a window.
"""
import ast
import functools
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import pstairs
from layout import compose_scene, WALLS

tree = ast.parse((BASE / 'vpstairs.py').read_text(encoding='utf-8'))
# Retain the original drawing functions and initial constants, not its CLI.
tree.body = [node for node in tree.body if not (
    isinstance(node, ast.ImportFrom) and node.module == 'graphics'
    or isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    and isinstance(node.value.func, ast.Name) and node.value.func.id == 'main'
)]
CODE = compile(tree, str(BASE / 'vpstairs.py'), 'exec')

@functools.lru_cache(maxsize=128)
def geometry(n):
    if type(n) is not int or not 1 <= n <= 10000:
        raise ValueError('Number must be an integer from 1 to 10000')
    polygons = []
    role = "tread"
    class Point:
        def __init__(self, x, y):
            self.x, self.y = x, y
    class Polygon:
        def __init__(self, points):
            self.points = [[p.x, p.y] for p in points]
        def setFill(self, color):
            self.color = color
        def draw(self, win):
            # Adjacent duplicate vertices are an artifact of the original pen API.
            points = []
            for p in self.points:
                if not points or p != points[-1]:
                    points.append(p)
            polygons.append({'points': points, 'face': self.color, 'role': role})
    ns = {'Point': Point, 'Polygon': Polygon,
          'color_rgb': lambda r,g,b: {(0,255,0): 'top', (0,0,255): 'front', (255,255,0): 'side'}[(r,g,b)]}
    exec(CODE, ns)
    ps = pstairs.PenroseStaircase(n)
    ns.update(A=ps.a, B=ps.b, C=ps.c, D=ps.d, L=ps.l,
              WH=ps.d*2, ZM=1, XO=0, YO=0, PLIST=[], win=None)
    # Label the four structural walls without editing any upstream drawing code.
    def wrap(name):
        fn = ns[name]
        def call(*args):
            nonlocal role
            previous, role = role, name
            try:
                return fn(*args)
            finally:
                role = previous
        return call
    for name in ('front_wall','right_wall','mid_wall2','inner_wall2'):
        ns[name] = wrap(name)
    ns['drawStaircase'](0, 0, ps.l)
    points = [p for poly in polygons for p in poly['points']]
    bounds = [min(p[0] for p in points), min(p[1] for p in points),
              max(p[0] for p in points), max(p[1] for p in points)]
    tops = [p for p in polygons if p['face'] == 'top']
    a, d, b = ps.a, ps.d-1, ps.b-1
    ordered = tops[:a][::-1] + tops[a+d:a+d+b] + tops[a+d+b:] + tops[a:a+d][::-1]
    route = []
    for p in ordered:
        pts = p['points']
        route.append([sum(v[0] for v in pts)/len(pts), sum(v[1] for v in pts)/len(pts)])
    original = polygons
    # Preserve the upper profile from the non-degenerate original capture.
    # Drawing with WH=0 collapses coincident vertices during deduplication,
    # so the last two vertices would no longer reliably denote the base.
    extrusion = ns['getFinalPoint'](ns['U'] * ns['WH'] * .5, ns['H'] * ns['WH'])
    zero_walls = []
    for polygon in original:
        pts = [v[:] for v in polygon['points']]
        if polygon['role'] in WALLS:
            for v in pts[-2:]:
                v[0] -= extrusion.x
                v[1] -= extrusion.y
        zero_walls.append({**polygon, 'points': pts})
    scene = compose_scene(zero_walls, route)
    return {'scene': scene, 'number': n, 'ratio': [ps.a, ps.b, ps.c, ps.d], 'length': ps.l,
            'polygons': original, 'bounds': bounds, 'route': route, 'steps': len(tops)}
