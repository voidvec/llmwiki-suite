---
title: 全仓权威口径基准 v1
description: 全仓唯一权威口径：现状事实、进展时间线、措辞规范与裁定顺序
tags: ["口径", "治理", "事实源"]
difficulty: intermediate
categories: ["知识库规范"]
record_id: PR-00
kind: governance-baseline
status: authoritative
version: v1
scope: 全仓唯一事实源：现状事实、最新进展时间线、统一措辞规范、裁定顺序；文档与基准冲突以本节为准，本节与实现冲突以 src/llmwiki/ 代码为准
audience: 全体文档维护者、审计者、接手者
created: 2026-11-11
last_verified: 2026-11-26
---

# 全仓权威口径基准 v1

> **定位**：本文是全仓唯一权威口径基准，全仓引用时简称「**口径基准**」。原为 `knowledge-base/README.md §0`，2026-11-12 按方案 C 迁出独立成篇；**§0.x 小节编号保持不变**，全仓原有的 `KB-00 §0.x` 引用已于同日统一替换为「口径基准 §0.x」。本文件属治理层，不是知识库文档。同日完成的文档编号重排见 §0.3 与 `docs/project-records/README.md §2`。

## 0.1 现状事实（唯一口径）

| 项 | 权威值 | 取证位置 |
|---|---|---|
| 当前版本 | `0.1.8`，发布日 2026-11-26 | `pyproject.toml:7`、`src/llmwiki/__init__.py:3`、`CHANGELOG.md` `[0.1.8] - 2026-11-26`、PyPI 元数据、GitHub Release `v0.1.8` |
| 待发布段 | `[Unreleased]` 为空；`v0.1.7` 与 `v0.1.8` 同日发布：tag + PyPI wheel/sdist + GitHub Release（0.1.7 于 10:57 CST、0.1.8 于 11:48 CST，`pypi.org/pypi/llmwiki-suite/json` 可查） | `CHANGELOG.md`、`git tag`、`gh release list`、`pypi.org/pypi/llmwiki-suite/json` |
| 工程侧最后功能变更 | 0.1.8（2026-11-26）：Markdown 链接对「索引外文件」不再判死（大小写严格 + 拒绝 `..` 逃逸的存在性兜底）、`is_vendored` 认 `README.<lang>.md` 等本地化变体 | `git log`、`src/llmwiki/kb_core.py` |
| CLI 子命令 | **9** 个：`init / ingest / index / query / lint / categories-sync / eval / health / serve` | `src/llmwiki/cli.py` 的 `build_parser()` |
| 观测快照 | `stats/` 85 份，覆盖 2026-09-01 ~ 2026-11-25（缺 09-02），`obs(daily)` 仍在继续 | `stats/`、`git log` 的 `obs(daily)` 提交 |
| 周报 | 仅 `docs/weekly/2026-W36.md` 一份 | `docs/weekly/` |
| 版本 tag | `v0.1.8 → c2cf4a1`（`release: 0.1.8`）、`v0.1.7 → 0f4210a`；tag 之后的提交只改文档，不影响版本 | `git tag --format='%(refname:short) %(objectname:short)'`、`git rev-parse v0.1.8^{commit}` |
| 版本号落点 | 四处必须一致：`pyproject.toml`（**唯一真源**）、`src/llmwiki/__init__.py`（`llmwiki --version` 读它）、`CHANGELOG.md` 段、tag + PyPI + GitHub Release。本机另有两处**生成物**：`src/*.egg-info`（`python -m build` 产）与 `.venv` 的 editable dist-info（`pip install -e .` 产），不手改 | 2026-11-26 已全部对齐 `0.1.8`；`stats/` 快照的 `version` 是历史抓取值（止于 11-25 的 `v0.1.6`），不属对齐范围 |
| 版本号自动化与门禁 | 升版本走 `python scripts/version.py --set X.Y.Z`（真源 + `__init__` + getting-started 两处锚点，锚定替换不碰历史段）；`--check` 校验 6 个落点并禁止版本硬编码回潮；`--check-tag` 校验 tag 与真源一致。门禁三处：`ci.yml` 的 `version` job、`release.yml` 首步、KB 仓 `kb-ci.yml` 的 `suite-ref` job | `scripts/version.py`、`.github/workflows/ci.yml`、`release.yml`；KB `scripts/check_suite_ref.py` |
| 未发布过的版本段 | **`0.1.3` 只有 CHANGELOG 正文与代码变更，无 tag、无 PyPI 记录**（PyPI 发布序列为 0.1.0 / 0.1.1 / 0.1.2 / 0.1.4 / 0.1.5 / 0.1.6 / 0.1.7 / 0.1.8）；与之相对 `0.1.2` 有 tag 与 PyPI 记录但 CHANGELOG 无正文 | `git tag --list`、`pypi.org/pypi/llmwiki-suite/json` 的 `releases` 键 |
| 09-05 ~ 11-25 提交 | 除 2026-11-26 的功能 / 发布提交外，全部为 `obs(daily): 曝光快照` | `git log` |
| 文档结构 | 2026-11-11 建立 14 个文件（1 导航 + 13 篇主题文档）并完成全仓口径统一；**2026-11-12 按方案 C 重排为知识层 8 篇 + 1 导航（`knowledge-base/`，9 个文件）与项目记录 6 篇 + 1 导航（`docs/project-records/`，7 个文件，含 1 份权威基准）；同日完成连续重编号** | `knowledge-base/README.md`、`docs/project-records/README.md` |

