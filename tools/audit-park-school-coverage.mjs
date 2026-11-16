// Park & school inventory for the photo-guided interior refinement goal.
// Parks use mapped land polygons; schools have no mapped campus polygons in this
// snapshot, so their boundaries are listed explicitly as verified or missing.
// Counts describe mapped source geometry, not a claim that every surface is restored.
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {GEO} from '../js/shuyang-geodata.js';
import {ROADS, ISLAND_BOUNDS} from '../js/city-config.js';

const root = new URL('../', import.meta.url);
const source = JSON.parse(gunzipSync(readFileSync(new URL('tools/data/shuyang/buildings-enriched.json.gz', root)))).buildings;
const pois = JSON.parse(readFileSync(new URL('tools/data/shuyang/osm_pois.json', root), 'utf8')).elements;

const inFrame = (x, z) => x > ISLAND_BOUNDS.minX && x < ISLAND_BOUNDS.maxX && z > ISLAND_BOUNDS.minZ && z < ISLAND_BOUNDS.maxZ;
const toPairs = (flat) => {
  const out = [];
  for (let i = 0; i + 1 < flat.length; i += 2) out.push([flat[i], flat[i + 1]]);
  return out;
};
const ringArea = (ring) => {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) a += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
  return Math.abs(a / 2);
};
const pointInRing = (ring, x, z) => {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, az] = ring[i], [bx, bz] = ring[j];
    if ((az > z) !== (bz > z) && x < ((bx - ax) * (z - az)) / (bz - az) + ax) inside = !inside;
  }
  return inside;
};
const footprint = (b) => b.polygons.flatMap((p) => p.outer.map(([x, z]) => [x, z]));
const centroid = (pts) => {
  let x = 0, z = 0;
  for (const p of pts) { x += p[0]; z += p[1]; }
  return [x / pts.length, z / pts.length];
};

// World coordinates are x east / z south, so OSM lon/lat convert like the generator.
const LAT0 = 34.1285, LON0 = 118.7740;
const KX = 111320 * Math.cos((LAT0 * Math.PI) / 180), KY = 110574;
const toWorld = (lon, lat) => [(lon - LON0) * KX, -(lat - LAT0) * KY];

const buildings = source.map((b, index) => {
  const pts = footprint(b);
  const [x, z] = centroid(pts);
  return {index, id: b.id, name: b.name || '', height: b.height, x, z, area: Math.round(ringArea(pts) * 10) / 10};
});

// ---- parks ------------------------------------------------------------------------------------------
const parks = GEO.parks.filter((p) => p.rings.length).map((p) => {
  const rings = p.rings.map(toPairs);
  const area = rings.reduce((s, r) => s + ringArea(r), 0);
  const inside = (x, z) => rings.some((r) => pointInRing(r, x, z));
  const parkBuildings = buildings.filter((b) => inside(b.x, b.z));
  const roads = ROADS.map((r, index) => ({index, r})).filter(({r}) => r.pts.some((q) => inside(q.x, q.z)))
    .map(({index, r}) => ({index, sourceWayId: GEO.roadSourceIds?.[index] || null, name: r.name, kind: r.kind, width: r.w}));
  const paths = (GEO.mapPaths || []).map(([name, kind, w, bridge, flat], index) => {
    let insideCount = 0, total = 0;
    for (let i = 0; i + 1 < flat.length; i += 2) {
      total++;
      if (inside(flat[i], flat[i + 1])) insideCount++;
    }
    return {index, name, kind, width: w, bridge: !!bridge, verticesInside: insideCount, vertices: total};
  }).filter((p) => p.verticesInside > 0);
  const pitches = GEO.landuse.filter((l) => l.kind === 'pitch').filter((l) => {
    const ring = toPairs(l.rings[0]);
    const [x, z] = centroid(ring);
    return inside(x, z);
  }).length;
  return {name: p.name || '(unnamed)', kind: p.kind, areaHa: Math.round(area / 100) / 100,
    buildings: parkBuildings.map(({index, id, name, height, area}) => ({index, id, name, height, area})),
    roads, paths, pitches};
});
parks.sort((a, b) => b.areaHa - a.areaHa);

