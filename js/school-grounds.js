import * as THREE from 'three/webgpu';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { nearestRoads, blockAt, ISLAND_BOUNDS } from './city-config.js';
import { GEO } from './shuyang-geodata.js';
import { URBAN_SURFACE_STYLES } from './urban-context.js';

// 校区地面细部：校门、门柱、校名牌与门前小广场。
// 校区轮廓来自 OSM amenity=school 实测面；校门位置优先取“实测步道穿越校区边界”的位置，
// 没有步道证据时退到“最贴近城市道路的一段边界”的顶点，并在验收文档中标为推断。
// 校舍本体沿用已有实测楼体，不新增任何建筑轮廓。

const CANVAS = typeof document !== 'undefined';
const SKIP = new Set(['沭阳实验小学', '江苏省沭阳高级中学', '江苏省沭阳梦溪中学']);
const PLAQUE_BG = '#8c2f26';
const PLAQUE_FG = '#e8c979';

function toRing(flat) {
  const ring = [];
  for (let i = 0; i + 1 < flat.length; i += 2) ring.push({ x: flat[i], z: flat[i + 1] });
  return ring;
}

function insideRing(ring, x, z) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a.z > z) !== (b.z > z) && x < ((b.x - a.x) * (z - a.z)) / (b.z - a.z) + a.x) inside = !inside;
  }
  return inside;
}

const CELL_W = 640;
const CELL_H = 112;

// 校门前的硬地原先固定在 0.085 m，而门前的实际地面可能是街区台地（0.22 m）、
// 路缘（0.18 m）或影像铺面（0.225–0.28 m）：铺装会被整块盖住。这里逐门取该点
// 最高的那层地面再抬 2.5 cm；门前没有任何铺面时才保留原来的 0.085 m。
const APRON_Y = 0.085;
const APRON_LIFT = 0.025;
const CURB_TOP = 0.18;
const RECT_SLAB_MAX_AREA = 120000;

// 影像铺面按面缓存包围盒，避免每道门都遍历全部多边形。
const MAPPED_SURFACES = [];
for (const surface of GEO.urban?.surfaces || []) {
  const style = URBAN_SURFACE_STYLES[surface.kind];
  if (!style) continue;
  for (const p of surface.polygons || []) {
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (let i = 0; i + 1 < p.outer.length; i += 2) {
      minX = Math.min(minX, p.outer[i]); maxX = Math.max(maxX, p.outer[i]);
      minZ = Math.min(minZ, p.outer[i + 1]); maxZ = Math.max(maxZ, p.outer[i + 1]);
    }
    MAPPED_SURFACES.push({ outer: p.outer, holes: p.holes || [], y: style.y, minX, maxX, minZ, maxZ });
  }
}

function pointInFlatRing(flat, x, z) {
  let inside = false;
  for (let i = 0, j = flat.length - 2; i < flat.length; j = i, i += 2) {
    const zi = flat[i + 1], zj = flat[j + 1];
    if ((zi > z) !== (zj > z) && x < ((flat[j] - flat[i]) * (z - zi)) / (zj - zi) + flat[i]) inside = !inside;
  }
  return inside;
}

function apronHeightAt(x, z) {
  let top = null;
  const block = blockAt(x, z);
  if (block) {
    // 小矩形街区整块铺到 0.22 m（city-grid 的 instanced rect slabs）。
    if (block.rect && block.area <= RECT_SLAB_MAX_AREA) top = ISLAND_BOUNDS.sidewalkHeight;
    else for (const slab of block.slabs || []) {
      if (insideRing(slab.outer, x, z) && !(slab.holes || []).some((h) => insideRing(h, x, z))) {
        top = ISLAND_BOUNDS.sidewalkHeight;
        break;
      }
    }
    if (top === null) for (const curb of block.surfaces || []) {
      if (insideRing(curb.outer, x, z) && !(curb.holes || []).some((h) => insideRing(h, x, z))) {
        top = CURB_TOP;
        break;
      }
    }
  }
  for (const s of MAPPED_SURFACES) {
    if (x < s.minX || x > s.maxX || z < s.minZ || z > s.maxZ) continue;
    if (top !== null && s.y <= top) continue;
    if (pointInFlatRing(s.outer, x, z) && !s.holes.some((h) => pointInFlatRing(h, x, z))) top = s.y;
  }
  return top === null ? APRON_Y : top + APRON_LIFT;
}

