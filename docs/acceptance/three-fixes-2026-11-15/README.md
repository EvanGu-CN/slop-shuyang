# 三处缺陷修复验收 — 2026-11-15

依据空间/渲染复扫（`docs/acceptance/spatial-render-rescan-2026-11-15/`）定位的三处缺陷逐处修复。
未 commit；未改动任何实测数据；标注纪律不变（新增几何仍是影像推断，±6 m）。

| # | 缺陷 | 改法 | 结果 |
|---|---|---|---|
| 1 | 沭河东岸配色取错 | 园名改按路径多数采样点取 | 东岸步道由白石材改为 `#9c3b30`，与连接路/园内园路一致 |
| 2 | 连接路与广场 9–11 m 草皮断口 | 新增 14.4 m 短接条目 | 断口两侧铺装重叠，raycast 连续命中红色铺装 |
| 3 | 校门铺装被台地埋掉 | 逐门取门前最高地面 + 0.025 m | 33 道门 0 处被遮挡；铺装高程分 4 档，非写死 |

## 1. 沭河东岸配色取错

**原因**：`js/park-interior.js` 用路径**中点** `parkAt(mid)` 决定 `PARK_PAVING`。沭河东岸步道紧贴水边，中点 `(1016, 3352)` 落在公园多边形外的河滩上，取不到 palette，退回通用石材；同一条连接路的中点落在园内，于是变成红色塑胶。同一公园两种材质。

**改法**（只改配色，不动家具/栏杆的既有判定）：

```js
// 沿折线每 4 m 采样，取命中次数最多的公园；全不在园内才返回 null。
function parkAlongPath(pts) { ... }
const palettePark = parkAlongPath(pts) || park;
const palette = palettePark ? PARK_PAVING[palettePark.name] : null;
```

**验证**：

| 点位 | 坐标 | 修复前 | 修复后 |
|---|---|---|---|
| 东岸步道 | 1006, 3290 | 0.095 `white` | **0.095 `#9c3b30`** |
| 东岸连接路 | 1080, 3343 | 0.095 `#9c3b30` | 0.095 `#9c3b30` |
| 连接路短接 | 1164, 3330 | —（草坪 0.05） | **0.095 `#9c3b30`** |

`[parkInterior] paletteCounts = {"red":3,"rust":0,"stone":63}`：沭河公园内 3 段（园路 + 连接路 + 短接）统一走红色，其余 63 段不受影响。
截图：`fix1-shuhe-colour-200m.jpg`（200 m）、`fix1-shuhe-800m.jpg`（800 m）。

## 2. 连接路与广场之间的草皮断口

**原因**：`js/park-retrofit.js` 的连接路末点 `x=1160`，广场 pad 中心 `1200`、宽 `62` → 西缘 `x=1169`，中间 9 m 没有铺装。

**改法**：新增一条独立短接条目，不改既有连接路与广场：

```js
{ id: 'retrofit/shu-he/plaza-junction', kind: 'footpath', width: 3,
  pts: [[1158, 3334], [1170, 3326]] }
```

端点各伸入既有铺装 2 m / 1 m 以避免接缝；长度 14.4 m，方向按最短连线取直（影像判读，±6 m）。

**验证**（raycast 顶面）：

| 点位 | 坐标 | 修复前 | 修复后 |
|---|---|---|---|
| 短接中点 | 1164, 3330 | 0.05 草坪 | **0.095 `#9c3b30`** |
| 广场 pad | 1200, 3326 | 0.097 | 0.097 |
| 原断口坐标 | 1165, 3334 | 0.05 草坪 | 0.05（新线位在 z≈3329，该点已不在线上） |

几何上短接段 `x=1169–1170` 与广场 pad（西缘 1169）重叠，铺装连续。
截图：`fix2-shuhe-junction-200m.jpg`（可见红色铺装接到砖铺广场）、`fix2-shuhe-junction-800m.jpg`。

## 3. 校门铺装被台地埋掉

**原因**：`js/school-grounds.js` 把门前硬地固定在 `y=0.085`，而门前实际地面可能是街区台地 `0.22`、路缘 `0.18`、影像铺面 `0.225–0.28`，整块被盖住。

**改法**：不再写死一个值，逐门取该点**最高的那层地面**再抬 2.5 cm：

```js
function apronHeightAt(x, z) {
  // 街区台地 ISLAND_BOUNDS.sidewalkHeight (0.22)
  // 路缘 0.18
  // 影像铺面 URBAN_SURFACE_STYLES[kind].y (0.225–0.28)
  return top === null ? 0.085 : top + 0.025;
}
```

铺面高程表从 `js/urban-context.js` 提升为 `export const URBAN_SURFACE_STYLES`（单点改动，原逻辑不变），避免两处各写一份常数。校名牌、门柱高度未动。

**验证**（33 道校门逐点 raycast + 合并几何顶点）：

| 指标 | 数值 |
|---|---|
| 校门数 / 铺装平面数 | 33 / 33 |
| 抬高（>0.085） | **13**（台地 10 + 路缘 2 + 影像铺面 1） |
| 保持 0.085（门前无铺面） | 20 |
| 铺装高程档位 | 0.085 / 0.205 / 0.245 / 0.28 |
| **仍被遮挡** | **0**（首次只按台地判断时为 3，加路缘/影像铺面后归零） |

`[schoolGrounds] = {"gates":33,"byMappedPath":1,"plaques":33,"raisedAprons":13}`。
截图：`fix3-gate-raised-200m.jpg` + `crop-gate-raised-200m.jpg`（抬高后铺装露出）、`fix3-gate-flat-200m.jpg` + `crop-gate-flat-200m.jpg`（未抬高的对照）、`fix3-school-gate-raised-140m.jpg`、`fix3-gate-raised-800m.jpg`。

## 4. 回归与性能

- 全量测试：**430 / 430 通过**（`node --test tests/*.test.*`，排除 `overpass.test.mjs`）。
- mesh 数：修复前后均 **7,875**；`SchoolGates` 仍为 4 个 mesh（门柱/名牌面/名牌底/铺装）。
- draw call：两处改动都只往**既有合批**里追加顶点——连接路并入园路批（材质仍为 paving/plaza/red 三种），校门铺装只改顶点高程、不新增 mesh，因此绘制调用不增加。三角形随短接段增加约 2 个四边形，可忽略。

## 5. 改动文件

| 文件 | 改动 |
|---|---|
| `js/park-interior.js` | 新增 `parkAlongPath()`；palette 改按多数命中取；stats 增 `paletteCounts`（单点改动） |
| `js/park-retrofit.js` | 新增 `retrofit/shu-he/plaza-junction`（自有文件） |
| `js/school-grounds.js` | 新增 `apronHeightAt()` 与铺面缓存；stats 增 `raisedAprons`（自有文件） |
| `js/urban-context.js` | `styles` 提升为 `export const URBAN_SURFACE_STYLES`（单点改动，行为不变） |

本目录：`README.md`、`apron-verify.json`、`apron-centres.json` 与截图。
