"""Fetch AMap z18 satellite mosaics for facility review.

Reads tools/data/shuyang/batch1-imagery-sites.json and writes review mosaics to
docs/acceptance/batch1-skeleton-2026-11-15/imagery with a 50 m world grid,
100 m bold rulers and existing building footprints overlaid. Tiles are GCJ-02;
every sample is inverted to WGS84 before it is drawn in the project metric
frame, so grid, source footprints and imagery share one coordinate system.
"""
import json, math, sys, time, runpy, gzip
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/shuyang'
OUT = ROOT / 'docs/acceptance/batch1-skeleton-2026-11-15/imagery'
CACHE = ROOT / '.workbuddy/imagery-tiles'
frame = runpy.run_path(str(ROOT / 'tools/enrich-shuyang-buildings.py'))
LAT, LON, KX, KY = frame['LAT'], frame['LON'], frame['KX'], frame['KY']
coord = runpy.run_path(str(ROOT / 'tools/china-coordinates.py'))
TILE = 256
SCALE = 1.6
FONT_PATH = r'C:\Windows\Fonts\msyhbd.ttc'


def wgs_to_px(lon, lat, z):
    n = 2 ** z
    gx, gy = coord['wgs84_to_gcj02'](lon, lat)
    px = (gx + 180) / 360 * n * TILE
    s = math.sin(math.radians(gy))
    py = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n * TILE
    return px, py


def world_to_px(x, z, zoom, origin):
    lon = LON + x / KX
    lat = LAT - z / KY
    px, py = wgs_to_px(lon, lat, zoom)
    return px - origin[0], py - origin[1]


def fetch(tx, ty, zoom):
    path = CACHE / f'{zoom}/{tx}/{ty}.jpg'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://webst01.is.autonavi.com/appmaptile?style=6&x={tx}&y={ty}&z={zoom}'
        req = Request(url, headers={'User-Agent': 'slop-shuyang facility review'})
        for attempt in range(3):
            try:
                with urlopen(req, timeout=25) as r:
                    path.write_bytes(r.read())
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5)
    return path


def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_PATH if bold else r'C:\Windows\Fonts\msyh.ttc', size)
    except OSError:
        return ImageFont.load_default()


class Canvas:
    def __init__(self, img, zoom, origin, scale):
        self.img, self.zoom, self.origin, self.scale = img, zoom, origin, scale
        self.draw = ImageDraw.Draw(img)

    def px(self, x, z):
        a, b = world_to_px(x, z, self.zoom, self.origin)
        return a * self.scale, b * self.scale


def draw_grid(c, x, z, half, step=50, major=100):
    small, big = font(15), font(21)
    lo_x, hi_x, lo_z, hi_z = x - half, x + half, z - half, z + half
    for gx in range(math.ceil(lo_x / step) * step, math.floor(hi_x / step) * step + 1, step):
        p0, p1 = c.px(gx, lo_z), c.px(gx, hi_z)
        is_major = gx % major == 0
        c.draw.line([p0, p1], fill=(255, 0, 170, 150 if is_major else 80), width=2 if is_major else 1)
        if is_major:
            for yy in (8, c.img.size[1] - 26):
                c.draw.rectangle([p0[0] - 26, yy - 3, p0[0] + 26, yy + 20], fill=(0, 0, 0, 160))
                c.draw.text((p0[0] - 24, yy), str(gx), font=big, fill=(255, 160, 240))
    for gz in range(math.ceil(lo_z / step) * step, math.floor(hi_z / step) * step + 1, step):
        p0, p1 = c.px(lo_x, gz), c.px(hi_x, gz)
        is_major = gz % major == 0
        c.draw.line([p0, p1], fill=(255, 0, 170, 150 if is_major else 80), width=2 if is_major else 1)
        if is_major:
            for xx in (6, c.img.size[0] - 58):
                c.draw.rectangle([xx - 3, p0[1] - 11, xx + 54, p0[1] + 11], fill=(0, 0, 0, 160))
                c.draw.text((xx, p0[1] - 11), str(gz), font=big, fill=(255, 160, 240))
    c.draw.text((8, 8), f'world x {round(lo_x)}..{round(hi_x)} / z {round(lo_z)}..{round(hi_z)}',
                font=small, fill=(255, 255, 180))


def draw_site(frame_img, site, zoom, origin, scale):
    c = Canvas(frame_img, zoom, origin, scale)
    draw_grid(c, site['x'], site['z'], site['half'])
    cx, cz = c.px(site['x'], site['z'])
    c.draw.line([(cx - 14, cz), (cx + 14, cz)], fill=(0, 255, 255), width=3)
    c.draw.line([(cx, cz - 14), (cx, cz + 14)], fill=(0, 255, 255), width=3)
    label = f"{site['name']}  中心 {site['x']:.1f},{site['z']:.1f}"
    c.draw.rectangle([6, 30, 6 + 17 * len(label), 58], fill=(0, 0, 0, 175))
    c.draw.text((10, 33), label, font=font(18), fill=(255, 255, 0))
    return c


