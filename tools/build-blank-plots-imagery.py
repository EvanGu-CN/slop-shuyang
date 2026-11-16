"""Expand the 批2 空地补全 imagery reading into review records.

Reads tools/data/shuyang/blank-plots-imagery-traces.json (15 plots that had an
OSM plot boundary but no local buildings: 12 residential plots + 3 schools) and
writes reviewed footprint/surface files. Nothing here is a survey: generated
footprints are flagged geometrySource='imagery-reconstructed-row-block' or
'imagery-reconstructed-footprint', clipped to the OSM plot, and kept clear of
OSM water, road corridors and existing survey/Overture footprints.
"""
import json, math, runpy, gzip
from pathlib import Path
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from shapely import make_valid, transform as transform_geometry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
frame = runpy.run_path(str(ROOT / 'tools/enrich-shuyang-buildings.py'))
LAT, LON, KX, KY = frame['LAT'], frame['LON'], frame['KX'], frame['KY']

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


def footprint_feature(ident, g, props):
    return {'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [[
                [round(v, 8) for v in lonlat(px, pz)] for px, pz in g.exterior.coords]]},
            'properties': dict(props, id=ident)}


def main():
    trace = json.loads((DATA / 'blank-plots-imagery-traces.json').read_text(encoding='utf-8'))
    ref = trace['reference']
    boundaries = {}
    for f in ('osm_land.json', 'osm_school_grounds.json'):
        for e in json.loads((DATA / f).read_text(encoding='utf-8'))['elements']:
            if e.get('type') == 'way' and e.get('geometry'):
                boundaries[(f, str(e['id']))] = e
    water, roads, existing = load_masks()

    features, surfaces, districts = [], [], []
    audit = {'districts': [], 'candidates': 0, 'kept': 0, 'keptExplicit': 0, 'droppedExisting': 0,
             'droppedRoad': 0, 'droppedWater': 0, 'droppedEdge': 0, 'droppedExclusion': 0, 'surfaces': 0}
    for d in trace['districts']:
        e = boundaries.get((d['boundaryFile'], d['landuseId'].split('/')[-1]))
        if not e:
            raise SystemExit(f"Missing boundary {d['boundaryFile']} {d['landuseId']}")
        ring_wgs = [(p['lon'], p['lat']) for p in e['geometry']]
        plot = make_valid(Polygon(world_ring(ring_wgs)))
        inset = plot.buffer(-2)
        theta = math.radians(d.get('tiltDegrees', 0))
        cx, cz0 = plot.centroid.x, plot.centroid.y
        radius = int(max(abs(plot.bounds[0] - cx), abs(plot.bounds[2] - cx),
                         abs(plot.bounds[1] - cz0), abs(plot.bounds[3] - cz0)) + 80)
        excl = [Polygon(x['ring']) for x in d.get('exclusions', [])]
        excluded = unary_union(excl).buffer(.5) if excl else Polygon()
        common = {
            'name': '', 'communityContext': d['name'],
            'geometryAccuracyNote': ref['limitations'],
            'referenceImageDate': ref['imageAcquired'], 'referenceId': ref['id'],
            'referenceRetrievedAt': ref['retrievedAt'],
        }
        kept = 0
        for pat in d.get('patterns', []):
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
                            free = clipped.difference(existing).difference(water).difference(roads)
                            if free.is_empty or free.area < 90:
                                audit['droppedExisting'] += 1
                            for j, part in enumerate(getattr(free, 'geoms', [free])):
                                if part.geom_type != 'Polygon' or part.area < 90:
                                    continue
                                ident = f"reviewed/imagery/blank/{d['id']}/{pat['id']}-{cz:.0f}-{col}" + (f'-{j}' if j else '')
                                features.append(footprint_feature(ident, part, dict(common, **{
                                    'building': pat['building'], 'height': pat['height'],
                                    'building:levels': pat['levels'], 'roof:shape': pat['roofShape'],
                                    'roof:height': pat['roofHeight'], 'levelsEstimate': pat['levels'],
                                    'geometrySource': 'imagery-reconstructed-row-block',
                                    'geometryAccuracyNote': (ref['limitations'] + ' 单体为同规格矩形，'
                                                             '按影像可见的行列、间距与单体长度重建，被边界与既有足迹裁剪，'
                                                             '水平误差约 ±6 m，非实测轮廓。'),
                                    'heightNote': pat['heightNote'],
                                })))
                                audit['kept'] += 1
                                kept += 1
                        u += width + gap
                        col += 1
                i += 1
        for b in d.get('buildings', []):
            g = make_valid(Polygon(b['ring'])).intersection(inset)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 12:
                    continue
                ident = f"reviewed/imagery/blank/{d['id']}/{b['id']}" + (f'-{j}' if j else '')
                features.append(footprint_feature(ident, part, dict(common, **{
                    'building': b['building'], 'height': b['height'],
                    'building:levels': b['levels'], 'roof:shape': b['roofShape'],
                    'roof:height': b['roofHeight'], 'levelsEstimate': b['levels'],
                    'geometrySource': 'imagery-reconstructed-footprint',
                    'geometryAccuracyNote': (ref['limitations'] + ' 单体按影像可见屋面逐栋描边，'
                                             '非实测轮廓，水平误差约 ±6 m。'),
                    'heightNote': b.get('note', '') + ' 高度为屋面形态与体量推断，非测量值。',
                })))
                audit['keptExplicit'] += 1
                kept += 1

        lanes = list(d.get('lanes', []))
        for pat in d.get('patterns', []):
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
            g = g.intersection(inset)
            if g.is_empty or g.area < 40:
                continue
            lane_shapes.append(g)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                surfaces.append({
                    'id': f"reviewed/imagery/blank/{d['id']}/{lane['id']}" + (f'-{j}' if j else ''),
                    'kind': 'community-path', 'name': '', 'sourceSiteId': f"reviewed/imagery/blank/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'widthEstimate': lane['width'],
                    'geometryMethod': 'imagery-inferred route centre line; GCJ-02 inverted to WGS84; clipped to OSM plot',
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        for x in d.get('exclusions', []):
            g = make_valid(Polygon(x['ring'])).intersection(inset)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 200:
                    continue
                surfaces.append({
                    'id': f"reviewed/imagery/blank/{d['id']}/excluded-{x['id']}" + (f'-{j}' if j else ''),
                    'kind': x.get('kind', 'green'), 'name': '', 'sourceSiteId': f"reviewed/imagery/blank/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'geometryMethod': f"imagery-inferred non-building ground ({x['reason']})",
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        for gdef in d.get('greens', []):
            g = make_valid(Polygon(gdef['ring'])).intersection(inset)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 60:
                    continue
                surfaces.append({
                    'id': f"reviewed/imagery/blank/{d['id']}/green-{gdef['id']}" + (f'-{j}' if j else ''),
                    'kind': 'green', 'name': '', 'sourceSiteId': f"reviewed/imagery/blank/{d['id']}",
                    'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                    'geometryMethod': 'imagery-inferred courtyard/lawn boundary; clipped to OSM plot',
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        for s in d.get('surfaces', []):
            g = make_valid(Polygon(s['ring'], s.get('holes', []))).intersection(inset)
            for j, part in enumerate(getattr(g, 'geoms', [g])):
                if part.geom_type != 'Polygon' or part.area < 60:
                    continue
                rings = [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]]
                rings += [[[round(p[0], 1), round(p[1], 1)] for p in r.coords] for r in part.interiors]
                surfaces.append({
                    'id': f"reviewed/imagery/blank/{d['id']}/surface-{s['id']}" + (f'-{j}' if j else ''),
                    'kind': s['kind'], 'name': '', 'sourceSiteId': f"reviewed/imagery/blank/{d['id']}",
                    'rings': rings,
                    'geometryMethod': s.get('method', 'imagery-inferred playing field / hardstand boundary; clipped to OSM plot'),
                    'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                })
        lane_union = unary_union(lane_shapes).buffer(.5) if lane_shapes else Polygon()
        bands = d.get('greenBands')
        if bands:
            for pat in d.get('patterns', []):
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
                            'id': f"reviewed/imagery/blank/{d['id']}/garden-{pat['id']}-{int(z)}-{j}",
                            'kind': 'green', 'name': '',
                            'sourceSiteId': f"reviewed/imagery/blank/{d['id']}",
                            'rings': [[[round(p[0], 1), round(p[1], 1)] for p in part.exterior.coords]],
                            'geometryMethod': 'imagery-inferred courtyard band; GCJ-02 inverted to WGS84; clipped to OSM plot',
                            'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
                        })
        districts.append({
            'id': d['id'], 'sid': d['sid'], 'name': d['name'], 'landuseId': d['landuseId'],
            'boundaryFile': d['boundaryFile'], 'boundarySource': d['boundarySource'],
            'boundary': [[round(v, 1) for v in p] for p in world_ring(ring_wgs)],
            'plotAreaM2': round(plot.area), 'note': d['note'],
            'typeConflict': bool(d.get('reading', {}).get('typeConflict')),
            'unresolved': d.get('reading', {}).get('unresolved', ''),
        })
        audit['districts'].append({'id': d['id'], 'sid': d['sid'], 'name': d['name'],
                                   'plotAreaM2': round(plot.area), 'kept': kept})

    out = {'type': 'FeatureCollection', 'reference': ref, 'additionalReferences': [],
           'districts': districts, 'features': features}
    (DATA / 'reviewed-blank-plots.geojson').write_text(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (DATA / 'blank-plots-surfaces.json').write_text(
        json.dumps({'reference': ref, 'surfaces': surfaces}, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8')
    audit['surfaces'] = len(surfaces)
    audit['features'] = len(features)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