## 0.2 最新进展时间线（唯一权威版本）

| 日期 | 仓库内证据 | 说明 |
|---|---|---|
| 2026-08-31 | 0.1.6 发布；Q4 九周计划三份交付物 | 此后工程侧长期停滞，直到 2026-11-26 的 0.1.7 / 0.1.8 |
| 2026-09-01 | `docs/weekly/2026-W36.md`（唯一周报）；`stats/` 首份快照 | 计划 W1 |
| 2026-09-02 | `docs/hn-account-growth.md` 养号计划 K=1 重排（正文 AuthorDate） | 不是提交日 |
| 2026-09-05 ~ 11-25 | 逐日 `obs(daily): 曝光快照` 提交 + `stats/` 85 份快照 | 唯一的持续仓库活动 |
| 2026-11-07 | 回填提交 `c57c718`（CommitDate 12:00），仅改 `docs/hn-account-growth.md` | 当时为 HEAD；不是养号执行记录 |
| 2026-11-25 | 最新一条 `obs(daily)`（`af29328`）与 `llmwiki-obs-2026-11-25.json` | 观测仍在继续（11-07 ~ 11-25 由远端补齐） |
| 2026-11-11 | 新建 `knowledge-base/` 14 篇；全仓口径统一 | 口径基准 v1 建立 |
| 2026-11-12 | 方案 C 落地：`knowledge-base/` 收敛为 8 篇知识文档 + 1 份导航；5 篇治理 / 状态 / 台账 / 索引迁至 `docs/project-records/`，权威基准从原导航 §0 独立成篇（该目录共 6 篇 + 1 导航） | 仅文档结构调整，无代码变更 |
| 2026-11-12 | 按用户纠正完成重编号：知识层 `KB-01` ~ `KB-08` 连续且与文件名一致，项目记录改用独立 `PR-00` ~ `PR-05`；全仓引用一次性同步，旧号存于 `legacy_kb_id` | 修正上一轮的跳号与同号歧义；v1 口径不变，仅补记结构变更 |
| 2026-11-26 | 6 个功能 / 修复提交 + `release: 0.1.7`；推 tag 触发 `release.yml`，PyPI 与 GitHub Release 同日发布（`0f4210a`） | 工程侧停滞 87 天后恢复 |
| 2026-11-26（下午） | 套件仓自身 lint 归零（25 → 0：`is_vendored` 认本地化变体、`deliverables/` 退出索引、13 份文档补 frontmatter）、`ci.yml` 增 lint 自检 job、文档收录范围收紧到 `docs/`；随后 `release: 0.1.8` 发 **0.1.8**（链接存在性兜底 + vendored 变体） | 与 0.1.7 同日第二版；health 60 → 87 |
| 2026-11-26（晚间） | 版本号治理：新增 `scripts/version.py`（`--check` / `--set` / `--next` / `--check-tag`），文档版本硬编码从 17 处收缩到 2 处（getting-started 的复制粘贴场景），三处门禁落地（`ci.yml` version job、`release.yml` 首步、KB `kb-ci.yml` 的 `suite-ref`） | 起因是 11 篇计划 / 历史文档的状态头「推进到 0.1.8」本身又成了漂移面 |

