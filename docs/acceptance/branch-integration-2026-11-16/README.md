# 主分支整合验收 — 2026-11-16

## 分支与范围

- 操作前工作区干净；本地分支只有 `main` 和 `codex/shuyang-city-refinement-20261114`。
- 已执行 `git fetch origin --prune`，源码远程为 `https://github.com/EvanGu-CN/slop-shuyang.git`；远程仅有 `main`，指向 `c21106cbdd9b0af425b637ebcb03a46eae401d2b`。
- 本地 `main` 从原项目提交 `536a907c605964421563f12f15c5e00d735fc94f` 快进到开发分支 `c21106cbdd9b0af425b637ebcb03a46eae401d2b`，无需冲突处理。整合后两分支独有提交数为 `0 / 0`，没有未合并的本地分支。
- `main` 的跟踪分支由 `upstream/main` 改为 `origin/main`。原纽约项目的 `upstream` 远程分支不属于沭阳开发分支；没有合并或推送它们。
- 操作前 `origin/main` 已包含开发分支的全部提交；此次新增提交仅记录本次验收，不改变运行代码或生成数据。推送目标限定为 `origin` 的 `main`，不用强推。

## 实际验证

- Node.js `v24.15.0`：按 AGENTS.md 的 PowerShell 文件清单运行，排除 `overpass.test.mjs`，**430 / 430 通过**。完整输出见 `node-tests.txt`。
- 项目虚拟环境 Python `3.12.13`：`python -m unittest discover -s tests -p 'test_*.py'`，**2 / 2 通过**。完整输出见 `python-tests.txt`。
- 首轮 Node 运行出现两处失败：`core.autocrlf=true` 在切换分支时把 `js/tsl-materials.js` 检出为 CRLF，而两处源码提取测试使用 LF 字符串定位。确认该文件规范化后与 Git blob 相同，再将工作文件恢复为 HEAD 原始字节；相关 7 项通过，随后上述全量 430 项通过。没有修改测试断言或材质逻辑。
- 7 项 Overpass 测试未运行，不计入通过数；本轮采用 Windows 基线，未配置该测试所需的 POSIX 执行环境。
- 本轮没有新增视觉、几何、来源或交互变更，没有重跑生成器或浏览器验收。运行文件与既有 `c21106c` 验收快照一致；既有渲染证据见相邻的 `three-fixes-2026-11-15/` 和 `spatial-render-rescan-2026-11-15/`。
- 没有同步另一个 `evans-github-pages` 仓库或执行 Pages 部署。上述回归不扩大此前实景还原的范围与精度结论。