def draw_buildings(c, x, z, half):
    rows = json.loads(gzip.decompress((DATA / 'buildings-enriched.json.gz').read_bytes()).decode())['buildings']
    label_font = font(14)
    for i, b in enumerate(rows):
        rings = b['polygons']
        pts = [p for poly in rings for p in poly['outer']]
        if not pts:
            continue
        if (max(p[0] for p in pts) < x - half or min(p[0] for p in pts) > x + half
                or max(p[1] for p in pts) < z - half or min(p[1] for p in pts) > z + half):
            continue
        for poly in rings:
            ring = [c.px(px, pz) for px, pz in poly['outer']]
            color = (0, 220, 255) if b['source'] == 'OSM' else (255, 70, 70)
            if b['source'] == 'ReviewedImagery':
                color = (255, 220, 0)
            c.draw.line(ring + [ring[0]], fill=color, width=3)
        area = sum(abs(sum(poly['outer'][k][0] * poly['outer'][k - 1][1] - poly['outer'][k - 1][0] * poly['outer'][k][1]
                            for k in range(len(poly['outer'])))) / 2 for poly in rings)
        if area >= 400:
            q = c.px(sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            c.draw.rectangle([q[0] - 2, q[1] - 2, q[0] + 76, q[1] + 18], fill=(0, 0, 0, 120))
            c.draw.text((q[0], q[1]), f"{i} {b['source'][:2]} {int(area)}", font=label_font, fill=(255, 255, 255))


def draw_batch1(c, x, z, half):
    """批1/批2 新增或改写的几何：绿色为建筑与地表，便于与影像逐件核对。"""
    for name in ('reviewed-batch1-buildings.geojson', 'reviewed-batch2-buildings.geojson'):
        path = DATA / name
        if not path.exists():
            continue
        for f in json.loads(path.read_bytes())['features']:
            ring = [((lon - LON) * KX, -(lat - LAT) * KY) for lon, lat in f['geometry']['coordinates'][0]]
            if not any(abs(px - x) < half and abs(pz - z) < half for px, pz in ring):
                continue
            pts = [c.px(px, pz) for px, pz in ring]
            c.draw.line(pts + [pts[0]], fill=(0, 255, 90), width=4)
    for name in ('batch1-facility-surfaces.json', 'batch2-facility-surfaces.json'):
        surfaces = DATA / name
        if surfaces.exists():
            for s in json.loads(surfaces.read_bytes())['surfaces']:
                for r in [s['rings'][0], *s['rings'][1:]]:
                    pts = [c.px(px, pz) for px, pz in r]
                    c.draw.line(pts + [pts[0]], fill=(0, 255, 90), width=3)


def main():
    # 第二个批次复用同一套网格/叠加与标注纪律：参数为站点文件名与输出目录。
    sites_name = sys.argv[1] if len(sys.argv) > 1 else 'batch1-imagery-sites.json'
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    sites = json.loads((DATA / sites_name).read_text(encoding='utf-8'))['sites']
    # 每次出图只写本次站点会覆盖掉先前站点的来源信息；保留已记录站点，
    # 追加或更新同 id 的条目，避免多批影像共用目录时丢失坐标标定。
    previous = []
    if (out_dir / 'metadata.json').exists():
        previous = json.loads((out_dir / 'metadata.json').read_text(encoding='utf-8')).get('sites', [])
    meta = {'provider': '高德地图卫星影像瓦片（GCJ-02）',
            'tileUrl': 'https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
            'retrievedAt': '2026-11-15', 'resolutionMetersPerPixel': 0.494,
            'coordinateNote': '瓦片为 GCJ-02 网格；经 tools/china-coordinates.py 反算 WGS84 后投影到项目米制坐标，与 OSM/Overture 同系。检索日期不是拍摄日期。',
            'limitations': '影像约 0.5 m/px；树冠、阴影与在建工地遮挡会压低轮廓判读精度；高度为层数或照片推断，非测量值。',
            'sites': []}
    for site in sites:
        zoom, half = site.get('zoom', 18), site['half']
        corners = [world_to_px(site['x'] + dx, site['z'] + dz, zoom, (0, 0))
                   for dx, dz in ((-half, -half), (half, -half), (-half, half), (half, half))]
        tx0, tx1 = int(min(c[0] // TILE for c in corners)), int(max(c[0] // TILE for c in corners))
        ty0, ty1 = int(min(c[1] // TILE for c in corners)), int(max(c[1] // TILE for c in corners))
        img = Image.new('RGB', ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE))
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                img.paste(Image.open(fetch(tx, ty, zoom)).convert('RGB'), ((tx - tx0) * TILE, (ty - ty0) * TILE))
        origin = (tx0 * TILE, ty0 * TILE)
        base = img.resize((int(img.size[0] * SCALE), int(img.size[1] * SCALE)), Image.LANCZOS).convert('RGBA')
        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
        c = Canvas(overlay, zoom, origin, SCALE)
        draw_buildings(c, site['x'], site['z'], half)
        draw_batch1(c, site['x'], site['z'], half)
        draw_site(overlay, site, zoom, origin, SCALE)
        out = Image.alpha_composite(base, overlay).convert('RGB')
        path = out_dir / f"{site['id']}.png"
        out.save(path, optimize=True)
        a = world_to_px(site['x'] - half, site['z'] - half, zoom, origin)
        b = world_to_px(site['x'] + half, site['z'] + half, zoom, origin)
        meta['sites'].append({'id': site['id'], 'name': site['name'], 'zoom': zoom,
                              'worldCenter': [site['x'], site['z']], 'halfSizeM': half,
                              'imageScale': SCALE,
                              # 出图是 1.6 倍放大后的像素；换算世界坐标要乘回 imageScale。
                              'pixelPerMeter': round((b[1] - a[1]) / (2 * half) * SCALE, 4),
                              'worldToPixel': {'x0': round(a[0] * SCALE, 2), 'z0': round(a[1] * SCALE, 2)},
                              'image': path.name})
        print(site['id'], path.name, out.size)
    merged = {s['id']: s for s in previous}
    merged.update({s['id']: s for s in meta['sites']})
    meta['sites'] = list(merged.values())
    (out_dir / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
