# 万顺·帝景天成周边 2 km 环状影像重建 — 环 0（0–500 m）验收（2026-11-15）

以万顺·帝景天成地块中心 `(898.4, 2146.6)` 为圆心，按 500 m 分环向外推进。
本目录记录**第一环（0–500 m）**的空地审计、影像判读、补入结果与验收；
环 1–3 的审计数字见 `docs/refinement/ring-audit.json`，验收文档在各环完成后追加。

## 1. 审计口径

`tools/audit-imagery-rings.py`，100 m 网格，只有落在 OSM
`landuse=residential|commercial|retail|industrial` 多边形内、且裁剪面积 ≥ 40% 的格子才计入：

| 指标 | 判据 |
| --- | --- |
| 空地（empty） | 格内建筑足迹覆盖率 < 12%（"有地块但无建筑"） |
| 粗块（coarse） | 格内所有足迹均 > 900 m²（合并 slab，与影像成排住宅不符） |
| 内部无通道（noLane） | 无 `residential/service/unclassified/living_street` 道路穿越 |

内部通道分两类计数：OSM 实测 way（`mapped`）与 `community-path` 推断面（`inferred`）。

### 环 0 审计结果

| 时点 | 格数 | 空地格 / 面积 | 粗块 | 无内部通道 | 实测通道格 | 推断通道格 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 重建前 | 43 | 18 格 / 15.84 ha | 1 | 23 | — | — |
| 重建后 | 43 | **2 格 / 0.97 ha** | **0** | **0** | 7 | 41 |

剩余 2 格位于沃德嘉园东南角，高清判读确认为土方堆场、行道树与河岸绿化带，**不是漏补楼体**，
已在 `imagery-districts-traces.json` 写入 `east-river-belt` 排除区，并铺为绿地面。

## 2. 数据来源

| 项目 | 内容 |
| --- | --- |
| 影像 | 高德卫星瓦片 `appmaptile?style=6&z=18`，约 0.494 m/px |
| 获取日期 | 2026-11-15（**不是拍摄日期**；拍摄时间未知） |
| 坐标 | GCJ-02 反算 WGS84（`tools/china-coordinates.py`） |
| 地块边界 | OSM `landuse` way/1321791085（沃德嘉园）、way/1321791091（金禾理想城）、way/1321791104（新江南）——沿用原值 |
| 判读记录 | `tools/data/shuyang/imagery-districts-traces.json` |
| 生成器 | `tools/build-imagery-districts.py` → `reviewed-imagery-districts.geojson` + `imagery-districts-surfaces.json` |

## 3. 补入内容（全部为影像推断）

| 小区 | 行排建筑 | 足迹面积 | 内部通道 | 绿化/非建设用地 |
| --- | ---: | ---: | ---: | ---: |
| 沃德嘉园 | 111 栋 | 27,832 m² | 7 段 / 13,834 m² | 57 面 / 37,606 m² |
| 金禾理想城 | 94 栋 | 28,364 m² | 5 段 / 9,087 m² | 35 面 / 16,659 m² |
| 沭阳县新江南小区 | 74 栋 | 26,702 m² | 5 段 / 11,324 m² | 41 面 / 34,216 m² |
| 合计 | **279 栋** | **82,898 m²** | **17 段 / 34,245 m²** | **133 面 / 108,481 m²** |

- 279 条足迹中 277 条进入来源记录（`building-source-order.json` 尾部追加，索引 7793 起），
  2 条与既有 OSM 足迹重叠超过 20%，按 `enrich-shuyang-buildings.py` 的既有规则被拒绝；
  建筑来源记录 7,793 → **8,070**，其中 `ReviewedImagery` 235 → **512**。
- 行排规格（行中心 Z 起点 / 行距 / 进深 / 单元宽 / 间距 / 层数 / 总高）：

| 小区 | 行排 | 参数 |
| --- | --- | --- |
| 沃德嘉园 | 北区 | startZ 1736，pitch 33.6，depth 13，unit 24+8 m，5 层 / 15.2 m |
| 沃德嘉园 | 南区 | startZ 2087，pitch 33.4，depth 14，unit 26+8 m |
| 金禾理想城 | 沿街 | startZ 2064，pitch 40，depth 16，unit 32 m，3 层 / 11.0 m（商业） |
| 金禾理想城 | 内部 | startZ 2088，pitch 36.0，depth 14，unit 24+9 m，5 层 / 16.0 m |
| 新江南 | 北区 | startZ 2418，pitch 37.1，depth 13，unit 34+10 m |
| 新江南 | 南区 | startZ 2663，pitch 36.6 |

- 行中心取「地块内已有足迹的行中心聚类」（10 m 容差），而不是亮度剖面峰值——
  院内铺装带会把亮度峰值带偏一行；倾角取地块内已有足迹最小外接矩形中位角
  （沃德嘉园 3.0°、金禾 5.5°、新江南 5.0°），并**锚定小区质心**旋转。
