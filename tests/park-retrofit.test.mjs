import assert from 'node:assert/strict';
import test from 'node:test';
import {PARKS} from '../js/city-config.js';
import {PARK_RETROFIT_PATHS, PARK_RETROFIT_SUMMARY, PARK_RETROFIT_SKIPPED} from '../js/park-retrofit.js';

const inside = (ring, x, z) => {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a.z > z) !== (b.z > z) && x < ((b.x - a.x) * (z - a.z)) / (b.z - a.z) + a.x) hit = !hit;
  }
  return hit;
};
const parkRings = (name) => PARKS.filter((p) => p.name === name).flatMap((p) => p.rings);

test('every retrofit line carries a dated, sourced inference note', () => {
  assert.ok(PARK_RETROFIT_PATHS.length >= 6);
  for (const item of PARK_RETROFIT_PATHS) {
    assert.match(item.id, /^retrofit\//, item.id);
    assert.match(item.park, /[\u4e00-\u9fa5]/, item.id);
    assert.ok(['pedestrian', 'footpath', 'plaza'].includes(item.kind), `${item.id} kind`);
    assert.ok(item.evidence?.strength, `${item.id} strength`);
    assert.ok(item.evidence.source.length > 10, `${item.id} source`);
    assert.equal(item.evidence.fetched, '2026-11-15', `${item.id} fetch date`);
    assert.ok(item.evidence.note.length > 10, `${item.id} note`);
    assert.equal(item.building, undefined, `${item.id} must not add buildings`);
  }
});

test('retrofit lines stay inside their park outline', () => {
  // 沭河公园的多边形只覆盖河岸绿化带，实测的滨河步道贴着水边、位于多边形外侧
  // 约 30 m，因此允许"落在轮廓内或距轮廓 40 m 以内"，其余公园必须落在轮廓内。
  const ringDistance = (r, x, z) => {
    let best = Infinity;
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const a = r[i], b = r[j];
      const dx = b.x - a.x, dz = b.z - a.z;
      const t = Math.max(0, Math.min(1, ((x - a.x) * dx + (z - a.z) * dz) / (dx * dx + dz * dz || 1)));
      best = Math.min(best, Math.hypot(x - (a.x + dx * t), z - (a.z + dz * t)));
    }
    return best;
  };
  for (const item of PARK_RETROFIT_PATHS) {
    const rings = parkRings(item.park);
    assert.ok(rings.length, `${item.park} exists in PARKS`);
    const mid = item.kind === 'plaza' ? item.pts[0] : item.pts[Math.floor(item.pts.length / 2)];
    const ok = rings.some((r) => inside(r, mid[0], mid[1]))
      || (item.park === '沭河公园' && rings.some((r) => ringDistance(r, mid[0], mid[1]) < 40));
    assert.ok(ok, `${item.id} midpoint inside ${item.park}`);
  }
});

test('closed loops close and plazas carry a pad size', () => {
  for (const item of PARK_RETROFIT_PATHS) {
    if (item.kind === 'plaza') {
      assert.ok(item.pad.w > 0 && item.pad.d > 0, `${item.id} pad`);
      continue;
    }
    assert.ok(item.pts.length >= 2, `${item.id} points`);
    assert.ok(item.width >= 2 && item.width <= 9, `${item.id} width`);
    if (item.closed) {
      const a = item.pts[0], b = item.pts[item.pts.length - 1];
      assert.ok(Math.hypot(a[0] - b[0], a[1] - b[1]) < 0.5, `${item.id} closes`);
    }
  }
});

test('summary totals match the entries and skipped items explain themselves', () => {
  for (const row of PARK_RETROFIT_SUMMARY) {
    const items = PARK_RETROFIT_PATHS.filter((p) => p.park === row.park);
    assert.equal(row.paths + row.plazas, items.length, row.park);
    assert.ok(row.sources.length > 0);
  }
  assert.ok(PARK_RETROFIT_SKIPPED.length >= 3);
  for (const s of PARK_RETROFIT_SKIPPED) assert.ok(s.reason.length > 20, s.park);
});
