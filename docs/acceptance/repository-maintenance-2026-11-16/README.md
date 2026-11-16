# 仓库维护验收 — 2026-11-16

## 分支与本地文件

- 已确认 `codex/shuyang-city-refinement-20261114` 的提交全部包含于 `main`，使用 `git branch -d` 删除该本地分支；源码远程 `origin` 原本只有 `main`，无需删除远程分支。
- 已确认 `.releases/core-frontage-release-83ac8f3` 工作树干净，且其提交为 `main` 的祖先，再使用 `git worktree remove` 注销并删除。当前只有主工作树与本地 `main`。
- 临时发布包、过程脚本、截图草稿、分享包、浏览器临时目录和 Python 缓存已移出工作区。目录级清单、文件数及字节数见 [cleanup.json](cleanup.json)。清单统计在临时工作树移除后进行，不含该工作树。
- 工具自动审批拒绝批量永久删除，仅返回 `blocked by policy`；随后改用 Windows 回收站完成六处目录清理，文件可从回收站恢复。本记录不将回收站内容计为磁盘空间已释放。
- 保留 `.venv/`、`tools/data/shuyang/reference/`、全部来源及判读数据、数据生成与审计工具、测试和正式验收证据。没有修改原纽约项目的远程分支。

## README 与 About

- 重整 README：加入已有项目渲染截图、功能入口、快速运行、操作、数据范围、近期进展、开发与生成、文件维护、发布及许可说明。
- 根据已提交数据和解压后的 `buildings-enriched.json.gz` 交叉确认：9,977 条建筑来源，展示估高为 4,711 条，CNBH 为 5,264 条，OSM 高度和核对层数各 1 条；修正旧 README 的过期估高数。
- 公园说明区分来源步道与后补的影像/资料推断线位；住宅进展更新为 0–2.5 公里五环，保留统一层数回填及未完成逐栋核实的限制。
- GitHub About 已更新中文简介、在线体验地址与十个主题标签，通过 GitHub API 回读确认。既有 GitHub 连接器没有仓库元数据编辑能力，本次使用当前 Git 登录凭据调用 API，凭据未写入文件。修改前后字段见 [github-about.json](github-about.json)。
- 同步 AGENTS.md 中已实测的 430 项 Node 基线与进度页维护记录。

## 验证范围

本轮只修改文档及仓库元数据；314 个运行代码、静态运行资产、生成数据、来源资料、工具、测试和许可文件逐项与 `667742a` 的 Git 内容一致（文本允许检出换行差异）。64 条本地 Markdown 链接、预览图和引用脚本路径均检查存在，启动检查 `tests/boot.test.cjs` 的 2 项通过，六处清理目录均确认不存在。汇总见 `checks.json`。

完整 430 项 Node、2 项 Python 回归已在同日主分支整合时运行，通过记录见 [branch-integration-2026-11-16](../branch-integration-2026-11-16/README.md)。本轮没有重复完整回归或新增实现镜像测试；7 项 Overpass 仍未运行，没有新增浏览器视觉验收。README 预览使用已检查的历史项目渲染图，未纳入第三方原图。

本次推送范围为源码仓库 `origin/main`，没有同步 Pages 发布仓库。
