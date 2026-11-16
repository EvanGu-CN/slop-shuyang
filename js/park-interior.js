import * as THREE from 'three/webgpu';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { PARKS, LANDMARK_SITES, isWater } from './city-config.js';
import { GEO } from './shuyang-geodata.js';
import { PARK_RETROFIT_PATHS } from './park-retrofit.js';
import {
  createParkPavingMaterial,
  createParkLampGlobeMaterial,
  createParkLampPoolMaterial
} from './tsl-materials.js';

// 公园与校区内部的地面细部：把 OSM 实测步道铺成园路，并在公园范围内按固定间距
// 布置座椅、垃圾桶、园灯与灯下光斑。园路走向与宽度是实测数据；家具体量属类型化
// 推定（照片只用于确定样式与分布密度），不新增任何建筑轮廓。

const PAVE_Y = 0.095;
const LAMP_H = 3.4;
const BENCH_SPACING = 34;
const BIN_SPACING = 88;
const LAMP_SPACING = 23;

const PAINT = {
  wood: 0x8a5a33,
  iron: 0x2c3136,
  bin: 0x2f4f3a,
  pole: 0x343a40
};

const parkRings = PARKS.flatMap((p) => p.rings.map((ring) => ({ name: p.name, kind: p.kind, ring })));
const landmarkReserve = Object.values(LANDMARK_SITES);

// 园路铺装按实景证据分色：沭河公园主步道为红色塑胶/彩色沥青，梦溪植物园为赭红园路，
// 城北公园山道为小粒径卵石。只有取得实拍证据的公园才换色，其余沿用通用石材铺装。
const PARK_PAVING = {
  沭河公园: 'red',
  梦溪植物园: 'rust',
  城北公园: 'cobble'
};
// 临水护栏样式：沭河公园为白色古典石栏板＋小望柱（2019-06 实拍），
// 梦溪植物园为蓝白金属栏杆（2026-01 实拍）。仅沿实测园路的临水一侧设置。
const PARK_RAIL = {
  沭河公园: 'stone',
  梦溪植物园: 'metal'
};
// 临水公园边界处的石栏：沭河公园沿河一侧是白色古典石栏（2019-06 实拍），
// 该园在 OSM 中没有园路，因此按实测公园边界的临水段落布置。
const RIVER_RAIL_PARKS = new Set(['沭河公园']);

function insideRing(ring, x, z) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a.z > z) !== (b.z > z) && x < ((b.x - a.x) * (z - a.z)) / (b.z - a.z) + a.x) inside = !inside;
  }
  return inside;
}
const parkAt = (x, z) => parkRings.find((p) => insideRing(p.ring, x, z)) || null;
const inLandmarkReserve = (x, z) => landmarkReserve.some((s) => Math.abs(x - s.x) < s.w / 2 && Math.abs(z - s.z) < s.d / 2);
const toPoints = (flat) => {
  const pts = [];
  for (let i = 0; i + 1 < flat.length; i += 2) pts.push({ x: flat[i], z: flat[i + 1] });
  return pts;
};
// 沭河东岸步道贴着水边走，中点落在公园多边形外的河滩上，按中点取园名会取空，
// 铺装就退回通用石材。改成沿折线每 4 m 采样、取命中次数最多的公园；全不在园内
// 才返回 null（此时仍用通用石材）。
function parkAlongPath(pts) {
  const hits = new Map();
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1];
    const steps = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.z - a.z) / 4));
    for (let s = 0; s <= steps; s++) {
      const t = s / steps;
      const park = parkAt(a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t);
      if (!park) continue;
      const row = hits.get(park.name) || { park, n: 0 };
      row.n++;
      hits.set(park.name, row);
    }
  }
  let best = null;
  for (const row of hits.values()) if (!best || row.n > best.n) best = row;
  return best ? best.park : null;
}

