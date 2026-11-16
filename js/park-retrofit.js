// 公园内部补线：只收录「有公开资料或卫星影像可核实走向」的园路与广场。
//
// 这批 7 个公园原先只有绿地轮廓（或几栋既有建筑），设施清单里标为「部分渲染」。
// 本轮逐园检索公开资料 + 高德 z18 影像裁片判读，能确认的只落"走向"这一层：
// 园路中心线、入口广场、环湖环线；不能确认的一律不落，并在 evidence.note 写明原因。
//
// 标注纪律（与环 0–4 一致）：
// - 所有条目都是 imagery-inferred / 公开资料方位推断，不是测绘中心线，
//   水平误差约 ±6 m（z18 影像 0.494 m/px，人工取中线）。
// - 不新增任何建筑轮廓：7 个公园都没有可核实的建筑位置依据，纪念碑、亭、公厕、
//   管理房一律不补，避免臆造。
// - 资料里的"5 座休闲广场""2500 m 彩色跑道"等属于整条老沭河健身步道走廊的统计，
//   不能平移到本段公园，故只落本段可核实的单条步道与单处广场。
//
// 每个条目字段：
//   id            场景内唯一 id（retrofit/<park>/<name>）
//   park          对应 PARKS[].name
//   name          中文名
//   kind          'pedestrian' | 'footpath' | 'plaza'
//   width         铺装宽度（米）
//   pad           广场尺寸（仅 kind === 'plaza'）
//   surfaceY      铺装顶面高程（仅当所在公园台地高于默认 0.095 m 时填写）
//   closed        是否闭合环线
//   pts           [[x, z], ...]，项目米制世界坐标
//   evidence      { strength, source, fetched, note }
//
// 来源清单见 docs/acceptance/park-retrofit-2026-11-15/README.md。

export const PARK_RETROFIT_PATHS = [
  {
    id: 'retrofit/yu-ji/axis',
    park: '虞姬生态园',
    name: '南北中心轴园路',
    kind: 'pedestrian',
    width: 5.5,
    closed: false,
    surfaceY: 0.245,
    pts: [[2405, 1714], [2430, 1655], [2455, 1600], [2478, 1546], [2455, 1470], [2410, 1380], [2360, 1290], [2310, 1200], [2270, 1130], [2250, 1110]],
    evidence: {
      strength: 'medium',
      source: 'shuyang.gov.cn 标准地名通知（南北中心轴、南北两门）+ AMap z18 影像（2026-11-15 获取）',
      fetched: '2026-11-15',
      note: '轴线走向与两端门位由官方"南北中心轴"描述与影像中的南门前庭确认；中段穿越林地，中线按南门与北门连线取直，±6 m。园址大部分在 0.22 m 街区台地上，铺装顶面取 0.245 m（surfaceY），否则会被台地遮住。'
    }
  },
  {
    id: 'retrofit/shu-he/riverside',
    park: '沭河公园',
    name: '老沭河东岸健身步道',
    kind: 'pedestrian',
    width: 3.2,
    closed: false,
    pts: [[1012, 3090], [1008, 3150], [1002, 3220], [1006, 3290], [1016, 3352], [1032, 3412], [1052, 3470], [1070, 3524]],
    evidence: {
      strength: 'medium',
      source: '江苏省体育局"老沭河健身步道"（3 m 彩色跑道）+ AMap z18 影像（2026-11-15 获取）',
      fetched: '2026-11-15',
      note: '宽度 3 m 来自省体育局报道；东岸走向由影像中沿河浅色铺装带取中线，±6 m。西岸不在本公园多边形内，未补；跨河桥无位置依据，未补。'
    }
  },
  {
    id: 'retrofit/shu-he/plaza-link',
    park: '沭河公园',
    name: '东岸广场连接路',
    kind: 'footpath',
    width: 3,
    closed: false,
    pts: [[1016, 3352], [1060, 3348], [1110, 3340], [1160, 3334]],
    evidence: {
      strength: 'medium',
      source: 'AMap z18 影像（2026-11-15 获取）：步道与东侧圆形广场之间的浅色连接路',
      fetched: '2026-11-15',
      note: '连接路走向可见，宽度按 3 m 类型化取值，±6 m。'
    }
  },
  {
    id: 'retrofit/shu-he/plaza-junction',
    park: '沭河公园',
    name: '连接路—广场短接',
    kind: 'footpath',
    width: 3,
    closed: false,
    pts: [[1158, 3334], [1170, 3326]],
    evidence: {
      strength: 'medium',
      source: 'AMap z18 影像（2026-11-15 获取）：连接路与圆形广场西缘之间连续的铺装',
      fetched: '2026-11-15',
      note: '只补连接路末点 (1160, 3334) 与广场西缘 x=1169 之间 9–11 m 的草缝，走向按最短连线取直，端点各伸入既有铺装 2 m / 1 m 以避免接缝；不改动既有连接路与广场几何。±6 m。'
    }
  },
  {
    id: 'retrofit/shu-he/plaza',
    park: '沭河公园',
    name: '东岸圆形广场',
    kind: 'plaza',
    width: 0,
    closed: false,
    pts: [[1200, 3326]],
    pad: {w: 62, d: 62},
    evidence: {
      strength: 'medium',
      source: 'AMap z18 影像（2026-11-15 获取）：双圆铺装广场',
      fetched: '2026-11-15',
      note: '影像判读为一大一小两个圆叠合的铺装广场，按外接 62 × 62 m 方场近似；不还原圆环与花坛。'
    }
  },
  {
    id: 'retrofit/lieshi/axis',
    park: '沭阳烈士陵园',
    name: '纪念中轴园路',
    kind: 'pedestrian',
    width: 8,
    closed: false,
    surfaceY: 0.245,
    pts: [[1425, 1755], [1450, 1700], [1470, 1650], [1470, 1600], [1485, 1562]],
    evidence: {
      strength: 'medium',
      source: '宿迁市政府"沭阳烈士陵园"（纪念广场位于南侧、纪念碑在广场中央、1975 年建）+ AMap z18 影像（2026-11-15 获取）',
      fetched: '2026-11-15',
      note: '南门—纪念广场—纪念碑的空间序列由官方描述确认；中线沿 OSM 陵园轮廓的西南窄段取线（东段轮廓在 z≈1560 以南收窄），±6 m。园址整体在 0.22 m 街区台地上，铺装顶面取 0.245 m（surfaceY），否则会被台地遮住。东亭、西亭与墓区排布无精确坐标，未补。'
    }
  },
  {
    id: 'retrofit/lieshi/plaza',
    park: '沭阳烈士陵园',
    name: '纪念广场',
    kind: 'plaza',
    width: 0,
    closed: false,
    surfaceY: 0.245,
    pts: [[1468, 1608]],
    pad: {w: 60, d: 52},
    evidence: {
      strength: 'medium',
      source: '宿迁市政府"沭阳烈士陵园"（纪念广场位于南侧）+ AMap z18 影像',
      fetched: '2026-11-15',
      note: '广场范围按影像中铺装边界量取，±6 m；不新增纪念碑本体（既有 6 栋建筑已覆盖）。'
    }
  }
];

