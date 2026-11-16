# 批2 空地补全 — 12 个整片空地小区 + 3 所空地学校（2026-11-15）

清单来源：[设施/地块盘点](../../facility-inventory/shuyang-facilities.csv) 中"建议批次 = 批2 空地补全"的 15 条
（状态码 C：有 OSM 地块边界但渲染为空地），编号 SY-045 … SY-059，集中在南部新城与东南片区。

本轮把这 15 个地块按卫星影像补出楼排、内部通道与绿化面；**15 块全部做了判读与重建**，
其中 13 块完整进入地图，SY-057 只发布了北侧在框部分、SY-059 只有 1 栋在框内（见第 5 节）。

## 1. 影像来源与判据

| 项 | 值 |
| --- | --- |
| 参考影像 | `amap-satellite-z18-20261115-blankplots`（高德 z18 卫星瓦片拼合，GCJ-02 反算 WGS84） |
| 分辨率 | 0.494 m/px |
| 获取时间 | 2026-11-15（拼接下载）；瓦片本身未标注成像日期，`imageAcquired` 留空，不假装有日期 |
| 判读辅助 | 25 m 网格 + 50 m 坐标标签叠合页（`z/x` 读数），逐块量排距、单体长宽、朝向 |
| 地块边界 | **沿用 OSM 原值**（`osm_land.json` / `osm_school_grounds.json`），不改、不外扩 |
| 已知误差 | 平面水平误差约 ±6 m；叠合时影像整体相对 OSM 略偏北约 10–20 m，属瓦片配准，未追偏移，按地块内缩 2 m 保守裁剪 |

判读纪律（与 `tools/build-wanshun-imagery.py`、`reviewed-buildings.geojson` 一致）：

- 每栋建筑带 `geometrySource`：`imagery-reconstructed-row-block`（行排）/ `imagery-reconstructed-footprint`（逐栋描边）；
- 每条 `geometryReference` 带 `referenceId`、`retrievedAt`、`imageDate`、`accuracyNote`；
- 高度写 `heightNote`（按层数/体量推断），`heightSource` 为 `estimate`，**不写成测量值**；
- 与既有 OSM/Overture/已复核足迹重叠时让位：生成器先减去既有足迹、水体与道路走廊，
  而不是覆盖或删除别人的记录。

## 2. 数据链与代码改动

新增（全部为本轮独立文件，不与他人数据混写）：

| 文件 | 作用 |
| --- | --- |
| `tools/build-blank-plots-imagery.py` | 读判读源数据 → 生成足迹与面要素，输出审计计数 |
| `tools/data/shuyang/blank-plots-imagery-traces.json` | 15 块的判读源数据（行列参数、显式建筑、面、排除区、通道、判读备注） |
| `tools/data/shuyang/reviewed-blank-plots.geojson` | 生成物：366 条足迹 + 地块索引 + `reference`/`additionalReferences` |
| `tools/data/shuyang/blank-plots-surfaces.json` | 生成物：164 个面（通道 / 绿地 / 跑道 / 球场 / 广场） |

共享文件只做单点小改（改前重新读取，不动他人改动）：

| 文件 | 改动 |
| --- | --- |
| `tools/build-shuyang-reviewed-district.py` | ① 在批1 之后追加批2 的 `blank_path` 合并块与 `blank_refs`；② surfaces 追加 `blank-plots-surfaces.json`。其余行未改 |
| `tools/enrich-shuyang-buildings.py` | ① supersede 计算从"万顺单地块"推广为 `scopes` 列表（万顺 + 15 个批2 地块，按 ID 前缀归属）；② 冲突豁免元组加 `reviewed/imagery/blank/`；③ 越界足迹在审计里补 `reason`，把"模型边境外"与"轮廓无效"分开 |

生成物（重建后自动更新）：`reviewed-buildings.geojson`、`reviewed-district-surfaces.json`、
`buildings-enriched.json.gz`、`building-source-order.json`、`js/building-geodata.bin.gz`、
`js/shuyang-geodata.js`、`docs/refinement/coverage.json`。

## 3. 逐条结果

