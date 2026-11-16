"""Audit the 0–500/1000/1500/2000 m rings around 万顺·帝景天成 for empty ground.

Three questions, answered per OSM landuse polygon at 100 m granularity:

* 有地块但无建筑 — building footprint covers < 12 % of the cell;
* 建筑与影像明显不符 — a cell whose recorded footprints are all much larger
  than a typical roof run (coarse merged massing), flagged separately;
* 有路网但内部无通道 — a cell with footprints but no residential/service way
  crossing the plot, i.e. no internal access lane.

Run: python tools/audit-imagery-rings.py [--json docs/refinement/ring-audit.json]
"""
import argparse, gzip, json, math
from pathlib import Path
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from shapely import make_valid
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
LAT, LON, KX, KY = 34.1285, 118.7740, 92150.088, 110574
CENTER = (898.4, 2146.6)   # 万顺·帝景天成地块中心（与 build-wanshun-imagery.py 同源）
CELL = 100
RINGS = [(0, 0, 500), (1, 500, 1000), (2, 1000, 1500), (3, 1500, 2000), (4, 2000, 2500)]
INNER_LANES = ('residential', 'service', 'unclassified', 'living_street')


def world(lon, lat):
    return ((lon - LON) * KX, -(lat - LAT) * KY)


def ring_of(x, z):
    d = math.hypot(x - CENTER[0], z - CENTER[1])
    for r, lo, hi in RINGS:
        if lo <= d < hi:
            return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='docs/refinement/ring-audit.json')
    args = ap.parse_args()

    plots = []
    for e in json.loads((DATA / 'osm_land.json').read_text(encoding='utf-8'))['elements']:
        use = e.get('tags', {}).get('landuse')
        if use not in ('residential', 'commercial', 'retail', 'industrial'):
            continue
        if e.get('type') != 'way' or len(e.get('geometry') or []) < 4:
            continue
        pts = [world(p['lon'], p['lat']) for p in e['geometry']]
        g = make_valid(Polygon(pts))
        if not g.is_empty and g.area >= 500:
            plots.append({'id': f"way/{e['id']}", 'name': e.get('tags', {}).get('name', ''),
                          'use': use, 'g': g})

    rows = json.loads(gzip.decompress((DATA / 'buildings-enriched.json.gz').read_bytes()).decode('utf-8'))
    hidden = set((rows.get('report', {}).get('reviewedImagery') or {}).get('supersededSourceIds', []))
    rows = rows['buildings']
    footprints, sources, areas, cats = [], [], [], []
    for r in rows:
        # Superseded massing is hidden in the renderer and the map, so it must not
        # count as coverage here either.
        if r['id'] in hidden:
            continue
        for p in r['polygons']:
            g = Polygon(p['outer'], p['holes'])
            if g.is_valid and g.area > 0:
                footprints.append(g)
                sources.append(r['source'])
                areas.append(g.area)
                cats.append(r.get('category', 'unknown'))
    tree = STRtree(footprints)

    lanes = []
    for e in json.loads((DATA / 'osm_roads.json').read_text(encoding='utf-8'))['elements']:
        if e.get('type') != 'way' or len(e.get('geometry') or []) < 2:
            continue
        if e.get('tags', {}).get('highway') not in INNER_LANES:
            continue
        lanes.append(LineString([world(p['lon'], p['lat']) for p in e['geometry']]))
    mapped = len(lanes)
    # Inferred internal lanes (reviewed surfaces) count too, tagged so the report
    # never presents them as surveyed roads.
    reviewed = DATA / 'reviewed-district-surfaces.json'
    grounds = []
    if reviewed.exists():
        for s in json.loads(reviewed.read_bytes())['surfaces']:
            if s.get('kind') == 'community-path' and s.get('rings'):
                lanes.append(LineString(s['rings'][0]))
            # Deliberately building-free ground read from the imagery (courtyard
            # green, river bank, farmland, paved parking court). Counted separately
            # from empty land.
            if s.get('kind') in ('green', 'farmland', 'parking') and s.get('rings'):
                for r in s['rings']:
                    g = make_valid(Polygon(r))
                    if not g.is_empty:
                        grounds.append(g)
    lane_tree = STRtree(lanes)
    ground_tree = STRtree(grounds) if grounds else None

    stats = {r: {'cells': 0, 'empty': 0, 'emptyAreaM2': 0, 'surfaced': 0, 'coarse': 0, 'noLane': 0,
                 'mappedLane': 0, 'inferredLane': 0} for r, _, _ in RINGS}
    empty_cells, no_lane_cells, coarse_cells = [], [], []
    for p in plots:
        minx, miny, maxx, maxy = p['g'].bounds
        for gx in range(int(minx // CELL) * CELL, int(maxx) + 1, CELL):
            for gz in range(int(miny // CELL) * CELL, int(maxy) + 1, CELL):
                clip = p['g'].intersection(box(gx, gz, gx + CELL, gz + CELL))
                if clip.is_empty or clip.area < CELL * CELL * .4:
                    continue
                rp = clip.representative_point()
                ring = ring_of(rp.x, rp.y)
                if ring is None:
                    continue
                idx = [int(i) for i in tree.query(clip)]
                covered = unary_union([footprints[i].intersection(clip) for i in idx]).area if idx else 0
                ratio = covered / clip.area
                ground_ratio = 0.0
                if ground_tree is not None:
                    gidx = [int(i) for i in ground_tree.query(clip)]
                    if gidx:
                        ground_ratio = unary_union([grounds[i].intersection(clip) for i in gidx]).area / clip.area
                has_lane = len(lane_tree.query(clip)) > 0
                mapped_lane = any(int(i) < mapped for i in lane_tree.query(clip))
                stats[ring]['cells'] += 1
                cell = {'x': gx, 'z': gz, 'plot': p['id'], 'name': p['name'], 'use': p['use'],
                        'areaM2': round(clip.area), 'coverage': round(ratio, 3),
                        'groundCoverage': round(ground_ratio, 3),
                        'sources': sorted({sources[i] for i in idx}),
                        'internalLane': 'mapped' if mapped_lane else ('inferred' if has_lane else False)}
                if ratio < .12 and ground_ratio < .4:
                    stats[ring]['empty'] += 1
                    stats[ring]['emptyAreaM2'] += round(clip.area)
                    empty_cells.append({**cell, 'ring': ring})
                elif ratio < .12:
                    # Covered by imagery-read green/farmland, not a bare gap.
                    stats[ring]['surfaced'] += 1
                else:
                    if mapped_lane:
                        stats[ring]['mappedLane'] += 1
                    if has_lane:
                        stats[ring]['inferredLane'] += 1
                    if not has_lane:
                        stats[ring]['noLane'] += 1
                        no_lane_cells.append({**cell, 'ring': ring})
                    # Coarse massing: residential/unknown footprints in the cell are all
                    # over 2,500 m2. A single 6-storey slab (80 x 15 m) is ~1,200 m2 and
                    # matches the imagery, while a mall or factory is legitimately large,
                    # so only housing-type categories are flagged.
                    if idx and min(areas[i] for i in idx) > 2500 and all(cats[i] in ('residential', 'house', 'unknown') for i in idx):
                        stats[ring]['coarse'] += 1
                        coarse_cells.append({**cell, 'ring': ring, 'minAreaM2': round(min(areas[i] for i in idx))})

    report = {
        'center': list(CENTER),
        'cellMeters': CELL,
        'method': 'OSM landuse cells (100 m) inside 4 rings; coverage from merged building footprints; '
                  'internal lane = OSM residential/service/unclassified/living_street way or an imagery-inferred '
                  'community-path crossing the cell; surfaced = imagery-read green/farmland/parking ground.',
        'rings': [{'ring': r, 'fromM': lo, 'toM': hi,
                   **{k: (round(v) if isinstance(v, float) else v) for k, v in stats[r].items()}}
                  for r, lo, hi in RINGS],
        'emptyCells': sorted(empty_cells, key=lambda c: (c['ring'], c['z'], c['x'])),
        'noInternalLaneCells': sorted(no_lane_cells, key=lambda c: (c['ring'], c['z'], c['x'])),
        'coarseMassingCells': sorted(coarse_cells, key=lambda c: (c['ring'], c['z'], c['x'])),
    }
    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'rings': report['rings'], 'emptyCells': len(empty_cells),
                      'noLaneCells': len(no_lane_cells), 'coarseCells': len(coarse_cells)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