- 每 3 排一条东西向宅间通道（5.5 m），另按判读补南北向主轴；通道/绿化面均带
  `geometryMethod`、`referenceId`、`retrievedAt`、`imageAcquired: null`。

## 4. 实测与推断的区分

- **实测/既有来源**：三个地块边界、外围道路、地块内原有 OSM/Overture 建筑，
  一条未删、一条未改；Overture 粗块本轮**没有**被标记 superseded（新足迹均绕开既有足迹，
  用相减而非整格丢弃，重叠处保留原记录）。
- **影像推断**：279 栋建筑 `geometrySource=imagery-reconstructed-row-block`、
  `heightSource=estimate`、`imageAcquired=null`、`referenceId=amap-satellite-z18-20261115-rings`，
  `heightNote` 写明"按 N 层砖混行列住宅推断……不是测量高度"，
  `geometryAccuracyNote` 写明"水平误差约 ±6 m，非实测轮廓"。
- **被排除的非建设用地**：沃德嘉园院心圆形绿地、东侧土方/河岸带
  （`[[714,2125],[800,2125],[800,2370],[714,2370]]`）、新江南西南农田
  （`[[410,2640],[560,2645],[556,2950],[410,2950]]`）——不建楼，铺绿地面，判读理由写入 traces。
- 沃德嘉园的实测细部模块（`js/wode-district.js`，坡屋面、阳台、车位）只作用于
  已测绘足迹；`reviewed/imagery/*` 行走 `buildings.js` 通用渲染，避免把推断体块
  当成实测轮廓追加精细构件（`tests/wode-district.test.mjs` 锁定）。

## 5. 验证

1. 自动化：`node --test "tests/*.test.mjs"` → 200 项中 193 通过；7 项失败全部来自
   `tests/overpass.test.mjs`（Windows 无 bash，`spawnSync bash ENOENT`，历史已知，与本次无关）。
   `python -m unittest` 2 项通过。基线更新：建筑 8,070、`mapBuildings` 8,074、
   `ReviewedImagery` 512、`building-geodata.bin.gz` sha256
   `83282f4b…ba677`（与环状重建前一致——本轮只改 sources 与 surfaces，未改打包格式）。
2. 环审计：`tools/audit-imagery-rings.py` → `docs/refinement/ring-audit.json`。
3. 判读叠合：推断足迹叠在 z18 影像上核对行排相位、朝向与河道/农田避让
   （临时目录裁剪图，未入库）。
4. 运行时：headless Chrome + CDP（`127.0.0.1:8123`，1600×900）
   `ring0-overview-2km.jpg`、`ring0-wood-jiayuan-top.jpg`、`ring0-jinhe-top.jpg`、
   `ring0-xinjiangnan-top.jpg`、`ring0-street-inside-wood.jpg`、`ring0-street-inside-xinjiangnan.jpg`。
5. 性能（同一次会话，`renderer.info` 按帧归一化）：

| 位置 | draw calls / 帧 | 三角形 / 帧 | fps |
| --- | ---: | ---: | ---: |
| 人民中路 & 上海中路 | 238 | 9,623 | 60.0 |
| 万顺·帝景天成 | 318 | 16,893 | 54.6 |
| 沃德嘉园中心 | 365 | 15,626 | 56.4 |
| 金禾理想城中心 | 428 | 12,840 | 55.9 |
| 新江南中心 | 526 | 17,803 | 51.2 |

   与上一批（万顺地块 56.6 fps）同量级，帧率仍在 51–60；draw call 随视野内建筑数增长，
   但新增建筑并入 `buildings.js` 的合并几何与实例化批次，未出现数量级跳升。

## 6. 未做与限制

- 行排为街区尺度重建：同排同规格矩形，被既有足迹裁剪，未逐栋测量；个别单元与影像
  屋顶边缘可能偏移数米（声明 ±6 m）。
- 层数按可见体量与类型推断，5 层/3 层为类型化取值，不是房产登记层数。
- 屋顶颜色、立面为通用渲染，未按影像逐栋区分；沿街商业立面未单独建模。
- 院内车位、围墙、门岗、单元入口未新增；这些细节仅存在于已测绘的沃德嘉园细部模块中。
- 南侧农田仅铺绿地面，未做垄沟/作物纹理。
- 未采集地面实拍，因此没有新补建筑的实景立面依据。

## 7. 许可与署名

未改变既有许可：OpenStreetMap © contributors（ODbL 1.0）、Overture Buildings（ODbL 1.0）、
CNBH-10m（CC BY 4.0）。高德卫星影像仅用于定位判读，原图不随仓库分发；
获取日期与拍摄日期分开记录，`imageAcquired` 保持 `null`。
