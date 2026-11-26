---
title: 项目记录导航（治理 / 状态 / 台账 / 索引）
description: 治理、状态、台账、索引层导航，含新旧编号映射与三层分工
tags: ["项目记录", "导航", "编号映射"]
difficulty: beginner
categories: ["参考手册"]
kind: project-records-index
status: derived
scope: 2026-11-12 方案 C：5 篇非知识层文档从 knowledge-base/ 迁出、1 份权威基准独立成篇；同日完成 PR-00~05 重编号，含新旧编号映射、三层分工、时效约定
audience: 主理人、审计者、查现状或查待办的人
created: 2026-11-12
last_verified: 2026-11-12
---

# 项目记录

> **定位**：从 `knowledge-base/` 迁出的 5 篇非知识层文档，加上从原导航 §0 独立出来的 1 份权威基准，共同构成治理 / 状态 / 台账 / 索引层。**不是知识库**，不放「改代码才会变」的工程知识。本目录使用独立 `PR-xx` 编号，与知识层 `KB-xx` 分离；2026-11-11 的原始 KB 编号见 §2 与各篇 `legacy_kb_id`。

## 1. 三层分工

| 层 | 内容 | 位置 | 变更频率 |
|---|---|---|---|
| 知识层 | 架构、流程、术语、配置、算法、门禁、通道、规则（8 篇） | `knowledge-base/` | 改代码才变 |
| **项目记录**（本目录） | 口径基准、定位观点、打包运维、现状时间线、偏差台账、文档索引 | `docs/project-records/` | 随日期 / 决策 / 修 bug 变化 |
| 手册与计划 | 用户手册、教程、规范、发布运营计划（39 份） | `docs/`、根目录、`deliverables/`、`.github/` | 按各自生命周期 |

文件数口径：知识层 **8 篇主题文档 + 1 份导航 = 9 个文件**；项目记录 **6 篇主题文档（1 份权威基准 + 5 篇迁出记录）+ 1 份导航 = 7 个文件**。全仓引用中的「8 篇」「6 篇」一律指主题文档，不含导航。

## 2. 新旧编号映射（全仓引用解析表）

2026-11-12 按用户纠正完成重编号：知识层收敛为 `KB-01` ~ `KB-08` 连续，项目记录改用 `PR-00` ~ `PR-05`。**两套编号空间互不重叠**，全仓引用已一次性同步；历史核对记录中的旧编号按此表换算（例：`KB-12 P2-5` → `PR-04 P2-5`）。

### 2.1 项目记录层（本目录，`PR-xx`）

| 新编号 | 旧编号（2026-11-11） | 文件 | 性质 |
|---|---|---|---|
| PR-00 | 原导航 `KB-00 §0` | `00-canonical-baseline.md` | 治理：全仓唯一权威事实源，v1 |
| PR-01 | KB-01 | `01-product-positioning.md` | 产品定位 / 市场判断（观点，与 README「Why」有重叠） |
| PR-02 | KB-09 | `02-packaging-and-operations.md` | 打包发布链 + 观测数据（含时点数据，与 `pypi-release-guide.md` / `RELEASE.md` 重叠） |
| PR-03 | KB-11 | `03-evolution-and-current-state.md` | 版本 / 计划 / 现状时间线，随时点过期 |
| PR-04 | KB-12 | `04-known-deviations-and-open-items.md` | P0–P4 偏差与待办，会被修完 |
| PR-05 | KB-13 | `05-existing-docs-index.md` | 原有 39 份文档的可信度分级与查阅路径 |

### 2.2 知识层（`knowledge-base/`，`KB-xx`）

| 新编号 | 旧编号（2026-11-11） | 文件 |
|---|---|---|
| KB-00（未变） | KB-00 | `README.md`（导航，不是主题文档） |
| KB-01 | KB-02 | `01-architecture-and-dependencies.md` |
| KB-02 | KB-03 | `02-core-workflow-and-dataflow.md` |
| KB-03 | KB-04 | `03-glossary.md` |
| KB-04 | KB-05 | `04-configuration-and-entrypoints.md` |
| KB-05 | KB-06 | `05-recall-algorithm.md` |
| KB-06 | KB-07 | `06-quality-gates.md` |
| KB-07 | KB-08 | `07-channels-and-service-security.md` |
| KB-08 | KB-10 | `08-business-rules-and-constraints.md` |

每篇 frontmatter 的 `legacy_kb_id` 记录其旧编号，便于脚本或人工换算。

## 3. 阅读约定

- 本目录共 7 个文件：1 份导航（本文件）、1 份权威基准（`00-canonical-baseline.md`）、5 篇迁出的项目记录。其中 **5 篇迁出文档记录的是 2026-11-11 时点**的静态核对结果；2026-11-12 方案 C 只调整归属、编号与引用，**正文论证与历史数据一律不改写**。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 映射表与口径基准 §0.1 为准；基准维护的是当前权威事实。
- 需要更新现状时**追加状态块，不涂改历史记录**；权威时间线只在 `00-canonical-baseline.md §0.2` 维护一处。
- `04-...` 是台账，不是 bug 跟踪系统；可执行的待办应转 GitHub Issues / TODO，本目录只留核对痕迹。
- `05-...` 的分级（`[现行]` / `[部分过时]` / `[历史]`）继续有效；计划 / 历史类文档顶部还有 2026-11-11 加的状态标注头，以标注头为第一判据。

## 4. 按场景的入口

| 场景 | 入口 |
|---|---|
| 核对该写什么口径 | `00-canonical-baseline.md §0.3` |
| 判断项目现在到哪一步 | `03-evolution-and-current-state.md` → `00-canonical-baseline.md §0.2` |
| 查已知缺陷 / 待办 | `04-known-deviations-and-open-items.md` |
| 回到某份原始文档 | `05-existing-docs-index.md` |
| 发版 / 运维 / 观测数据 | `02-packaging-and-operations.md` |
| 产品定位与 Non-Goals | `01-product-positioning.md`（与根目录 README「Why」对照读） |
| 系统怎么运转 | **不在本目录**，去 `knowledge-base/README.md` |

## 5. 已知待办（未随方案 C 处理）

- **索引隔离**：`knowledge-base/` 与 `docs/project-records/` 均未加入 `DEFAULT_EXCLUDE_DIRS`（`src/llmwiki/defaults.py:9-13`），且这些文档 frontmatter 缺 `lint.py:36` 要求的 `description` / `tags` / `difficulty`。对仓库根跑 `llmwiki index` 会收录、`llmwiki lint` 会报 `fm.required`。方案 C 只收敛内容范围，技术隔离仍需单独决策（原台账 P4-5）。
- **待补主题**（知识层缺口）：扩展开发指南、故障排查 playbook、数据契约全集、设计决策 ADR、兼容性矩阵、知识库维护元规范。
