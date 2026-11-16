# 万顺·帝景天成影像重建验收（2026-11-15）

该地块此前在渲染中接近空地。经排查，原因不是裁剪、范围或图层遗漏，而是**数据缺口**：
OSM 只有 `landuse=residential` 地块边界（way/1321791090），地块内 0 栋 OSM 建筑，
`GEO.urban.surfaces` 在该地块也为 0；Overture 只有 32 条粗块（合并 slab、十几平方米碎片、
全部为平顶 13–19 m），与卫星影像中约 50 栋成排低层住宅不符。因此画面只剩孤立粗盒和大片灰地。

## 1. 数据来源

| 项目 | 内容 |
| --- | --- |
| 影像 | 高德卫星瓦片 `appmaptile?style=6&z=18`，约 0.494 m/px |
| 获取日期 | 2026-11-15（**不是拍摄日期**；拍摄时间未知） |
| 坐标 | GCJ-02 反算 WGS84（`tools/china-coordinates.py`） |
| 边界 | OSM `landuse=residential` way/1321791090（沿用原值，非推断） |
| 判读记录 | `tools/data/shuyang/wanshun-imagery-traces.json` |
| 生成器 | `tools/build-wanshun-imagery.py` → `reviewed-wanshun-buildings.geojson` + `wanshun-reviewed-surfaces.json` |

影像仅用于轮廓、排布与体量判读；原图不随仓库分发。

## 2. 补入内容

| 项目 | 数量 | 来源标注 |
| --- | ---: | --- |
| 别墅（一复二带花园，3 层，12 排 × 28 m 宽 × 6 m 间距） | 50 栋 | `imagery-reconstructed-villa-row` |
| 南侧弧形大棚市场（9 m 平顶） | 1 栋 | `imagery-reviewed-outline` |
| 社区内部通道（5.5 / 6 / 7 m，含东侧脊线、南门、东门支路、12 条东西向宅间路） | 15 段 | `imagery-inferred` |
| 宅间绿化带 | 12 条 | `imagery-inferred` |

- 地块 83,153 m²；新增建筑足迹 29,692 m²（35.7%）；内部通道 15,373 m²（约 2.5 km）；
  绿化带 29,867 m²。
- 别墅总高 12.4 m（含 2.8 m 四坡屋顶），层数 3 —— 来自公开小区描述（一复二带花园，
  共 3 层）与影像体量判读，**均为推断**，`heightSource=estimate`，`heightNote` 写明
  “不是测量高度”；水平误差约 ±5 m，不是逐栋实测轮廓。
- 平面通道宽度、绿化带位置按影像判读；未新增任何公共道路（外围常州路、临安东路来自 OSM）。

## 3. 实测与推断的区分

- **实测/既有来源**：地块边界（OSM）；外围道路（OSM）；地块外建筑（OSM / Overture）原样保留。
- **影像推断**：本表全部 51 栋建筑与 27 个面要素，均带 `referenceId=amap-satellite-z18-20261115`、
  `imageAcquired=null`、`geometryMethod`、`accuracyNote`，并写入 `reviewed-buildings.geojson`
  的 `additionalReferences`；`wanshun-district.test.mjs` 锁定这些标注。
- **被取代的粗块**：地块内 32 条 Overture 记录中 30 条与重建足迹重叠，标记
  `supersededSourceIds`，在三维（`GEO.supersededSourceIndices`）和矢量地图（`mapBuildings.sup`）
  同时隐藏；记录本身保留，不破坏 `building-source-order.json` 索引。OSM 记录一条也不隐藏。
  北缘 2 条（16.8 m 建筑、跨边界合并块）代表点未被重建覆盖，保留原记录。

## 4. 验证方式

1. 自动化：`node --test "tests/*.test.mjs"` → 200 项中 193 项通过；7 项失败全部来自
   `tests/overpass.test.mjs`（Windows 无 bash，`spawnSync bash ENOENT`，历史已知，与本次无关）。
   新增 `tests/wanshun-district.test.mjs`（5 项）覆盖：影像参考与拍摄日期未知、地块内 0 栋 OSM
   建筑、51 栋全部落在 OSM 边界内、推断标注、30 条 superseded 且不隐藏 OSM、地图与三维同源、
   27 个面要素与标注。
2. 构图叠合：重建足迹叠加在 z18 影像上核对行排相位、南侧大棚位置与东侧脊线避让停车带
   （上一阶段 `check-a.png` / `check-b.png`，临时目录，未入库）。
3. 运行时：headless Chrome + CDP（`127.0.0.1:8123`，1600×900）截图见本目录
   `aerial-overview.jpg`、`aerial-district-top.jpg`、`street-changzhou-road-west.jpg`、
   `street-south-gate.jpg`、`street-north-sheds.jpg`。
4. 性能：同一次浏览器会话，人民中路 & 上海中路路口 45,207 calls / 1,694,152 triangles / 56.8 fps；
   地块内 56,383 calls / 2,054,909 triangles / 56.6 fps（垂直同步上限约 57 fps，帧率无退化）。

## 5. 未做与限制

- 别墅排按街区尺度重建：同排同规格矩形、6 m 间距，未逐栋测量；个别单元与影像屋顶边缘
  可能偏移数米。
- 北缘 2 条保留粗块仍为 Overture 平顶体量，未按影像重画；大棚内部摊位、围墙、门岗未建模。
- 地块西侧临河段落、停车位、铺装材质未按影像细化；屋顶颜色与立面为类型化表现。
- 未采集地面实拍，因此没有沿街立面与院墙的实景依据。

## 6. 许可与署名

未改变既有许可：OpenStreetMap © contributors（ODbL 1.0）、Overture Buildings（ODbL 1.0）、
CNBH-10m（CC BY 4.0）。高德卫星影像仅用于定位判读，原图不随仓库分发；获取日期与拍摄日期
分开记录。