// 供验收文档与测试读取的汇总；不做渲染。
export const PARK_RETROFIT_SUMMARY = (() => {
  const byPark = new Map();
  for (const item of PARK_RETROFIT_PATHS) {
    const row = byPark.get(item.park) || {park: item.park, paths: 0, pathMeters: 0, plazas: 0, plazaAreaM2: 0, sources: new Set()};
    if (item.kind === 'plaza') {
      row.plazas++;
      row.plazaAreaM2 += item.pad.w * item.pad.d;
    } else {
      row.paths++;
      let len = 0;
      for (let i = 0; i + 1 < item.pts.length; i++) {
        len += Math.hypot(item.pts[i + 1][0] - item.pts[i][0], item.pts[i + 1][1] - item.pts[i][1]);
      }
      row.pathMeters += Math.round(len);
    }
    row.sources.add(item.evidence.source.split('（')[0]);
    byPark.set(item.park, row);
  }
  return [...byPark.values()].map((r) => ({...r, sources: [...r.sources]}));
})();

export const PARK_RETROFIT_SKIPPED = [
  {park: '建陵公园', reason: '公开资料只确认 1.1 万 m² 桂花主题街头绿地，园路、出入口、水体均无依据；影像内为规则绿化，无可稳定判读的园路走向。'},
  {park: '台州路森林公园', reason: '公开资料只有"水杉林 + 水域 + 竹筏"，且 2023 年仍在勘察设计；影像内以苗圃、农田与林地为主，无成型园路与出入口，按不臆造原则跳过。'},
  {park: '孙巷公园', reason: '公开资料确认北门小广场与儿童设施，但园路走向无依据；卫星影像中公园多边形内以宅间绿地为主，无法稳定分离园路，跳过。'},
  {park: '虞姬生态园', reason: '无建筑：公开资料未给出园内任何建筑坐标，影像中也无稳定可判读的独立建筑轮廓，故新增建筑为 0。'},
  {park: '虞姬生态园', reason: '中心广场未补：影像中心是一处已由既有图层铺绘的方形硬质场地（台地顶 0.22 m），外围只有环形园路；没有可与既有铺装区分的独立广场边界，再叠一块 74 × 74 m 铺装属臆造，故移除，只保留南北中轴。'},
  {park: '沭河公园', reason: '无建筑：沿河带状公园，影像中无独立建筑；资料中的 5 座休闲广场 / 3 座儿童广场属整条 5 km 步道走廊统计，未平移。'},
  {park: '沭阳烈士陵园', reason: '纪念碑、东西双亭、陈列室均在资料中提名，但无坐标；既有 6 栋建筑已覆盖主体，未新增。'},
  {park: '城北公园', reason: '湖岸已在 reviewed-water.json 中复核，地标带 preserveParkLandscape 标记，园内景观不重复铺线；梅园、廉政亭、佳绝厅、紫阳夕照桥、曙红桥等只提名称无坐标，既有 4 栋建筑保持原样，未新增。'}
];
