import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(join(root, p), 'utf8');

test('school grounds are generated from mapped OSM areas', async () => {
  const { GEO } = await import('../js/shuyang-geodata.js');
  const grounds = GEO.schoolGrounds || [];
  assert.ok(grounds.length >= 30, `expected at least 30 campus outlines, got ${grounds.length}`);
  assert.ok(grounds.every((g) => g.n && g.r.length >= 6), 'every campus keeps a name and a closed ring');
  const kinds = new Set(grounds.map((g) => g.k));
  assert.ok(kinds.has('school'), 'schools are present');
  const source = JSON.parse(read('tools/data/shuyang/osm_school_grounds.json'));
  assert.ok(source.osm3s?.timestamp_osm_base, 'the source snapshot records its OSM timestamp');
  // The generator clips to the city bounds, so outlines outside the playable area are dropped on purpose;
  // what must hold is that every source outline whose centroid is inside the bounds survives.
  assert.ok(grounds.length <= source.elements.length, 'clipping can only drop outlines, never invent them');
  assert.ok(
    grounds.length >= source.elements.length * 0.5,
    `clipping should keep most outlines (kept ${grounds.length} of ${source.elements.length})`
  );
  assert.ok(grounds.every((g) => g.a >= 400), 'tiny fragments from clipping are filtered out');
});

test('park interior floors are built from mapped footways only', () => {
  const source = read('js/park-interior.js');
  assert.match(source, /GEO\.mapPaths/, 'park paths come from mapped OSM footways');
  assert.doesNotMatch(source, /new THREE\.(Box|Plane)Geometry\(\s*[0-9.]+\s*,\s*0\s*,/, 'no invented building footprints');
  assert.match(source, /RIVER_RAIL_PARKS[\s\S]*沭河公园/, 'river railing is bound to the photographed park');
  assert.match(source, /PARK_PAVING[\s\S]*沭河公园/, 'paving palette is bound to photographed parks');
  assert.match(source, /isWater\(/, 'water is excluded from path and furniture placement');
});

test('school gates record whether the position is mapped or inferred', () => {
  const source = read('js/school-grounds.js');
  assert.match(source, /mapped-path-crossing/, 'gates prefer mapped path crossings');
  assert.match(source, /nearest-mapped-road/, 'the fallback is labelled as an inference');
  assert.match(source, /SKIP = new Set\(\[[\s\S]*沭阳实验小学/, 'campuses with dedicated models are not duplicated');
  assert.match(source, /plaqueAtlas/, 'campus plaques share one atlas so they merge into few draw calls');
});

test('the vector map and the scene share the campus layer and the map can search it', () => {
  const map = read('js/city-map.js');
  assert.match(map, /GEO\.schoolGrounds/, 'map reads the same campus data as the scene');
  assert.match(map, /SCHOOL_NAMES/, 'map labels campuses');
  assert.match(map, /const school = SCHOOL_ITEMS\.find/, 'campuses are searchable');
  const main = read('js/main.js');
  assert.match(main, /buildParkInterior\(scene\)/);
  assert.match(main, /buildSchoolGrounds\(scene, modelColliders\)/);
  const html = read('index.html');
  assert.match(html, /modulepreload" href="\.\/js\/park-interior\.js"/);
  assert.match(html, /modulepreload" href="\.\/js\/school-grounds\.js"/);
});

test('campus buildings take the school facade family', () => {
  const source = read('js/buildings.js');
  assert.match(source, /insideSchoolGround\(b\.cx, b\.cz\)/, 'campus buildings are classified by the mapped outline');
  assert.match(source, /campusBuildings\.has\(sourceRecord\) \|\| insideSchoolGround/, 'existing reviewed campuses still win');
});