// ---- schools ----------------------------------------------------------------------------------------
const schoolPois = pois.filter((e) => {
  const t = e.tags || {};
  return ['school', 'kindergarten', 'college', 'university'].includes(t.amenity);
}).map((e) => {
  const lon = e.lon ?? e.center?.lon, lat = e.lat ?? e.center?.lat;
  const [x, z] = toWorld(lon, lat);
  if (!Number.isFinite(x) || !Number.isFinite(z)) return null;
  return {id: e.id, name: (e.tags || {}).name || '', amenity: (e.tags || {}).amenity, x: Math.round(x), z: Math.round(z), inFrame: inFrame(x, z)};
}).filter((s) => s.inFrame);

// Campus extents: OSM school-ground polygons (out geom, 2026-11 snapshot) plus the two
// reviewed campus traces where the OSM outline is coarser than the reviewed one.
const grounds = GEO.schoolGrounds || [];
const reviewed = [];
for (const [file, name] of [['reviewed-shiyan-campus.json', '沭阳实验小学'], ['reviewed-mengxi-campus.json', '梦溪中学']]) {
  try {
    const j = JSON.parse(readFileSync(new URL('tools/data/shuyang/' + file, root), 'utf8'));
    if (Array.isArray(j.boundary)) reviewed.push({file, name, ring: j.boundary.map((p) => Array.isArray(p) ? p : [p.x, p.z])});
  } catch { /* snapshot without that campus */ }
}
for (const s of schoolPois) {
  const ground = grounds.find((g) => g.n === s.name) || grounds.find((g) => g.n.includes(s.name) || s.name.includes(g.n));
  const rb = reviewed.find((r) => s.name.trim() === r.name);
  const ring = rb?.ring || (ground ? toPairs(ground.r) : null);
  s.boundary = ring ? (rb ? 'reviewed' : 'osm-ground') : 'missing';
  s.boundarySource = rb ? `${rb.file}（名称匹配）` : ground ? 'OSM amenity=school 面（out geom）' : null;
  s.groundArea = ground ? ground.a : null;
  const radius = s.amenity === 'kindergarten' ? 90 : 150;
  const candidates = ring
    ? buildings.filter((b) => pointInRing(ring, b.x, b.z))
    : buildings.filter((b) => Math.hypot(b.x - s.x, b.z - s.z) <= radius);
  s.candidateBuildings = candidates.length;
  s.buildingBinding = ring ? 'inside-campus-outline' : 'proximity-only';
  s.localRoads = ROADS.filter((r) => r.pts.some((q) => Math.hypot(q.x - s.x, q.z - s.z) < radius)).length;
}

const report = {
  scope: 'Parks use mapped land polygons. Schools use mapped POIs; a missing boundary means no campus extent is verified, so no interior surface is asserted for that school.',
  parks: parks.map((p) => ({...p, buildingCount: p.buildings.length})),
  schools: schoolPois,
  totals: {
    parks: parks.length,
    parksWithBuildings: parks.filter((p) => p.buildings.length > 0).length,
    parkBuildings: parks.reduce((s, p) => s + p.buildings.length, 0),
    parkRoadSegments: parks.reduce((s, p) => s + p.roads.length, 0),
    parkPaths: parks.reduce((s, p) => s + p.paths.length, 0),
    schools: schoolPois.length,
    schoolsWithVerifiedBoundary: schoolPois.filter((s) => s.boundary !== 'missing').length,
    schoolGroundsMapped: grounds.length,
    schoolBuildingsInsideOutlines: schoolPois.filter((s) => s.buildingBinding === 'inside-campus-outline').reduce((n, s) => n + s.candidateBuildings, 0)
  }
};
mkdirSync(new URL('docs/refinement/', root), {recursive: true});
writeFileSync(new URL('docs/refinement/park-school-coverage.json', root), JSON.stringify(report, null, 2) + '\n');
console.log('parks', report.totals.parks, '| park buildings', report.totals.parkBuildings,
  '| park roads', report.totals.parkRoadSegments, '| park paths', report.totals.parkPaths,
  '| schools', report.totals.schools, '| verified school boundaries', report.totals.schoolsWithVerifiedBoundary);
for (const p of report.parks.filter((p) => p.name !== '(unnamed)').slice(0, 15)) {
  console.log(`${p.name.padEnd(10)} ${String(p.areaHa).padStart(7)}ha  buildings=${p.buildingCount} roads=${p.roads.length} paths=${p.paths.length} pitches=${p.pitches}`);
}
console.log('top schools by candidate buildings:');
for (const s of [...schoolPois].sort((a, b) => b.candidateBuildings - a.candidateBuildings).slice(0, 15)) {
  console.log(`  ${s.name.padEnd(20)} cand=${s.candidateBuildings} roads=${s.localRoads} boundary=${s.boundary}`);
}