// 沿折线生成等宽带，uv.x 固定为铺装样式（供 createParkPavingMaterial 选择），uv.y 为里程。
function ribbon(pts, width, style, y = PAVE_Y) {
  const pos = [], nor = [], uv = [], idx = [];
  const half = width / 2;
  const left = [], right = [];
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const prev = pts[Math.max(0, i - 1)];
    const next = pts[Math.min(pts.length - 1, i + 1)];
    let dx = next.x - prev.x, dz = next.z - prev.z;
    const l = Math.hypot(dx, dz) || 1;
    dx /= l; dz /= l;
    const nx = -dz, nz = dx;
    left.push({ x: p.x + nx * half, z: p.z + nz * half });
    right.push({ x: p.x - nx * half, z: p.z - nz * half });
  }
  let dist = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const L = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z);
    const base = pos.length / 3;
    pos.push(
      left[i].x, y, left[i].z,
      right[i].x, y, right[i].z,
      left[i + 1].x, y, left[i + 1].z,
      right[i + 1].x, y, right[i + 1].z
    );
    for (let k = 0; k < 4; k++) nor.push(0, 1, 0);
    uv.push(style, dist, style, dist, style, dist + L, style, dist + L);
    // 顶点顺序保证正面朝上（默认 FrontSide 材质，反绕会被背面剔除）。
    idx.push(base, base + 2, base + 1, base + 2, base + 3, base + 1);
    dist += L;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx);
  return geo;
}

function pad(cx, cz, w, d, heading, style, y = PAVE_Y + 0.002) {
  const geo = new THREE.PlaneGeometry(w, d);
  geo.rotateX(-Math.PI / 2);
  geo.rotateY(heading);
  geo.translate(cx, y, cz);
  const count = geo.attributes.position.count;
  const styles = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) styles[i * 2] = style;
  geo.setAttribute('uv', new THREE.BufferAttribute(styles, 2));
  return geo;
}

function box(w, h, d, x, y, z, heading = 0) {
  const geo = new THREE.BoxGeometry(w, h, d);
  if (heading) geo.rotateY(heading);
  geo.translate(x, y, z);
  return geo;
}

function benchGeometry(x, z, heading) {
  const parts = [];
  const seatY = 0.44;
  for (let i = 0; i < 3; i++) {
    parts.push(box(1.7, 0.055, 0.115, x, seatY, z, heading));
  }
  // 靠背两片木板，向园路一侧倾斜
  const back = box(1.7, 0.13, 0.055, x - Math.sin(heading) * 0.24, 0.76, z - Math.cos(heading) * 0.24, heading);
  parts.push(back);
  parts.push(box(1.7, 0.13, 0.055, x - Math.sin(heading) * 0.3, 0.92, z - Math.cos(heading) * 0.3, heading));
  const legs = [];
  for (const s of [-0.72, 0.72]) {
    const lx = x + Math.cos(heading) * s;
    const lz = z - Math.sin(heading) * s;
    legs.push(box(0.07, seatY, 0.46, lx, seatY / 2, lz, heading));
    legs.push(box(0.07, 0.5, 0.06, lx - Math.sin(heading) * 0.26, seatY + 0.22, lz - Math.cos(heading) * 0.26, heading));
  }
  return { wood: mergeGeometries(parts), iron: mergeGeometries(legs) };
}

// 抬高整组家具到台地顶面（园址在 0.22 m 街区台地上时使用）。
function liftGeos(geos, dy) {
  if (!dy) return geos;
  for (const g of geos) g.translate(0, dy, 0);
  return geos;
}

function binGeometry(x, z) {
  const body = new THREE.CylinderGeometry(0.28, 0.24, 0.78, 10, 1);
  body.translate(x, 0.39, z);
  const rim = new THREE.CylinderGeometry(0.31, 0.31, 0.06, 10, 1);
  rim.translate(x, 0.81, z);
  return mergeGeometries([body, rim]);
}

function lampGeometry(x, z) {
  const pole = new THREE.CylinderGeometry(0.07, 0.09, LAMP_H, 8, 1);
  pole.translate(x, LAMP_H / 2, z);
  const base = new THREE.CylinderGeometry(0.16, 0.2, 0.22, 10, 1);
  base.translate(x, 0.11, z);
  return mergeGeometries([pole, base]);
}