> 计划中的 W4（09-22）发布 `v0.1.7` + HN 主帖、W37–W44 周报、`docs/cr/`、发布响应台账、W9 pivot/止损决策、范围冻结签署：其中 `v0.1.7` 已于 2026-11-26 落地（延期 65 天，含 PyPI 与 GitHub Release），**其余各项仓库内仍无记录**；不排除在仓库外发生，不作绝对断言。时间线展开对照见 `docs/project-records/03-evolution-and-current-state.md §4.5`。

## 0.3 统一措辞规范

| 主题 | 必须这样写 | 禁止 / 说明 |
|---|---|---|
| 计划产物 | 「仓库内无记录」（HN 发布 09-22、W37–W44 周报、`docs/cr/`、发布响应台账、pivot/止损决策、范围冻结签署、L1+ 命令） | 「确定未执行」「已放弃」「不存在」；仓库内无记录 ≠ 未执行。`v0.1.7` / `v0.1.8` 已于 2026-11-26 发布，不再属于此类 |
| 索引刷新 | `ingest --apply` 自动重建；`llmwiki index` 手动重建；`query` / `recall` 不自动重建、只做新鲜度告警 | 笼统的「索引不自动刷新」 |
| 配置节名 | `[serve]`；`[wechat]` 仅为 0.1.5 前的兼容别名 | 新文档用 `[wechat]` |
| 评估指标字段 | `summary.contextual_recall` 与 `summary.mrr`（两者并存，后者是真实字段） | `summary['recall']` |
| 词表语义 | `[categories].allowed` 增量追加，`replace_default = true` 才整体替换 | 「整体替换默认」 |
| 门禁阈值 | 执行口径 0.95 / 0.90（代码 / CI / pre-commit）；0.85 / 0.80 仅作历史计划口径并显式标注 | 两套混用不标注 |
| 命令数 | 9 个子命令（含 `health`） | 「CLI 8 命令」 |
| 时间锚点 | 「截至 2026-11-26」（0.1.8 发布后）；历史结论保留其原锚点「截至 2026-11-11 / 11-12」并标注 | 无锚点的「当前 / 最新」 |
| 文档结构 | 知识层 8 篇（`KB-01` ~ `KB-08` 连续）+ 项目记录 6 篇（`PR-00` ~ `PR-05`）；两套编号空间分离，旧号仅作 `legacy_kb_id` 与映射表 | 「14 篇知识库文档」「知识库共 13 篇」「编号沿用原始序号」等旧口径 |
| 问题记录 | 归为「已知问题 / 待办」，见 `docs/project-records/04-known-deviations-and-open-items.md`；未经实跑一律标「待验证 / 推测」 | 粉饰或删除 |

## 0.4 裁定顺序与状态标注

`src/llmwiki/` 代码实现 > 本基准 > 用户手册 / 教程 / 规范 > 历史周报与设计快照 > 2026-08-31 ~ 09-02 的发布运营计划（历史）。

