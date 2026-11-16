"""Expand the imagery-inferred villa grid for 万顺·帝景天成 into review records.

Input is a manual reading of the AMap z18 satellite mosaic (GCJ-02 inverted to
WGS84). Nothing here is a survey: every footprint carries
geometrySource='imagery-reconstructed-villa-row' and the reference limitations.
The OSM landuse boundary is reused as-is and only clips generated geometry.
"""
import json, math, runpy
from pathlib import Path
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
frame = runpy.run_path(str(ROOT / 'tools/enrich-shuyang-buildings.py'))
LAT, LON, KX, KY = frame['LAT'], frame['LON'], frame['KX'], frame['KY']


def lonlat(x, z):
    return LON + x / KX, LAT - z / KY


def band(poly, z, pad=80):
    lo = box(poly.bounds[0] - pad, z - .2, poly.bounds[2] + pad, z + .2).intersection(poly)
    return (lo.bounds[0], lo.bounds[2]) if not lo.is_empty else None


def main():
    trace = json.loads((DATA / 'wanshun-imagery-traces.json').read_text(encoding='utf-8'))
    ref = trace['reference']
    district = Polygon(trace['district']['boundary'])
    assert district.is_valid, 'district boundary'
    grid = trace['villaRows']
    width, gap, depth = grid['unitWidth'], grid['unitGap'], grid['rowDepth']
    inset = grid['insetFromBoundary']
    inner = district.buffer(-inset)
    lane_shapes = [LineString(l['pts']).buffer(l['width'] / 2, cap_style='flat', join_style='round')
                   for l in trace['lanes']]
    cross_width = trace['crossLaneWidth']
    cross = []
    for z in grid['rows']:
        cz = z + trace['crossLaneOffset']
        span = band(inner, cz)
        if not span:
            continue
        cross.append(LineString([(span[0] - 1, cz), (span[1] + 1, cz)]).buffer(cross_width / 2, cap_style='flat'))
    # Roads only need a hairline margin; generated villas need a real stand-off.
    road_block = unary_union(lane_shapes + cross).buffer(.8)
    building_block = unary_union([Polygon(b['ring']) for b in trace['buildings']]).buffer(grid['overlapRadius'])
    blocked = unary_union([road_block, building_block])

    features, audit = [], {'rows': len(grid['rows']), 'candidates': 0, 'kept': 0, 'clipped': 0,
                           'droppedEdge': 0, 'droppedRoad': 0, 'droppedOverlap': 0, 'areaM2': 0}
    for z in grid['rows']:
        span = band(inner, z + depth / 2)
        if not span:
            continue
        x = grid['originX']
        col = 0
        while x + width <= span[1] + .001:
            if x >= span[0] - .001:
                audit['candidates'] += 1
                cell = box(x, z, x + width, z + depth)
                clipped = cell.intersection(inner)
                if clipped.is_empty or clipped.area < 120:
                    audit['droppedEdge'] += 1
                elif clipped.intersects(blocked):
                    audit['droppedRoad'] += 1
                else:
                    if abs(clipped.area - cell.area) > .5:
                        audit['clipped'] += 1
                    ident = f"reviewed/wanshun/villa/{z}-{col}"
                    features.append({
                        'type': 'Feature',
                        'geometry': {'type': 'Polygon', 'coordinates': [[list(lonlat(px, pz)) for px, pz in clipped.exterior.coords]]},
                        'properties': {
                            'id': ident, 'name': '', 'building': grid['building'],
                            'height': grid['height'], 'building:levels': grid['levels'],
                            'roof:shape': grid['roofShape'], 'roof:height': grid['roofHeight'],
                            'levelsEstimate': grid['levels'], 'communityContext': trace['district']['name'],
                            'geometrySource': 'imagery-reconstructed-villa-row',
                            'geometryAccuracyNote': (ref['limitations'] + ' 楼排按影像可见的行列与间距重建，'
                                                     '单体轮廓为同规格矩形，水平误差约 ±5 m，非实测轮廓。'),
                            'heightNote': grid['heightNote'],
                            'referenceImageDate': ref['imageAcquired'],
                            'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'],
                            'annual': False
                        }
                    })
                    audit['kept'] += 1
                    audit['areaM2'] += clipped.area
            x += width + gap
            col += 1
    for b in trace['buildings']:
        poly = Polygon(b['ring'])
        assert poly.is_valid, b['id']
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [[list(lonlat(px, pz)) for px, pz in poly.exterior.coords]]},
            'properties': {
                'id': f"reviewed/wanshun/{b['id']}", 'name': b['name'], 'building': b['building'],
                'height': b['height'], 'roof:shape': b['roofShape'], 'roof:height': b['roofHeight'],
                'levelsEstimate': b['levels'], 'communityContext': trace['district']['name'],
                'geometrySource': 'imagery-reviewed-outline',
                'geometryAccuracyNote': ref['limitations'] + ' ' + b['note'],
                'heightNote': '按单层大棚尺度推断，非测量高度。',
                'referenceImageDate': ref['imageAcquired'], 'referenceId': ref['id'],
                'referenceRetrievedAt': ref['retrievedAt']
            }
        })
    audit['kept'] += len(trace['buildings'])

    out = {'type': 'FeatureCollection',
           'reference': ref, 'additionalReferences': [],
           'district': {k: trace['district'][k] for k in ('id', 'name', 'boundarySource')} | {'boundary': trace['district']['boundary']},
           'features': features}
    (DATA / 'reviewed-wanshun-buildings.geojson').write_text(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

    surfaces = []
    for lane in trace['lanes']:
        g = LineString(lane['pts']).buffer(lane['width'] / 2, cap_style='flat', join_style='round').intersection(inner)
        surfaces.append({
            'id': f"reviewed/wanshun/{lane['id']}", 'kind': 'community-path', 'name': '',
            'sourceSiteId': 'reviewed/wanshun',
            'rings': [[list(p) for p in g.exterior.coords]],
            'widthEstimate': lane['width'],
            'geometryMethod': 'imagery-inferred-route-centreline; GCJ-02 inverted to WGS84; clipped to OSM plot',
            'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
        })
    for i, (z, shape) in enumerate(zip(grid['rows'], cross)):
        surfaces.append({
            'id': f"reviewed/wanshun/cross-{z}", 'kind': 'community-path', 'name': '',
            'sourceSiteId': 'reviewed/wanshun',
            'rings': [[list(p) for p in shape.intersection(inner).exterior.coords]],
            'widthEstimate': cross_width,
            'geometryMethod': 'imagery-inferred-row-access; GCJ-02 inverted to WGS84; clipped to OSM plot',
            'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
        })
    lane_union = unary_union([LineString(s['rings'][0]).buffer(0) for s in surfaces])
    bands = trace['greenBands']
    for z in grid['rows']:
        g = box(district.bounds[0] - 10, z + bands['fromOffset'], district.bounds[2] + 10,
                z + bands['toOffset']).intersection(inner)
        if g.is_empty or g.area < 80:
            continue
        g = g.difference(lane_union.buffer(1.2))
        if g.is_empty:
            continue
        for j, part in enumerate(getattr(g, 'geoms', [g])):
            surfaces.append({
                'id': f"reviewed/wanshun/garden-{z}-{j}", 'kind': 'green', 'name': '',
                'sourceSiteId': 'reviewed/wanshun',
                'rings': [[list(p) for p in part.exterior.coords]],
                'geometryMethod': 'imagery-inferred courtyard band; GCJ-02 inverted to WGS84; clipped to OSM plot',
                'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'], 'imageAcquired': None
            })
    (DATA / 'wanshun-reviewed-surfaces.json').write_text(
        json.dumps({'reference': ref, 'surfaces': surfaces}, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8')
    audit['surfaces'] = len(surfaces)
    audit['districtAreaM2'] = round(district.area)
    audit['footprintRatio'] = round(audit['areaM2'] / district.area, 3)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
