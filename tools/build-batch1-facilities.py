"""Build the batch-1 city-skeleton review layers from imagery readings.

Reads tools/data/shuyang/batch1-facility-traces.json (manual z18 satellite
reading) and writes three auditable artefacts:

* reviewed-batch1-buildings.geojson  - imagery-reviewed footprints + the OSM
  landuse polygons that must stop rendering as buildings.
* batch1-facility-surfaces.json      - tracks, infields and yard paving.
* batch1-massing-overrides.json      - name/category/height corrections for
  records that keep their surveyed geometry.

No random or procedural building generation: every footprint is either an
explicit ring in the traces file or a concentric-ring fit to a visible stadium
outline, and every inference carries its reference, date and error note.
"""
import hashlib, json, math, runpy, sys
from pathlib import Path
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
frame = runpy.run_path(str(ROOT / 'tools/enrich-shuyang-buildings.py'))
LAT, LON, KX, KY = frame['LAT'], frame['LON'], frame['KX'], frame['KY']
BATCH = sys.argv[1] if len(sys.argv) > 1 else 'batch1'
TRACES = DATA / f'{BATCH}-facility-traces.json'


def wgs(x, z):
    return [LON + x / KX, LAT - z / KY]


def ellipse(e, hole=False):
    n = e.get('segments', 40)
    rx, rz = (e['innerRx'], e['innerRz']) if hole else (e['rx'], e['rz'])
    return [[round(e['cx'] + rx * math.cos(2 * math.pi * i / n), 2),
             round(e['cz'] + rz * math.sin(2 * math.pi * i / n), 2)] for i in range(n)]


def main():
    data = json.loads(TRACES.read_text(encoding='utf-8'))
    ref = data['reference']
    ref_props = {'referenceId': ref['id'], 'referenceRetrievedAt': ref['retrievedAt'],
                 'referenceImageDate': ref['imageAcquired']}
    features, surfaces, overrides = [], [], []
    superseded, reasons = [], {}
    for fac in data['facilities']:
        prefix = f"reviewed/{BATCH}/{fac['id']}"
        for ex in fac.get('excludeSourceIds', []):
            superseded.append(ex['id'])
            reasons[ex['id']] = ex['reason']
        for b in fac['buildings']:
            ring = b.get('ring') or ellipse(b['ellipse'])
            holes = [ellipse(b['ellipse'], hole=True)] if 'innerRx' in b.get('ellipse', {}) else []
            # 建筑层与 reviewed 其它批一致，落盘为 WGS84 经纬度；地表 rings 仍是项目米制。
            poly = Polygon([wgs(x, z) for x, z in ring],
                           [[wgs(x, z) for x, z in h] for h in holes])
            assert poly.is_valid, b['id']
            props = {'id': f"{prefix}/{b['id']}", 'name': b['name'], 'building': b['category'],
                     'height': b['height'], 'building:levels': b['levels'], 'levelsEstimate': b['levels'],
                     'roof:shape': b['roofShape'], 'roof:height': b['roofHeight'],
                     'geometrySource': b['geometrySource'],
                     'geometryAccuracyNote': b['geometryAccuracyNote'],
                     'heightNote': b['heightNote'], 'note': b.get('note', ''),
                     'facilityGroup': fac['group'], **ref_props}
            features.append({'type': 'Feature', 'geometry': mapping(poly), 'properties': props})
        for s in fac['surfaces']:
            if 'ellipse' in s:
                rings = [ellipse(s['ellipse'])] + ([ellipse(s['ellipse'], True)] if 'innerRx' in s['ellipse'] else [])
            else:
                rings = [s['ring']]
            surfaces.append({'id': f"{prefix}/{s['id']}", 'kind': s['kind'], 'name': s['name'],
                             'sourceSiteId': prefix, 'rings': rings,
                             'geometryMethod': s['geometryMethod'], 'note': s['note'],
                             'imageAcquired': ref['imageAcquired'], **ref_props,
                             **({'widthEstimate': s['widthEstimate']} if 'widthEstimate' in s else {})})
        for o in fac.get('overrides', []):
            overrides.append({**o, 'facilityId': fac['id'], 'facilityName': fac['name'],
                              'facilityGroup': fac['group'], **ref_props})
    out = {'type': 'FeatureCollection', 'reference': ref,
           'additionalReferences': [], 'traceSha256': hashlib.sha256(TRACES.read_bytes()).hexdigest(),
           'supersededSourceIds': superseded, 'supersededReasons': reasons,
           'nonBuildingExclusionIds': superseded, 'features': features}
    (DATA / f'reviewed-{BATCH}-buildings.geojson').write_text(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (DATA / f'{BATCH}-facility-surfaces.json').write_text(
        json.dumps({'reference': ref, 'referenceId': ref['id'],
                    'referenceRetrievedAt': ref['retrievedAt'],
                    'imageAcquired': ref['imageAcquired'],
                    'reviewNote': data.get('surfaceReview', ''),
                    'surfaces': surfaces}, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (DATA / f'{BATCH}-massing-overrides.json').write_text(
        json.dumps({'reference': ref, 'overrides': overrides}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'footprints': len(features), 'surfaces': len(surfaces), 'overrides': len(overrides),
                      'excludedSourceRecords': superseded,
                      'notDone': len(data.get('notDoneFacilities', []))}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