function globeGeometry(x, z) {
  const geo = new THREE.SphereGeometry(0.19, 12, 8);
  geo.translate(x, LAMP_H + 0.16, z);
  return geo;
}

function poolGeometry(x, z, y = PAVE_Y) {
  const geo = new THREE.CircleGeometry(3.1, 16);
  geo.rotateX(-Math.PI / 2);
  geo.translate(x, y + 0.004, z);
  return geo;
}

function pathFrame(pts, distance) {
  let acc = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const seg = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z);
    if (acc + seg >= distance) {
      const t = seg > 0 ? (distance - acc) / seg : 0;
      const x = pts[i].x + (pts[i + 1].x - pts[i].x) * t;
      const z = pts[i].z + (pts[i + 1].z - pts[i].z) * t;
      const heading = Math.atan2(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z);
      return { x, z, heading };
    }
    acc += seg;
  }
  return null;
}

function buildParkInterior(scene) {
  const pavingGeos = [];
  const plazaGeos = [];
  const redGeos = [];
  const rustGeos = [];
  const stoneRailGeos = [];
  const blueRailGeos = [];
  const whiteRailGeos = [];
  const woodGeos = [];
  const ironGeos = [];
  const binGeos = [];
  const poleGeos = [];
  const globeGeos = [];
  const poolGeos = [];
  let pavedPaths = 0, benches = 0, bins = 0, lamps = 0, riverRails = 0;
  const paletteCounts = { red: 0, rust: 0, stone: 0 };
  const touchedParks = new Set();

  // 园路来自两处：GEO.mapPaths 的实测 OSM 步道，以及 park-retrofit.js 里
  // 逐园核实过走向的补线（公开资料 + z18 影像判读，标注为推断）。
  // 地标保留区（LANDMARK_SITES 外接框）默认挡住通用园路：城北公园/虞姬公园已有
  // 复核过的湖岸与公园景观，不在这里重复铺线；虞姬生态园与沭河公园的地标只有
  // 定位锚点/雕塑、没有园内景观模型，允许补已核实的园路。
  const RETROFIT_ALLOWED_IN_RESERVE = new Set(['虞姬生态园', '沭河公园']);
  const mappedPaths = (GEO.mapPaths || []).map(([, kind, width, bridge, flat]) => ({ kind, width, bridge, pts: flat, park: null }));
  const retrofitPaths = PARK_RETROFIT_PATHS.filter((p) => p.kind !== 'plaza')
    .map((p) => ({...p, pts: p.pts.flat()}));
  for (const { kind, width, bridge, pts: flat, park: owner, surfaceY } of [...mappedPaths, ...retrofitPaths]) {
    if (bridge) continue;
    const pts = toPoints(flat).filter((p) => !isWater(p.x, p.z));
    if (pts.length < 2) continue;
    const mid = pts[Math.floor(pts.length / 2)];
    if (inLandmarkReserve(mid.x, mid.z) && !RETROFIT_ALLOWED_IN_RESERVE.has(owner)) continue;
    const park = parkAt(mid.x, mid.z);
    const w = Math.max(1.7, Math.min(6, (width || 2) + 0.9));
    const style = kind === 'pedestrian' || kind === 'living_street' ? 2 : 1;
    const pathY = surfaceY ?? PAVE_Y;
    const lift = pathY - PAVE_Y;
    const geo = ribbon(pts, w, style, pathY);
    const palettePark = parkAlongPath(pts) || park;
    const palette = palettePark ? PARK_PAVING[palettePark.name] : null;
    if (palette === 'red') { redGeos.push(geo); paletteCounts.red++; }
    else if (palette === 'rust') { rustGeos.push(geo); paletteCounts.rust++; }
    else {
      (style === 2 ? plazaGeos : pavingGeos).push(geo);
      paletteCounts.stone++;
    }
    pavedPaths++;
    if (park) touchedParks.add(park.name);

    // 园路与城市道路的衔接处铺一块入口小广场，位置取实测步道端点。
    for (const end of [pts[0], pts[pts.length - 1]]) {
      const toward = Math.atan2(end.x - pts[Math.max(0, pts.length - 2)].x, end.z - pts[Math.max(0, pts.length - 2)].z);
      plazaGeos.push(pad(end.x, end.z, w + 1.4, 3.4, toward, 2, pathY + 0.002));
    }

    if (!park) continue;

    let length = 0;
    for (let i = 0; i + 1 < pts.length; i++) length += Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z);
    const place = (spacing, offset, fn) => {
      for (let d = spacing * 0.6; d < length; d += spacing) {
        const f = pathFrame(pts, d);
        if (!f) break;
        const ox = Math.cos(f.heading) * offset;
        const oz = -Math.sin(f.heading) * offset;
        const x = f.x + ox, z = f.z + oz;
        if (isWater(x, z) || !parkAt(x, z)) continue;
        fn(x, z, f.heading);
      }
    };

    // 临水侧护栏：只沿实测园路朝水的一侧生成，不沿整圈水岸凭空补栏。
    const railKind = PARK_RAIL[park.name];
    if (railKind) {
      for (let d = 1; d < length; d += 2.0) {
        const f = pathFrame(pts, d);
        if (!f) break;
        const nx = Math.cos(f.heading), nz = -Math.sin(f.heading);
        let s = 0;
        if (isWater(f.x + nx * 2.2, f.z + nz * 2.2)) s = 1;
        else if (isWater(f.x - nx * 2.2, f.z - nz * 2.2)) s = -1;
        if (!s) continue;
        const x = f.x + nx * s * 1.35, z = f.z + nz * s * 1.35;
        if (railKind === 'stone') {
          stoneRailGeos.push(box(0.16, 0.62, 0.16, x, 0.31, z, f.heading));
          stoneRailGeos.push(box(0.1, 0.32, 1.72, x, 0.62, z, f.heading));
          whiteRailGeos.push(box(0.21, 0.12, 2.0, x, 1.04, z, f.heading));
        } else {
          blueRailGeos.push(box(0.07, 1.02, 0.07, x, 0.51, z, f.heading));
          blueRailGeos.push(box(0.05, 0.05, 2.0, x, 0.56, z, f.heading));
          whiteRailGeos.push(box(0.06, 0.06, 2.0, x, 1.0, z, f.heading));
        }
      }
    }

    let side = 1;
    const firstWood = woodGeos.length, firstIron = ironGeos.length, firstBin = binGeos.length;
    const firstPole = poleGeos.length, firstGlobe = globeGeos.length;
    place(BENCH_SPACING, 1.9, (x, z, heading) => {
      side = -side;
      const b = benchGeometry(x, z, side > 0 ? heading + Math.PI / 2 : heading - Math.PI / 2);
      woodGeos.push(b.wood);
      ironGeos.push(b.iron);
      benches++;
    });
    place(BIN_SPACING, -1.6, (x, z) => {
      binGeos.push(binGeometry(x, z));
      bins++;
    });
    place(LAMP_SPACING, 1.35, (x, z) => {
      poleGeos.push(lampGeometry(x, z));
      globeGeos.push(globeGeometry(x, z));
      poolGeos.push(poolGeometry(x, z, pathY));
      lamps++;
    });
    // 台地上的园路：家具与灯下光斑随铺装一起抬到台地顶面。
    if (lift) {
      liftGeos(woodGeos.slice(firstWood), lift);
      liftGeos(ironGeos.slice(firstIron), lift);
      liftGeos(binGeos.slice(firstBin), lift);
      liftGeos(poleGeos.slice(firstPole), lift);
      liftGeos(globeGeos.slice(firstGlobe), lift);
    }
  }

  // 沭河公园没有实测园路，按其实测公园边界与水面的相邻段落补白色石栏。
  for (const p of PARKS) {
    if (!RIVER_RAIL_PARKS.has(p.name)) continue;
    for (const ring of p.rings) {
      for (let i = 0; i < ring.length; i++) {
        const a = ring[i], b = ring[(i + 1) % ring.length];
        const len = Math.hypot(b.x - a.x, b.z - a.z);
        if (len < 0.5) continue;
        const tx = (b.x - a.x) / len, tz = (b.z - a.z) / len;
        for (let d = 1; d < len; d += 2.0) {
          const x = a.x + tx * d, z = a.z + tz * d;
          const nx = -tz, nz = tx;
          const dry = !isWater(x + nx * 1.6, z + nz * 1.6) ? 1 : !isWater(x - nx * 1.6, z - nz * 1.6) ? -1 : 0;
          if (!dry || isWater(x, z)) continue;
          const rx = x + nx * dry * 0.9, rz = z + nz * dry * 0.9;
          const heading = Math.atan2(tx, tz);
          stoneRailGeos.push(box(0.16, 0.62, 0.16, rx, 0.31, rz, heading));
          stoneRailGeos.push(box(0.1, 0.32, 1.72, rx, 0.62, rz, heading));
          whiteRailGeos.push(box(0.21, 0.12, 2.0, rx, 1.04, rz, heading));
          riverRails++;
        }
      }
    }
  }

  // 入口/纪念广场：只铺已核实范围的硬质铺装，不新增建筑与构筑物。
  const retrofitPlazas = PARK_RETROFIT_PATHS.filter((p) => p.kind === 'plaza');
  for (const item of retrofitPlazas) {
    const [x, z] = item.pts[0];
    if (inLandmarkReserve(x, z) && !RETROFIT_ALLOWED_IN_RESERVE.has(item.park)) continue;
    plazaGeos.push(pad(x, z, item.pad.w, item.pad.d, item.heading || 0, 2, (item.surfaceY ?? PAVE_Y) + 0.002));
    const park = parkAt(x, z);
    if (park) touchedParks.add(park.name);
  }

  const pavingMat = createParkPavingMaterial();
  const add = (geos, material, shadows = false) => {
    if (!geos.length) return null;
    const merged = mergeGeometries(geos);
    if (!merged) return null;
    const mesh = new THREE.Mesh(merged, material);
    mesh.receiveShadow = true;
    mesh.castShadow = shadows;
    scene.add(mesh);
    return mesh;
  };

  add(pavingGeos, pavingMat);
  add(plazaGeos, pavingMat);
  add(redGeos, new THREE.MeshStandardNodeMaterial({ color: 0x9c3b30, roughness: 0.88 }));
  add(rustGeos, new THREE.MeshStandardNodeMaterial({ color: 0x8a5340, roughness: 0.9 }));
  add(stoneRailGeos, new THREE.MeshStandardNodeMaterial({ color: 0xe4e0d6, roughness: 0.85 }), true);
  add(blueRailGeos, new THREE.MeshStandardNodeMaterial({ color: 0x4d8fc4, roughness: 0.5, metalness: 0.35 }), true);
  add(whiteRailGeos, new THREE.MeshStandardNodeMaterial({ color: 0xf1efe8, roughness: 0.6 }), true);
  add(woodGeos, new THREE.MeshStandardMaterial({ color: PAINT.wood, roughness: 0.78 }), true);
  add(ironGeos, new THREE.MeshStandardMaterial({ color: PAINT.iron, roughness: 0.55, metalness: 0.6 }), true);
  add(binGeos, new THREE.MeshStandardMaterial({ color: PAINT.bin, roughness: 0.7, metalness: 0.2 }), true);
  add(poleGeos, new THREE.MeshStandardMaterial({ color: PAINT.pole, roughness: 0.5, metalness: 0.55 }), true);
  add(globeGeos, createParkLampGlobeMaterial());
  add(poolGeos, createParkLampPoolMaterial());

  const stats = { pavedPaths, benches, bins, lamps, riverRails, retrofitPaths: retrofitPaths.length, retrofitPlazas: retrofitPlazas.length, parks: touchedParks.size, paletteCounts };
  console.log('[parkInterior]', JSON.stringify(stats));
  return stats;
}

export { buildParkInterior };
