"""Scene-space constraints for the 2D illusion; not a reconstruction of 3D stairs.
The original treads are unchanged. Wall bottoms share a projected foundation.
"""
import math

SLOPE = 0.8 / math.sqrt(3)
CENTER = (520.0, 485.0)
POOL_INNER = [[110.0, 485.0], [520.0, 485.0-410*SLOPE],
              [930.0, 485.0], [520.0, 485.0+410*SLOPE]]
POOL_OUTER = [[65.0, 485.0], [520.0, 485.0-455*SLOPE],
              [975.0, 485.0], [520.0, 485.0+455*SLOPE]]
WALLS = {'front_wall', 'right_wall', 'mid_wall2', 'inner_wall2'}
MARGIN = 38.0
COLLAR_SCALE = 1.035

def edge_clearance(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    return (dx*(point[1]-a[1])-dy*(point[0]-a[0])) / math.hypot(dx, dy)

def compose_scene(zero_walls, route):
    fronts = {p['role']: p for p in zero_walls if p['role'] in WALLS}
    # In the original pen API, the final two vertices close each wall at its base.
    front = fronts['front_wall']['points'][-2]
    left = fronts['front_wall']['points'][-1]
    right = fronts['right_wall']['points'][-2]
    rear = [left[0]+right[0]-front[0], left[1]+right[1]-front[1]]
    width = right[0]-left[0]
    required = 0.0
    for wall in fronts.values():
        a, b = wall['points'][-2:]
        dx = b[0]-a[0]
        if abs(dx) < width * 1e-7:
            continue  # B=2 collapses the inner wall base to a vertical seam.
        for x,y in wall['points'][:-2]:
            # Extend the base line, not a horizontal screen-Y cutoff.
            ground_y = a[1] + (x-a[0]) * (b[1]-a[1]) / dx
            required = max(required, y-ground_y)
    # Small positive shell depth. Remove the original arbitrary WH = D*2 bulk.
    shell_depth = width * .055
    offset = required + shell_depth
    footprint = [[x,y+offset] for x,y in [left,rear,right,front]]
    origin = [sum(p[i] for p in footprint)/4 for i in (0,1)]
    adjusted = []
    min_wall_gap = math.inf
    for p in zero_walls:
        pts = [v[:] for v in p['points']]
        if p['role'] in WALLS:
            for v in pts[-2:]:
                v[1] += offset
            a,b = pts[-2:]
            for x,y in (pts[:-2] if abs(b[0]-a[0]) > width*1e-7 else []):
                min_wall_gap = min(min_wall_gap, a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0])-y)
        adjusted.append({**p,'points':pts})
    # Limit the footprint first. Total building bounds only set additional limits.
    scale = 540/width
    for p in footprint:
        delta = [(p[i]-origin[i])*COLLAR_SCALE for i in (0,1)]
        for i,a in enumerate(POOL_INNER):
            b = POOL_INNER[(i+1)%4]
            available = edge_clearance(CENTER,a,b)-MARGIN
            direction = edge_clearance([CENTER[0]+delta[0],CENTER[1]+delta[1]],a,b)-edge_clearance(CENTER,a,b)
            if direction < 0:
                scale = min(scale, available/-direction)
    vertices = [v for p in adjusted for v in p['points']]
    for x,y in vertices:
        if y < origin[1]:
            scale = min(scale, (CENTER[1]-170)/(origin[1]-y))
    def transform(v):
        return [CENTER[0]+(v[0]-origin[0])*scale, CENTER[1]+(v[1]-origin[1])*scale]
    mapped_base = [transform(v) for v in footprint]
    collar = [[CENTER[i]+(p[i]-CENTER[i])*COLLAR_SCALE for i in (0,1)] for p in mapped_base]
    mapped = [{**p,'points':[transform(v) for v in p['points']]} for p in adjusted]
    points = [v for p in mapped for v in p['points']]
    clearance = min(edge_clearance(v,POOL_INNER[i],POOL_INNER[(i+1)%4]) for v in collar for i in range(4))
    return {'polygons':mapped,'route':[transform(v) for v in route],
            'footprint':mapped_base,'collar':collar,'anchor':list(CENTER),
            'poolInner':POOL_INNER,'poolOuter':POOL_OUTER,
            'bounds':[min(v[0] for v in points),min(v[1] for v in points),max(v[0] for v in points),max(v[1] for v in points)],
            'clearance':clearance,'minWallGap':min_wall_gap*scale,
            'scale':scale,'baseOffset':offset,'shellDepth':shell_depth*scale}

