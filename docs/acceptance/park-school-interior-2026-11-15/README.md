# 公园与学校内部细化验收（2026-11-15）

本轮在既有数据与渲染体系内，只把 OSM 实测几何（公园多边形、校区边界、步道、公园边界）用于建模，
公开实拍只用于层数、形制、铺装颜色、护栏样式与出入口位置。所有几何来源可追溯到
`tools/data/shuyang/`，未新增任何凭推测生成的道路或建筑轮廓。

## 1. 覆盖范围

### 公园

| 公园 | 处理 | 依据 |
| --- | --- | --- |
| 虞姬生态园 | 7 段实测园路铺装 + 端点入口小广场 + 座椅 96 / 垃圾桶 37 / 园灯 138（两园合计） | `GEO.mapPaths` 实测步道；2023-11 航拍确认环湖步道级别 |
| 南湖公园 | 16 段实测园路铺装 + 入口小广场 + 家具 | `GEO.mapPaths`；虞姬园牌楼、崇孝苑铺装照片 |
| 沭河公园 | 682 段白色古典石栏（望柱 + 栏板 + 压顶），沿实测公园边界的临水段落 | 2019-06 实拍的石栏样式；该园在 OSM 中无园路，因此未铺园路 |
| 城北公园、孙巷公园、烈士陵园、台州路森林公园、建陵公园、开发区体育公园 | 未新增园路/家具 | OSM 中无园路几何；实拍只有景点细部，无法确定路径走向 |

- 公园多边形共 34 个；公园内实测建筑 20 栋、道路 5 段、步道 29 段（`data-audit.json`）。
- 梦溪植物园有完整实拍，但其范围（约 lon 118.836）落在项目核心边界以东，被边界裁剪，
  因此本轮未渲染，`PARK_PAVING` 中它的配色暂不生效。
- 建陵公园、开发区体育公园没有任何可核实实拍，仅按通用绿地渲染，园区细部未做。

### 学校

- 从 Overpass `amenity=school|kindergarten|college|university out geom`（2026-11 快照）取得 51 个具名闭合校区面，
  经项目边界裁剪后 40 个写入 `GEO.schoolGrounds`；此前只有 3 个专用校区有边界。
- 33 个校区生成校门（石柱 0.46×3.4、门楣、深红底金字校名牌、门前硬地）；3 个已有专用模型的校区
  （沭阳实验小学、江苏省沭阳高级中学、江苏省沭阳梦溪中学）跳过，避免重复。
- 校门方位：1 个由实测步道穿越校区边界确定（`byMappedPath`），其余 32 个取“边界上最贴近实测道路的顶点”，
  证据标记为 `nearest-mapped-road`；牌面文字取 OSM 校名。
- 校区内 400+ 栋楼改走学校立面族（`buildings.js` 的 school material），不再混用住宅立面。
- 23 条实测步道落在校区内，已由公园/校区地面模块统一铺装。
- 矢量地图新增校区图层（缩放到 0.045 填色、0.14 描边）与校名标注，`findPlace` 可搜索校名。

### 道路细化

- 铺装对象只有 `GEO.mapPaths` 的实测步道（61 段）：公园/校区内按公园配色，
  其余按普通园路或步行街样式；桥梁跳过，水面点过滤。
- 每段步道两端各铺一块入口小广场；校门另铺 6.4×4.2 门前硬地。
- 没有实测几何的园路、环湖路、操场跑道一律不补，避免“看起来合理但无出处”的道路。

### 性能

- 新增网格：公园内部 10 个、校门 4 个（浏览器），合计 14 个 draw call，约 11.4 万顶点（Node 合并后统计）。
- 校名牌改用 640×112 单元、2 列的 Canvas 图集并合并几何：原方案 33 块牌 × 6 个材质组约 198 个绘制组，
  现为 1 个石板网格 + 1 个印面网格；浏览器实测 `SchoolGates` 4 mesh / 3,564 顶点。
- 全部几何在 Node 中做 NaN 扫描，0 个非法顶点。

## 2. 未做与数据缺口

- 沭河公园、城北公园、孙巷公园、烈士陵园、台州路森林公园在 OSM 中没有园路，只有公园边界，
  因此无法按实测铺园路；照片中的桥、亭、廊架、广场位置也无法落到坐标，未建模。
- 梦溪植物园在渲染边界之外；建陵公园、开发区体育公园没有可核实实拍。
- 怀文中学、东关实验小学、沭河中学、师范附小、广州路实验小学、特殊教育学校、实验中学、南湖初中、
  第二实验小学等校区没有可核实的校内实拍，校门统一采用类型化石柱 + 校名牌，属**推断形制**；
  只有出入口位置来自实测道路/步道关系。
- 各校运动场在 `GEO.urban.surfaces` 中已有实测面（红色跑道、绿色球场等），本轮未改动。

## 3. 验证方式

1. `node --test`（排除依赖 bash 的 `tests/overpass.test.mjs`）：415 项全部通过，日志见 `node-tests.txt`。
   新增 `tests/park-school-interior.test.mjs` 覆盖：校区面来源、园路来自 `GEO.mapPaths`、校门证据类型、
   地图/3D 同源与 preload、校名牌图集合并。
2. Node + three@0.187.0 运行时 harness（临时目录，不写入仓库）：加载全部模块，断言无 NaN、
   碰撞盒 66 个、公园与校门统计与 `runtime-audit.json` 一致。
3. 浏览器：headless Chrome 157 + CDP，静态服务 `127.0.0.1:8123`，1600×900。截图见本目录：
   `chengbei-park-aerial.jpg`、`yuji-eco-park-aerial.jpg`、`yuji-park-furniture.jpg`、
   `shuhe-river-rail-close.jpg`、`shuhe-river-rail-close-b.jpg`、`xiuyuan-gate.jpg`、
   `renminlu-gate.jpg`、`xiuyuan-campus-aerial.jpg`、`guangyu-campus-aerial.jpg`、
   `renminlu-primary-aerial.jpg`、`city-map-campus-layer.jpg`（校区图层与校名）。
4. `tools/audit-park-school-coverage.mjs` 可重复生成 `data-audit.json` 的公园/学校覆盖清单。

## 4. 许可与署名

未改变既有许可：OpenStreetMap © contributors（ODbL 1.0）、Overture Buildings（ODbL 1.0）、
CNBH-10m（CC BY 4.0）。实拍仅作形制与颜色参考，原图不随仓库分发；参考页与发布日记录在
`tools/data/shuyang/park-interior-photo-research-20261115.md` 与
`tools/data/shuyang/school-interior-photo-research-20261115.md`。