"发布/判读"为进入地图的栋数 / 描出的足迹数；"面"为内部通道、绿地、跑道、球场、广场、排除面。

| 编号 | 名称 | 判读形态 | 发布/判读 | 面 | 体量（推断） |
| --- | --- | --- | ---: | ---: | --- |
| SY-045 | 中央花园 | 行列住宅 + 中央绿轴 | 53/53 | 29 | 5–6 层，排距 27 m，单元 42 m + 间距 14 m |
| SY-046 | 福达国际城 | 东侧 3 层联排 + 西侧温室/厂房列 | 89/89 | 29 | 3 层 11.4 m；西侧 4 栋东西向大跨 7–8 m |
| SY-047 | 汇金新城（南区） | 大跨市场/仓储大棚围合中央绿地水塘 | 12/12 | 4 | 1–2 层 7–10 m |
| SY-048 | 明厚源紫玉庄园 | 大跨金属坡顶厂房/仓储 + 门房 | 9/9 | 3 | 1 层 9–10 m，门房 4.5 m |
| SY-049 | 智慧路初级中学 | 3 组 C 形教学楼 + 风雨操场 + 400 m 跑道 + 2 球场 | 9/9 | 6 | 4 层 16.8 m 教学楼；跑道内场挖空 |
| SY-050 | 小太阳幼儿园 | 3 层回字形 + 蓝色连廊 | 4/4 | 3 | 3 层 11 m，连廊 7 m |
| SY-051 | 东城幼儿园 | 3 层 L 形园舍 | 2/2 | 2 | 3 层 11 m |
| SY-052 | 新康景园 | 4 排 5–6 层板楼 | 15/15 | 10 | 16–18 m |
| SY-053 | 华脉金樾府 | 5 排 6 层坡顶住宅 | 15/15 | 8 | 18 m，坡顶 |
| SY-054 | 教工住宅小区 | 5 栋大跨浅色金属坡顶 | 5/5 | 3 | 1 层 8–9 m |
| SY-055 | 荣润麒麟府 | 已封顶 6 层 + 南侧联排；东半部在建 | 12/12 | 3 | 18 m / 联排 12 m；在建区只铺裸土面 |
| SY-056 | 盛唐世家 | 4–5 排 5 层坡顶住宅 | 9/9 | 7 | 15.5 m，单元 28 m + 间距 10 m |
| SY-057 | 明厚源·轩府 | 10 排 3 层联排/叠墅 + 东南角商业 | **16/89** | 21 | 12 m；83% 地块在模型框外 |
| SY-058 | 崇文公寓 | 2 栋 5 层公寓 | 2/2 | 3 | 16 m |
| SY-059 | 湾河丽景小区 | 7 排 6–8 层板楼 + 配套 | **1/41** | 33 | 18–20 m；99% 地块在模型框外 |
| 合计 | — | — | **253/366** | **164** | 足迹面积 152,869 m²（已发布部分） |

面要素合计：社区通道 36 段 / 44,165 m²，绿地 121 面 / 158,623 m²，广场 3 面 / 19,788 m²，
跑道 1 面 / 3,123 m²（内场已挖空），球场 3 面 / 9,110 m²。

### 登记类别与影像形态不一致（6 处，未改清单，只在地块与要素上标注）

- SY-046 西侧实为温室/厂房列；SY-047 为大跨市场大棚；SY-048 为厂房/仓储；SY-054 为大跨厂房尺度；
  SY-055 东半部混在建；SY-057 / SY-059 清单占地与 OSM 地块面积明显不符。这些均写进 trace 的
  `reading.typeConflict` / `reading.unresolved`，未静默按"住宅小区"建住宅。

## 4. 实测与推断的分界

| 内容 | 性质 |
| --- | --- |
| 地块边界、外围道路、水体、周边既有建筑 | **OSM 实测**，未改一顶点 |
| 15 块内部的建筑位置、栋数、排距、单体尺寸、层数/高度 | **影像推断**（本文件第 1 节的误差与来源已写进每条要素） |
| 内部通道（`community-path`）、绿地面、跑道/球场/广场 | **影像推断**，来源与获取时间同上 |
| 在建工地、水塘、既有足迹 | 作为排除区，不建体量 |