function drawPlaque(ctx, text, x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = PLAQUE_BG;
  ctx.fillRect(0, 0, CELL_W, CELL_H);
  ctx.strokeStyle = 'rgba(232,201,121,0.55)';
  ctx.lineWidth = 5;
  ctx.strokeRect(7, 7, CELL_W - 14, CELL_H - 14);
  ctx.fillStyle = PLAQUE_FG;
  const size = text.length > 9 ? 46 : text.length > 6 ? 56 : 68;
  ctx.font = `700 ${size}px "Microsoft YaHei", "PingFang SC", sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, CELL_W / 2, CELL_H / 2 + 2, CELL_W - 40);
  ctx.restore();
}

// One atlas for every campus plaque: 33 separate textured boards would otherwise cost one
// material group per box face. The atlas lets the stone sides and the printed faces each
// merge into a single draw call without changing what is printed.
function plaqueAtlas(names) {
  if (!CANVAS || !names.length) return null;
  const cols = 2;
  const rows = Math.ceil(names.length / cols);
  const canvas = document.createElement('canvas');
  canvas.width = CELL_W * cols;
  canvas.height = CELL_H * rows;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = PLAQUE_BG;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  names.forEach((name, i) => drawPlaque(ctx, name, (i % cols) * CELL_W, Math.floor(i / cols) * CELL_H));
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const rects = names.map((_, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    return { u0: col / cols, v0: 1 - (row + 1) / rows, du: 1 / cols, dv: 1 / rows };
  });
  return { texture: tex, rects };
}

// 实测步道穿越校区边界处，最可靠的校门位置证据。
function pathCrossing(ring) {
  for (const [, , , , flat] of GEO.mapPaths || []) {
    let prev = null;
    let prevInside = null;
    for (let i = 0; i + 1 < flat.length; i += 2) {
      const p = { x: flat[i], z: flat[i + 1] };
      const inside = insideRing(ring, p.x, p.z);
      if (prev && prevInside !== inside) {
        return {
          x: (prev.x + p.x) / 2,
          z: (prev.z + p.z) / 2,
          heading: Math.atan2(p.x - prev.x, p.z - prev.z),
          evidence: 'mapped-path-crossing'
        };
      }
      prev = p;
      prevInside = inside;
    }
  }
  return null;
}

// 退路：校区边界上离城市道路最近的顶点，取相邻边方向作为门线方向。
function roadFacing(ring) {
  let best = null;
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i];
    const near = nearestRoads(p.x, p.z, 30);
    if (!near.length) continue;
    const { road, dist } = near[0];
    if (dist > road.w / 2 + 14) continue;
    if (!best || dist < best.dist) {
      const next = ring[(i + 1) % ring.length];
      best = {
        x: p.x, z: p.z, dist,
        heading: Math.atan2(next.x - p.x, next.z - p.z),
        evidence: 'nearest-mapped-road'
      };
    }
  }
  return best;
}

function nearestRoadPoint(road, x, z) {
  let best = null;
  for (let i = 1; i < road.pts.length; i++) {
    const a = road.pts[i - 1], b = road.pts[i];
    const dx = b.x - a.x, dz = b.z - a.z;
    const t = Math.max(0, Math.min(1, ((x - a.x) * dx + (z - a.z) * dz) / (dx * dx + dz * dz || 1)));
    const px = a.x + dx * t, pz = a.z + dz * t;
    const d = Math.hypot(px - x, pz - z);
    if (!best || d < best.d) best = { x: px, z: pz, d };
  }
  return best;
}

function buildSchoolGrounds(scene, colliders = []) {
  const group = new THREE.Group();
  group.name = 'SchoolGates';
  const postGeos = [];
  const apronGeos = [];
  const plaques = [];
  let gates = 0;
  let byMappedPath = 0;
  let raisedAprons = 0;

  for (const ground of GEO.schoolGrounds || []) {
    if (SKIP.has(ground.n)) continue;
    if (!ground.r || ground.r.length < 6) continue;
    const ring = toRing(ground.r);
    const hit = pathCrossing(ring) || roadFacing(ring);
    if (!hit) continue;
    if (hit.evidence === 'mapped-path-crossing') byMappedPath++;

    // 门楣朝向：从校门指向最近道路点。
    let outward = { x: Math.cos(hit.heading + Math.PI / 2), z: -Math.sin(hit.heading + Math.PI / 2) };
    const near = nearestRoads(hit.x, hit.z, 40);
    if (near.length) {
      const rp = nearestRoadPoint(near[0].road, hit.x, hit.z);
      if (rp && rp.d > 0.5) outward = { x: (rp.x - hit.x) / rp.d, z: (rp.z - hit.z) / rp.d };
    }
    const heading = Math.atan2(outward.x, outward.z);
    const along = { x: Math.cos(heading + Math.PI / 2), z: -Math.sin(heading + Math.PI / 2) };

    for (const s of [-2.7, 2.7]) {
      const px = hit.x + along.x * s, pz = hit.z + along.z * s;
      const geo = new THREE.BoxGeometry(0.46, 3.4, 0.46);
      geo.translate(px, 1.7, pz);
      postGeos.push(geo);
      colliders.push({ minX: px - 0.3, maxX: px + 0.3, minZ: pz - 0.3, maxZ: pz + 0.3, minY: 0, maxY: 3.4 });
    }
    const beam = new THREE.BoxGeometry(6.1, 0.34, 0.4);
    beam.rotateY(heading);
    beam.translate(hit.x, 3.32, hit.z);
    postGeos.push(beam);

    // 门前硬地：从边界向道路一侧铺 4.2 m，避免压在楼体上；高程取门前实际台地。
    const apronX = hit.x + outward.x * 2.0;
    const apronZ = hit.z + outward.z * 2.0;
    const apronY = apronHeightAt(apronX, apronZ);
    if (apronY > APRON_Y) raisedAprons++;
    const apron = new THREE.PlaneGeometry(6.4, 4.2);
    apron.rotateX(-Math.PI / 2);
    apron.rotateY(heading);
    apron.translate(apronX, apronY, apronZ);
    const count = apron.attributes.position.count;
    const uv = new Float32Array(count * 2);
    for (let i = 0; i < count; i++) uv[i * 2] = 2;
    apron.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    apronGeos.push(apron);

    plaques.push({ name: ground.n, x: hit.x, z: hit.z, heading });
    gates++;
  }

  const add = (geos, material, shadow = false) => {
    if (!geos.length) return;
    const merged = mergeGeometries(geos);
    if (!merged) return;
    const mesh = new THREE.Mesh(merged, material);
    mesh.receiveShadow = true;
    mesh.castShadow = shadow;
    group.add(mesh);
  };
  add(postGeos, new THREE.MeshStandardNodeMaterial({ color: 0xd9d5ca, roughness: 0.82 }), true);
  add(apronGeos, new THREE.MeshStandardNodeMaterial({ color: 0x9a9a95, roughness: 0.92 }));

  const boardGeos = [];
  const faceGeos = [];
  const atlas = plaqueAtlas(plaques.map((p) => p.name));
  plaques.forEach((p, i) => {
    const board = new THREE.BoxGeometry(5.4, 0.92, 0.16);
    board.rotateY(p.heading);
    board.translate(p.x, 2.62, p.z);
    boardGeos.push(board);
    if (!atlas) return;
    const { u0, v0, du, dv } = atlas.rects[i];
    for (const side of [1, -1]) {
      const face = new THREE.PlaneGeometry(5.24, 0.8);
      const uv = face.attributes.uv;
      for (let v = 0; v < uv.count; v++) {
        uv.setXY(v, u0 + uv.getX(v) * du, v0 + uv.getY(v) * dv);
      }
      const h = p.heading + (side < 0 ? Math.PI : 0);
      face.rotateY(h);
      // The campus-side face is turned around; mirroring x keeps the name readable from both sides.
      if (side < 0) face.scale(-1, 1, 1);
      // Sit just proud of the board face (board depth 0.16) so the print never z-fights the stone.
      face.translate(p.x + Math.sin(h) * 0.081, 2.62, p.z + Math.cos(h) * 0.081);
      faceGeos.push(face);
    }
  });
  add(boardGeos, new THREE.MeshStandardNodeMaterial({ color: 0xd9d5ca, roughness: 0.82 }), true);
  if (atlas && faceGeos.length) {
    add(faceGeos, new THREE.MeshStandardNodeMaterial({ map: atlas.texture, roughness: 0.6 }));
  }

  scene.add(group);
  console.log('[schoolGrounds]', JSON.stringify({ gates, byMappedPath, plaques: plaques.length, raisedAprons }));
  return { gates, byMappedPath, plaques: plaques.length, raisedAprons };
}

export { buildSchoolGrounds };