2026-11-11 对项目内计划 / 历史类文档加了统一状态标注头：`[未兑现]`（计划动作仓库内无落地记录）、`[已过期]`（某一时点快照）；`05-existing-docs-index.md` 原有的 `[现行]` / `[部分过时]` / `[历史]` 分级继续有效。正文论证一律不改写，按历史快照阅读。全仓定点事实修正清单见 `04-known-deviations-and-open-items.md §1 修订记录`。

2026-11-12 方案 C 只做**文档归属调整**：不改写任何历史核对记录、不改动 CHANGELOG 与代码实现。同日按用户纠正补做**编号连续化**（知识层 01–08、项目记录 PR-00–05），全仓引用一次性同步，旧编号保留在 `legacy_kb_id` 与 `docs/project-records/README.md §2` 映射表中，不涂改历史结论。

2026-11-26 **定点修订**（只改已发生变化的硬事实，不重做全仓审计）：版本 `0.1.6 → 0.1.7`（tag / PyPI / GitHub Release 三处均已发布）、观测快照 66 → 85 份（覆盖延至 11-25，`obs(daily)` 未停止）、`v0.1.7` 从「计划产物无记录」清单移出、时间线补 2026-11-25 与 2026-11-26 两行、受影响的 10 篇计划 / 历史文档状态标注头同步重锚。**未重新核验**的部分（外部 star / 下载量走势、PR-04 其余待办、HN 发布与周报）仍保持各自原锚点，不得据本次修订推断为最新。

同日下午**第二轮修订**：`0.1.7 → 0.1.8`（同日第二版，tag / PyPI / GitHub Release 均已发布），修的是两个「给用户报假错」的问题——索引外文件的 md 链接被判死、双语仓库的 `README.<lang>.md` 被判成缺 frontmatter。同时口径补两处：本仓库收录范围收敛到 `docs/`（`deliverables/` 退出索引）、`ci.yml` 增 lint 自检 job。**10 篇计划 / 历史文档的状态标注头改为「版本口径以基准 §0.1 为准」**，不再写死「当前版本为 X」——今天一天内 0.1.6→0.1.7→0.1.8 连跳三轮，写死版本号的头每发一版就全成假话。（当晚进一步改成**完全不带版本号**：连「推进到 0.1.8」也是新的漂移面，见 §0.1「版本号落点」。）

## 0.5 「口径统一」与偏差台账的关系

「口径统一」指**同一事实在全仓说法一致**，不等于「项目不存在问题」。`04-known-deviations-and-open-items.md` 如实保留实现层潜在故障、仓库内无记录的产物、历史计划之间的口径差异，统一归类为「已知问题 / 待办」。计划文档之间的历史口径差异通过状态标注头解决，不改写历史记录。

`reconciled_against: 仓库口径基准 v1 · 2026-11-11` 表示该篇已按本基准统一口径；各篇不重复抄写时间线，统一引用 §0.1 / §0.2 与 `03-evolution-and-current-state.md §4.5`，避免再次漂移。

## 1. 本基准的来历与取证原则

2026-11-11 按三条线独立盘点后交叉推导：文档资产（根目录 6 份、`docs/` 25 份、`deliverables/product-strategy/` 4 份、`.github/` 模板 4 份）；代码实现（`src/llmwiki/` 14 个核心模块 + `channels/` 8 个模块，逐函数核对常量与退出码）；配置与运行（`pyproject.toml`、`MANIFEST.in`、3 个 workflow、6 个脚本、2 组测试夹具、`testkb/`、`stats/` 66 份快照、`dist/` 产物）。

取证原则：文档口径与代码冲突时以代码为准并显式标注冲突；数值结论尽量落到具体文件、常量或行号线索；无法确证的一律进入「不确定 / 待补充项」，不写成结论。

2026-11-12 方案 C 的判定原则：跨时点稳定、可复用、可传承的内容归知识层；随日期 / 决策变化、会被修完的内容归项目记录；只做导航或复述原文的归索引；裁定口径本身归治理。同日重编号的映射见 `docs/project-records/README.md §2`；基准 v1 的事实口径未因编号调整而改变。