运行时每条记录的 `geometryReference.accuracyNote` 都会带上"0.494 m/px、遮挡、±6 m、非实测轮廓"的说明，
矢量地图与 3D 详情面板读同一字段，不会把推断显示成实测。

## 5. 未做 / 受边界限制的部分

1. **模型框（CORE）边界**：发布世界固定为 `x −3200…3400, z −2400…5000`（`build-shuyang-geodata.mjs` 与
   地面/道路/水体一致）。SY-057 只有北侧约 17% 落在框内 → 89 栋里 73 栋被裁；SY-059 只有约 0.7% 落框
   → 41 栋里 40 栋被裁。这 113 条足迹**保留在 `reviewed-blank-plots.geojson` 里**（有坐标、有来源），
   只是不进运行时；enrich 审计把它们标为"越界（非轮廓无效）"。扩框会牵动地面、路网、水面与切块，
   属跨会话的大改，本轮不动。
2. **SY-049 跑道南端**：真实跑道到 `z≈5013`，超出 5000，发布时被框线切掉南端约 13 m。
3. **SY-055 东半部**：只建已封顶的 4 栋，未封顶/塔吊区按裸土广场面处理，不造体量。
4. **SY-051 园舍北侧**：被邻近建筑长阴影遮挡，进深按可见边界取保守值。
5. **SY-050 蓝色屋面**：连廊还是多功能厅未能确认，按连廊建 7 m 高。
6. **地块边缘**：6 个候选因裁剪后面积 < 120 m² 丢弃（`droppedEdge`），131 个候选落在绿地/广场/在建排除区
   （`droppedExclusion`），不计为遗漏。

## 6. 被替代的旧粗块

本轮 15 块在 Overture/OSM 里本来就是空的（`droppedExisting = 0`），**批2 自身没有需要替代的旧粗块**。
enrich 审计里 31 条 `supersededSourceIds` 全部来自并行的万顺地块重建（30 条 Overture）与上游显式声明
（1 条 OSM way），做法不变：记录留在抽取里保索引，只在渲染/地图上隐藏，不删记录。

## 7. 渲染与性能

无头 Chrome（Windows，1440×900，`?debug`）逐块停在街景上方 230 m / 距 170 m 俯视测 1.5 s：

| 指标 | 15 个地块 | 未改动的核心区参考（人民中路，同机位） |
| --- | --- | --- |
| 帧率 | 56.2 – 57.0 fps | 56.6 fps |
| draw call / 帧 | 22 | 22 |

- 帧率与参考区一致，**无退化**；draw call 在 15 个机位完全没有变化，说明新增 253 栋被并入既有分块批次，
  没有新增独立绘制对象。
- 建筑总数 8,742（ReviewedImagery 1,184），本轮新增 253 栋、164 个面。
- 截图：见本目录 `blank-sy-0xx-*.jpg`；`blank-reference-core.jpg` 为同机位核心区参考。

## 8. 复现

```powershell
.\.venv\Scripts\python.exe tools\build-blank-plots-imagery.py
.\.venv\Scripts\python.exe tools\build-shuyang-reviewed-district.py
.\.venv\Scripts\python.exe tools\enrich-shuyang-buildings.py
.\.venv\Scripts\python.exe tools\build-shuyang-urban.py
node tools/build-shuyang-geodata.mjs
node tools/audit-photo-refinement.mjs
node --test "tests/*.test.mjs"
```

`build-blank-plots-imagery.py` 会打印每块 `kept` 与总审计计数，可比对第 3 节。
测试：除 7 个 Overpass 用例在本机因缺 `bash` 报 `spawnSync bash ENOENT`（与数据无关的历史问题）外，
其余用例通过。

## 9. 截图索引

| 文件 | 内容 |
| --- | --- |
| `blank-sy-045-central-garden.jpg` … `blank-sy-059-wanhe-lijing.jpg` | 15 个地块的街景俯视 |
| `blank-reference-core.jpg` | 未改动核心区同机位参考（性能对照） |
