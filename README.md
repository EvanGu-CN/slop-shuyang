# Slop 沭阳

江苏沭阳城区的三维漫游项目，基于 Three.js WebGPURenderer 与 TSL 着色器，支持步行、驾车、骑行、直升机、实时小地图和可搜索的全屏街道图。

[在线体验](https://evangu-cn.github.io/evans-github-pages/slop-shuyang/) · [源码仓库](https://github.com/EvanGu-CN/slop-shuyang) · [持续还原进度](docs/BUILDING_REFINEMENT_PROGRESS.md) · [开发约定](AGENTS.md)

项目沿用 [Slop New York](https://github.com/mrdoob/slop-newyork/) 的渲染、交通、行人与音频引擎，将城市内容替换为沭阳；城区组织和加载策略也参考了 [Slop 武汉](https://github.com/LightYearZh/slop-wuhan)。原项目版权与 MIT 许可证保留。

## 当前范围与还原边界

现有研究范围东西约6.6公里、南北约7.4公里，覆盖人民路、上海路、北京路、苏州路、南湖及政务中心等城区。乡镇与开发区远端不在当前范围内。

截至2026-11-15，已提交数据包含：

| 项目 | 数量 |
| --- | ---: |
| 建筑来源记录 | 9,977 |
| OSM / Overture增量 / 影像核对补录 | 1,425 / 6,133 / 2,419 |
| 数据中的地图建筑部件 | 9,982 |
| 道路来源way / 渲染分段 | 1,104 / 1,105 |
| 地图步道与自行车道 | 92 |
| 可传送地标 | 21 |
| 具名小区近似范围 | 147 |

专用模型还会拆分展示体块；来源数、地图部件数和模型体块数不能混用。数据量不代表现实城区已经全部收录，也不代表逐栋实景还原已完成。5,264条来源采用CNBH估高、1条采用OSM高度标签、1条采用核对层数、3,774条为展示估高；实拍引导的展示高度与原来源高度分别保留。

近期细化包括：

- 中央商场：保留L形裙房与独立主塔来源，按消防报道使用147.15米展示楼体及14/29层信息，补浅框、暖灰竖板和成对窗格；北侧有限入口段按实拍近似细化，完整楼顶和精确门位仍未核实。
- 蓝天商贸城：门架按拍卖实拍改为单层实体顶板，保留真实圆洞与条形天窗，补细银柱与镂空粉色题字；楼顶按卫星像素补低多边形采光面、东侧露台铺面与三块近似绿化区，地图共用平面。高度、材质、洞口数量/尺寸和门位仍估计，未据此核实整座市场的实际楼体或新增28层塔楼。
- 南部文化馆群：美术馆分散体块、弧面红厅、光井、入口水面与波纹铺地；图书馆与博物馆按影像收回主体、恢复前场。南侧缺失楼体以“档案馆（位置推定）”补录，仅细化可见屋顶。
- 道路：连续矢量路缘；台州路珠海路—杭州路的六车道标准断面、非机动车道和景观带；兰亭路西侧、承晖路北侧的部分馆前步行带与绿带；人民路商圈东北角的蓝色/红褐色沿街铺装带，按历史实拍和卫星位置近似细化，避开道路与楼体。
- 万顺·帝景天成：OSM 无建筑的空缺地块按卫星影像补 50 栋三层别墅、1 栋南侧大棚与社区内部通道/绿化，全部标为影像推断，30 条 Overture 粗块由重建取代。
- 万顺周边 2 km 环状影像重建（环 0，0–500 m）：沃德嘉园、金禾理想城、新江南三个小区按影像行排补 279 栋推断建筑与 17 段内部通道、133 个绿地/非建设面，环内空地格 18 → 2（剩余为土方与河岸）。
- 万顺周边 2 km 环状影像重建（环 1，500–1000 m）：美好家园、翰林府第、浦东国际、金地花园、皇冠世纪、舒城一品六个地块补 418 栋行排/厂房与 61 段内部通道、128 个绿地/非建设面；凤凰国际城、天下景城、苏通花苑、颖都家园只补通道不加楼。环内空地格 31（24.41 ha）→ 0，无内部通道格 39 → 0。
- 万顺周边 2 km 环状影像重建（环 2，1000–1500 m）：阳光天地、欧洲城、仰龙湾、祥和小区、上海阳城西侧仓储补 298 栋行排与坡屋顶联排，含 1 处 120 m² 单元下限导致的联排单元宽度修正；16 个有楼无通道小区按足迹行距补内部通道，通道面由 355 增至 755；健康家园、美好家园、新康景园的停车院，人和小区、巴黎新城的菜地，嘉瑞玫瑰园的别墅院落按影像铺地面。环内空地格 47（37.84 ha）→ 0，无内部通道格 43 → 0，影像判读为既有建成而非空地的格单列 surfaced。
- 万顺周边 2 km 环状影像重建（环 3，1500–2000 m，2 km 范围最外环）：沭城天下及二期/三期、碧桂园按影像行排补 96 栋，其余 11 个地块统一 6 层规整回填 532 栋（宁浦云庭 15 层、健康家园 5 层按影像取层），共 628 栋；7 个只缺通道的地块按足迹行聚类补 298 段内部通道，15 个重建地块同步补行间横向通道；人和小区西侧铁路路堤旁用绿化带闭合最后一格。环内空地格 54（43.79 ha）→ 0，无内部通道格 22 → 0，2 格影像判读为绿地。
- 万顺周边 2.5 km 环状影像重建（环 4，2000–2500 m）：汇金新城、东郊住宅、南湖郡、帝景佳园天悦、如意庄园、昊园、观澜府、荣盛鑫城八个地块按影像行排补 309 栋，3 个只缺通道的地块（商贸批发中心、城市枫林西区、湖玺庄园）补 95 段内部通道，8 个重建地块同步补 82 段行间横向通道；汇金新城东缘河岸绿化带、南湖郡东侧停车广场、汇金南区停车院落、西侧农田按影像铺地。环 4 圆盘完全落在发布框内（东侧余量 1.6 m），未扩框。环内空地格 57（46.28 ha）→ 0，无内部通道格 19 → 0，6 格影像判读为非建设面。至此 0–2500 m 五环空地格、无通道格全部归零，合计补 1,932 栋；第二批与环 4 均为整地块统一层数回填，未逐栋判读异形楼。
- 中医院、政务服务中心、维也纳、久盛百货、学校及住宅街区的已登记实拍细节。

详见[逐条核对清单](docs/refinement/README.md)、[验收目录](docs/acceptance/)与[数据方法和限制](tools/data/shuyang/BUILDINGS.md)。照片发表日、获取日与拍摄日分开记录；未标日期的图片不能当作2026现状。

## 本地运行

项目是纯静态网站，无需前端构建：

```bash
git clone https://github.com/EvanGu-CN/slop-shuyang.git
cd slop-shuyang
python -m http.server 8123
```

打开 [http://127.0.0.1:8123/](http://127.0.0.1:8123/)，使用支持WebGPU并已启用硬件加速的浏览器。首次启动需要加载Three.js CDN模块；矢量地图本身不请求在线瓦片，实景参考图片与外部地图链接需要联网。运行页面应通过HTTP服务打开。

可用 `?tp=central`、`?tp=culture`、`?tp=shiyan` 等直达地标；`?building=vienna` 等打开已登记沿街建筑观察点；`?debug` 提供开发调试入口。

## 操作

| 按键或界面 | 功能 |
| --- | --- |
| `1` / `2` / `3` / `4` | 步行 / 驾车 / 骑行 / 直升机 |
| `W S A D` | 移动、转向 |
| 按住 `Shift` / 点击“加速” | 临时加速 / 持续加速 |
| `Space` | 跳跃、刹车或上升，随出行方式变化 |
| `M` / 点击小地图 | 全屏街道图与地点搜索 |
| `V` | 切换机位 |
| `H` / `N` / `B` | 隐藏界面 / 静音 / 鸣笛 |

触屏提供移动摇杆与动作按钮。传送菜单可查看地标、沿街建筑、道路和小区的实景参考、来源、日期及建模限制。

## 开发与验证

日常修改直接编辑HTML、CSS和ES模块。几何生成与审计使用Python、Shapely 2和Node.js；本次验证环境为Node.js 24、Python 3.12，依赖见[requirements-buildings.txt](tools/requirements-buildings.txt)。

Windows PowerShell：

```powershell
$cases = Get-ChildItem tests -File |
  Where-Object { $_.Name -match '\.test\.(cjs|mjs)$' -and $_.Name -ne 'overpass.test.mjs' } |
  ForEach-Object FullName
node --test $cases
python -m unittest discover -s tests -p 'test_*.py'
```

当前基线为410项Node与2项Python通过；另7项Overpass测试需要Bash，以上Windows命令明确排除该文件，不计入通过数。在具备Bash的环境可另行运行：

```bash
node --test tests/overpass.test.mjs
```

模型、材质或定位修改还应检查实际浏览器画面；数值测试不能替代实景身份核对。源码与已发布版本的验收证据保存在 `docs/acceptance/`，没有逐栋证据的状态不标为完成。

## 地理数据与生成

世界坐标按1单位=1米组织，`x`向东、`z`向南，原点为人民中路与上海中路交叉口附近。OSM来源、Overture建筑增量、估高与逐个核对的影像补录均保存在 `tools/data/shuyang/`。

数据生成工具需要Python 3.12或更新版本，当前锁定的rasterio要求Python ≥3.12；仅启动静态HTTP服务无需安装这些数据依赖。请确认下面的 `python` 指向符合版本的解释器，再创建独立环境：

```bash
python -m venv .venv
# 激活虚拟环境后
python -m pip install -r tools/requirements-buildings.txt
```

Windows也可用 `py -3.12 -m venv .venv` 创建环境，之后通过 `.\.venv\Scripts\python.exe` 执行脚本，避免误用系统中的旧版Python。

如需从已提交观察记录重新生成基础层，按依赖顺序运行：

```bash
python tools/build-shuyang-online-district.py
python tools/build-shuyang-reviewed-district.py
python tools/build-shuyang-reviewed-water.py
python tools/enrich-shuyang-buildings.py
python tools/build-shuyang-urban.py
python tools/build-shuyang-landmarks.py
python tools/build-shuyang-communities.py
node --max-old-space-size=8192 tools/build-shuyang-geodata.mjs
```

生成器使用Shapely 2构建矢量路缘，优先选择项目 `.venv`，也可设置 `SHUYANG_PYTHON`。新增建筑必须维护 `building-source-order.json`，将新来源追加，保持旧来源索引稳定；不要手工编辑生成的 `js/shuyang-geodata.js` 或压缩二进制。

相关增量工具：

```bash
python tools/build-taizhou-corridor.py
python tools/build-cultural-streets.py
python tools/build-wanshun-imagery.py
node tools/audit-photo-refinement.mjs
```

仅在对应观察记录变动时运行相关生成器，并检查输出差异、来源绑定、地图与碰撞。首次下载、去重、坐标转换和数据许可的详细方法见[BUILDINGS.md](tools/data/shuyang/BUILDINGS.md)。

### 公园与学校内部

- 校区边界来自 Overpass `amenity=school|kindergarten|college|university out geom`（2026-11 快照），
  裁剪后 40 个写入 `GEO.schoolGrounds`；矢量地图与三维场景共用同一份数据，可搜索校名。
- 校门位置取“实测步道穿越校区边界”优先，否则取边界上最贴近实测道路的顶点；牌面文字取 OSM 校名。
- 公园与校区内部的园路只铺 `GEO.mapPaths` 的实测步道；铺装配色与临水石栏样式按公开实拍
  （沭河公园 2019-06、城北公园 2021-12、梦溪植物园 2026-01）确定。没有实测园路的公园不补路、
  不臆造环湖路或桥位。
- 座椅/垃圾桶/园灯间距、门柱尺寸属类型化推断，实拍只作样式参考；照片原图不随仓库分发。

### 万顺·帝景天成影像重建

- 该地块在 OSM 中只有 `landuse=residential` 边界（way/1321791090），地块内没有建筑轮廓，
  也没有内部道路；此前的 32 条 Overture 粗块（合并 slab 与十几平方米碎片）就是全部体量，
  所以画面接近空地。这不是裁剪或图层遗漏。
- 以高德 z18 卫星影像（约 0.494 m/px，2026-11-15 获取，拍摄日期未知）判读行排，
  补 50 栋 3 层别墅（12 排、28 m 宽、6 m 间距、12.4 m 含四坡屋顶）与南侧弧形大棚（9 m）；
  另补 15 段社区内部通道和 12 条宅间绿化带。外围公共道路仍取 OSM，不新增。
- 以上全部标注 `geometrySource=imagery-reconstructed-villa-row` / `imagery-reviewed-outline`、
  `heightSource=estimate`、`imageAcquired=null`，水平误差约 ±5 m，不是逐栋实测；
  判读记录在 `tools/data/shuyang/wanshun-imagery-traces.json`。
- 与重建重叠的 30 条 Overture 粗块标记为 superseded，在三维与矢量地图同时隐藏（记录保留，
  不破坏来源索引）；OSM 实测记录一条也不隐藏。验收见
  [docs/acceptance/wanshun-imagery-2026-11-15/](docs/acceptance/wanshun-imagery-2026-11-15/)。

### 万顺周边 2 km 环状影像重建

- 以万顺地块中心 `(898.4, 2146.6)` 为圆心，按 0–500 / 500–1000 / 1000–1500 / 1500–2000 m
  分环推进，每环先跑 `tools/audit-imagery-rings.py`：100 m 格内建筑覆盖率 < 12% 记为
  "有地块但无建筑"，格内足迹全部 > 2,500 m² 且类别全为住宅/未知记为"粗块与影像不符"，
  无内部道路穿越记为"有路网但内部无通道"（900 m² 的旧阈值会把 80×15 m 的正常板楼误判为粗块）。
- 判读结果写进 `tools/data/shuyang/imagery-districts-traces.json`（行距、进深、单元宽/间距、
  倾角、层数、内部通道、排除区），由 `tools/build-imagery-districts.py` 生成足迹与面要素。
- 生成规则：行中心取地块内已有足迹的行中心聚类，倾角锚定小区质心；已有足迹/水体/道路走廊
  用**相减**而非整格丢弃；被排除的院心绿地、河岸土方、农田铺为绿地面，不留裸地。
- 全部标为影像推断（`imagery-reconstructed-row-block`、`heightSource=estimate`、
  `imageAcquired=null`、±6 m），旧粗块不删不改。环 0 验收见
  [docs/acceptance/ring0-imagery-2026-11-15/](docs/acceptance/ring0-imagery-2026-11-15/)。

## 主要目录

| 路径 | 内容 |
| --- | --- |
| `index.html`、`css/` | 页面、交互入口和样式 |
| `js/main.js`、`js/city-config.js` | 启动、城区配置和传送点 |
| `js/city-grid.js`、`js/road-ribbon.js` | 地面、道路、水体与连续路缘 |
| `js/buildings.js`、`js/building-geodata.js` | 来源建筑渲染、解码与细节 |
| `js/landmarks.js`、各建筑/街区模块 | 专用模型、来源绑定和展示估计 |
| `js/city-map.js` | 与三维场景共用数据的矢量地图 |
| `js/landmark-references.js`等 | 参考图片、署名、时点和限制 |
| `tools/`、`tools/data/shuyang/` | 观察记录、数据管线和审计 |
| `tests/` | 几何、来源、交互及启动回归 |
| `docs/refinement/`、`docs/acceptance/` | 持续清单、逐批证据与验收 |

## 提交与发布

本仓库 `EvanGu-CN/slop-shuyang` 维护源码，主分支为 `main`。原项目保留为 `upstream`；不要向 `mrdoob/slop-newyork` 推送沭阳修改。

线上站点继续由 [evans-github-pages](https://github.com/EvanGu-CN/evans-github-pages) 的 `main/slop-shuyang/` 目录发布。源码仓库推送不会自动同步到该站点；发布时只更新目标子目录，保留其他游戏与未关联文件。`deployment-manifest.json`记录来源提交及每个运行文件的长度、SHA-256。

先完成验证并提交，再打包已提交运行文件：

```bash
python tools/package-static-site.py
```

工具要求源码工作区干净，输出至被忽略的 `.releases/`。同步目标目录后应核对manifest、目标测试、Pages工作流和线上实际文件；不要把本地成功当作已部署成功。

## 许可与署名

代码采用 [MIT License](LICENSE)，保留Mr.doob原版权声明。

- **OpenStreetMap**：© OpenStreetMap contributors，ODbL 1.0。地图、道路、轮廓、水系、POI和地名保留署名；衍生数据库按相应许可再分发。
- **Overture Buildings 2026-10-21.0**：© Overture Maps Foundation，ODbL 1.0；裁剪记录保留原始来源属性。
- **CNBH-10m**：Wanben Wu，2020年建筑高度模型，[DOI 10.5281/zenodo.7923866](https://doi.org/10.5281/zenodo.7923866)，CC BY 4.0。本项目进行城区裁剪、像元统计和高度量化。
- **3D-GloBFP**：保留可选匹配支持，未纳入当前发布数据。
- **实拍与研究影像**：版权归原作者/服务提供者；参考面板保留来源和署名。高德、Esri / Vantor等影像仅用于定位研究，原图目录不提交，不作为建筑贴图分发。已知2021年影像与采集日未知的影像分别标记，获取日期不等于拍摄日期。
