"""Expand the ring-by-ring imagery reading into review records.

Reads tools/data/shuyang/imagery-districts-traces.json (row pitches, tilts,
internal lanes and exclusions read from the AMap z18 mosaic) and writes
reviewed footprint/surface files. Nothing here is a survey: every generated
footprint is flagged geometrySource='imagery-reconstructed-row-block' and only
fills space that no OSM/Overture/reviewed footprint already occupies.
"""
import json, math, runpy, gzip
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from shapely import make_valid, transform as transform_geometry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
frame = runpy.run_path(str(ROOT / 'tools/enrich-shuyang-buildings.py'))
LAT, LON, KX, KY = frame['LAT'], frame['LON'], frame['KX'], frame['KY']

# OSM highway tags carry no width in this extract; use the same class defaults
# as the road builder so generated rows never sit in a carriageway.
ROAD_HALF = {'motorway': 12, 'trunk': 11, 'primary': 10, 'secondary': 8, 'tertiary': 6,
             'residential': 3.5, 'living_street': 3, 'service': 2.5, 'unclassified': 3.5}


def lonlat(x, z):
    return LON + x / KX, LAT - z / KY


def world_ring(lonlat_ring):
    return [((lon - LON) * KX, -(lat - LAT) * KY) for lon, lat in lonlat_ring]


def closed_polygons(name, keep):
    out = []
    for e in json.loads((DATA / name).read_text(encoding='utf-8'))['elements']:
        if e.get('type') != 'way' or not e.get('geometry'):
            continue
        t = e.get('tags', {})
        if not keep(t):
            continue
        pts = [(p['lon'], p['lat']) for p in e['geometry']]
        if len(pts) < 4 or pts[0] != pts[-1]:
            continue
        g = make_valid(Polygon(pts))
        if not g.is_empty:
            out.append(g)
    return out


def load_masks():
    water = closed_polygons('osm_water.json', lambda t: t.get('natural') == 'water'
                            or bool(t.get('water')) or t.get('waterway') == 'riverbank')
    water_world = (transform_geometry(unary_union(water), lambda x, y: ((x - LON) * KX, -(y - LAT) * KY),
                                      interleaved=False) if water else Polygon())
    corridors = []
    for e in json.loads((DATA / 'osm_roads.json').read_text(encoding='utf-8'))['elements']:
        t = e.get('tags', {})
        half = ROAD_HALF.get(t.get('highway'))
        if not half or e.get('type') != 'way' or len(e.get('geometry') or []) < 2:
            continue
        pts = [((p['lon'] - LON) * KX, -(p['lat'] - LAT) * KY) for p in e['geometry']]
        corridors.append(LineString(pts).buffer(half + 1, cap_style='flat', join_style='round'))
    rows = json.loads(gzip.decompress((DATA / 'buildings-enriched.json.gz').read_bytes()).decode('utf-8'))['buildings']
    footprints = []
    for r in rows:
        # Never treat this generator's own previous output as surveyed context,
        # otherwise each rerun erodes the rows it just placed.
        if str(r['id']).startswith('reviewed/imagery/'):
            continue
        for p in r['polygons']:
            g = Polygon(p['outer'], p['holes'])
            if g.is_valid and g.area > 0:
                footprints.append(g)
    return water_world.buffer(4), unary_union(corridors).buffer(.5), unary_union(footprints).buffer(1.2)


def row_runs(inset, cx, cz, theta, reach, step=10):
    """Local-u intervals where the row centre line crosses the plot."""
    line = LineString([(cx + math.cos(theta) * u, cz + math.sin(theta) * u)
                       for u in range(-reach, reach + 1, step)])
    clipped = line.intersection(inset)
    runs = []
    for part in getattr(clipped, 'geoms', [clipped]):
        if part.geom_type != 'LineString' or part.length < 4:
            continue
        coords = list(part.coords)
        us = [(x - cx) * math.cos(theta) + (z - cz) * math.sin(theta) for x, z in coords]
        runs.append((min(us), max(us)))
    return runs


def main():
    trace = json.loads((DATA / 'imagery-districts-traces.json').read_text(encoding='utf-8'))
    ref = trace['reference']
    land = {str(e['id']): e for e in json.loads((DATA / 'osm_land.json').read_text(encoding='utf-8'))['elements']
            if e.get('type') == 'way'}
    water, roads, existing = load_masks()

    features, surfaces = [], []
    audit = {'districts': [], 'candidates': 0, 'kept': 0, 'droppedExisting': 0,
             'droppedRoad': 0, 'droppedWater': 0, 'droppedEdge': 0, 'droppedExclusion': 0}
    for d in trace['districts']:
        e = land.get(d['landuseId'].split('/')[-1])
        if not e:
            raise SystemExit('Missing landuse polygon ' + d['landuseId'])
        plot = make_valid(Polygon(world_ring([(p['lon'], p['lat']) for p in e['geometry']])))
        inset = plot.buffer(-2)
        theta = math.radians(d.get('tiltDegrees', 0))
        cx, cz0 = plot.centroid.x, plot.centroid.y
        radius = int(max(abs(plot.bounds[0] - cx), abs(plot.bounds[2] - cx),
                         abs(plot.bounds[1] - cz0), abs(plot.bounds[3] - cz0)) + 80)
        excl = [Polygon(x['ring']) for x in d.get('exclusions', [])]
        excluded = unary_union(excl).buffer(.5) if excl else Polygon()
        kept = 0
        for pat in d['patterns']:
            depth, width, gap = pat['depth'], pat['unitWidth'], pat['unitGap']
            i = 0
            while pat['startZ'] + i * pat['pitch'] <= pat['zTo'] + .001:
                cz = pat['startZ'] + i * pat['pitch']
                for s0, s1 in row_runs(inset, cx, cz, theta, radius):
                    u, col = s0 + 1, 0
                    while u + width <= s1 - .5:
                        audit['candidates'] += 1
                        local = [(u, -depth / 2), (u + width, -depth / 2),
                                 (u + width, depth / 2), (u, depth / 2)]
                        cell = Polygon([(cx + math.cos(theta) * x - math.sin(theta) * z,
                                         cz + math.sin(theta) * x + math.cos(theta) * z) for x, z in local])
                        clipped = make_valid(cell).intersection(inset)
                        if clipped.is_empty or clipped.area < 120:
                            audit['droppedEdge'] += 1
                        elif clipped.intersects(excluded):
                            audit['droppedExclusion'] += 1
                        else:
                            # Existing survey/Overture roofs win: subtract them instead of
                            # deleting the whole unit, so the rest of the row still fills in.
                            free = clipped.difference(existing).difference(water).difference(roads)
                            if free.is_empty or free.area < 90:
                                audit['droppedExisting'] += 1
                            for j, part in enumerate(getattr(free, 'geoms', [free])):
                                if part.geom_type != 'Polygon' or part.area < 90:
                                    continue
                                ident = f"reviewed/imagery/{d['id']}/{pat['id']}-{cz:.0f}-{col}" + (f'-{j}' if j else '')
                                features.append({
                                    'type': 'Feature',
                                    'geometry': {'type': 'Polygon', 'coordinates': [[
                                        [round(v, 8) for v in lonlat(px, pz)]
                                        for px, pz in part.exterior.coords]]},
                                    'properties': {
                                        'id': ident, 'name': '', 'building': pat['building'],
                                        'height': pat['height'], 'building:levels': pat['levels'],
                                        'roof:shape': pat['roofShape'], 'roof:height': pat['roofHeight'],
                                        'levelsEstimate': pat['levels'], 'communityContext': d['name'],
                                        'geometrySource': 'imagery-reconstructed-row-block',
                                        'geometryAccuracyNote': (ref['limitations'] + ' 楼排中心取影像亮度剖面峰值，'
                                                                 '朝向取地块内已有足迹最小外接矩形中位角，单体为同规格矩形并被已有足迹裁剪，'
                                                                 '水平误差约 ±6 m，非实测轮廓。'),
                                        'heightNote': pat['heightNote'],
                                        'referenceImageDate': ref['imageAcquired'],
                                        'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'],
                                    }
                                })
                                audit['kept'] += 1
                                kept += 1
                        u += width + gap
                        col += 1
                i += 1

        # Internal lanes: N-S spines read from the imagery plus an E-W access
        # lane every N rows, so the block is not a wall of buildings.
        lanes = list(d.get('lanes', []))
        for pat in d['patterns']:
            every = d.get('crossLaneEvery', 0)
            n = 1
            while every and pat['startZ'] + n * pat['pitch'] * every <= pat['zTo']:
                z = pat['startZ'] + (n * every - .5) * pat['pitch']
                x0, x1 = plot.bounds[0] - 25, plot.bounds[2] + 25
                lanes.append({'id': f"{pat['id']}-cross-{n}", 'width': d.get('crossLaneWidth', 5.5),
                              'pts': [[x0, z + math.tan(theta) * (x0 - cx)],
                                      [x1, z + math.tan(theta) * (x1 - cx)]]})
                n += 1
        lane_shapes = []
        for lane in lanes:
            g = LineString(lane['pts']).buffer(lane['width'] / 2, cap_style='flat', join_style='round')
            # A lane read between rows must not paint over a surveyed roof, so cut it
            # by the merged footprints instead of trusting the row estimate blindly.
            g = g.intersection(inset).difference(existing)
            if g.is_empty or g.area < 40:
                continue
            lane_shapes.append(g)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                surfaces.append({
                    'id': f"reviewed/imagery/{d['id']}/{lane['id']}" + (f'-{j}' if j else ''),
                    'kind': 'community-path', 'name': '', 'sourceSiteId': f"reviewed/imagery/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'widthEstimate': lane['width'],
                    'geometryMethod': 'imagery-inferred route centre line; GCJ-02 inverted to WGS84; clipped to OSM plot',
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        # Ground patches read off the imagery (parking court, shed yard, vegetable
        # plot, villa garden). Unlike exclusions these never delete a building; they
        # only paint free ground, so they can cover a whole cell safely.
        for gp in d.get('groundPatches', []):
            g = make_valid(Polygon(gp['ring'])).intersection(inset).difference(existing)
            kind = gp.get('kind', 'green')
            if kind not in ('green', 'parking', 'plaza'):
                kind = 'green'
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 120:
                    continue
                surfaces.append({
                    'id': f"reviewed/imagery/{d['id']}/ground-{gp['id']}" + (f'-{j}' if j else ''),
                    'kind': kind, 'landCover': gp.get('kind', 'green'),
                    'name': '', 'sourceSiteId': f"reviewed/imagery/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'geometryMethod': 'imagery-inferred paved/green ground; clipped to OSM plot and to existing roofs',
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        # Ground inside excluded areas stays building-free (courtyard garden, river
        # bank, farmland). Paint it as green so the block does not read as bare land.
        for x in d.get('exclusions', []):
            g = make_valid(Polygon(x['ring'])).intersection(inset)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 200:
                    continue
                # Parking courts and yards are paved, not garden; keep the ground
                # kind so the renderer draws asphalt instead of grass.
                kind = x.get('kind', 'green')
                if kind not in ('green', 'parking', 'plaza'):
                    kind = 'green'
                surfaces.append({
                    'id': f"reviewed/imagery/{d['id']}/excluded-{x['id']}" + (f'-{j}' if j else ''),
                    'kind': kind, 'landCover': x.get('kind', 'green'),
                    'name': '', 'sourceSiteId': f"reviewed/imagery/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'geometryMethod': 'imagery-inferred non-building ground; kept clear during row reconstruction',
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        lane_union = unary_union(lane_shapes).buffer(.5) if lane_shapes else Polygon()
        bands = d.get('greenBands')
        if bands:
            for pat in d['patterns']:
                z = pat['startZ'] + 1
                while z <= pat['zTo']:
                    g = box(plot.bounds[0] - 10, z + bands['fromOffset'], plot.bounds[2] + 10,
                            z + bands['toOffset']).intersection(inset)
                    z += pat['pitch']
                    if g.is_empty or g.area < 60:
                        continue
                    g = g.difference(lane_union).difference(excluded)
                    for j, part in enumerate(getattr(g, 'geoms', [g])):
                        if part.geom_type != 'Polygon' or part.area < 30:
                            continue
                        surfaces.append({
                            'id': f"reviewed/imagery/{d['id']}/garden-{pat['id']}-{int(z)}-{j}", 'kind': 'green',
                            'name': '', 'sourceSiteId': f"reviewed/imagery/{d['id']}",
                            'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                            'geometryMethod': 'imagery-inferred courtyard band; GCJ-02 inverted to WGS84; clipped to OSM plot',
                            'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                        })
        audit['districts'].append({'id': d['id'], 'name': d['name'], 'landuseId': d['landuseId'],
                                   'plotAreaM2': round(plot.area), 'kept': kept})
    out = {'type': 'FeatureCollection', 'reference': ref, 'additionalReferences': [],
           'districts': [{'id': d['id'], 'name': d['name'], 'landuseId': d['landuseId']}
                         for d in trace['districts']],
           'features': features}
    (DATA / 'reviewed-imagery-districts.geojson').write_text(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (DATA / 'imagery-districts-surfaces.json').write_text(
        json.dumps({'reference': ref, 'surfaces': surfaces}, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8')
    audit['surfaces'] = len(surfaces)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
