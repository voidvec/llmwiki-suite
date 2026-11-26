---
title: 知识库导航（知识层）
description: 知识层工程知识文档的导航、边界声明、编号规则与阅读路径
tags: ["知识库", "导航", "索引", "规范"]
difficulty: beginner
categories: ["参考手册"]
kb_id: KB-00
kind: knowledge-base-index
status: derived
scope: 2026-11-12 方案 C 收敛并完成连续重编号后的 8 篇工程知识文档清单、边界声明、编号规则与阅读路径
audience: 项目维护者、接手者
last_verified: 2026-11-12
reconciled_against: 口径基准 v1 · 2026-11-11（2026-11-12 结构性收敛与重编号）
confidence: high
---

# 知识库导航（知识层）

> **定位**：本目录只放**改代码才会变**的工程知识——架构、流程、术语、配置、算法、门禁、通道、规则。不放现状快照、待办台账、文档索引与治理基准。是派生文档，不是用户手册，不替代 `docs/` 与根目录 `README.md`。

## 1. 边界与三层分工（2026-11-12 方案 C）

| 层 | 内容 | 位置 |
|---|---|---|
| **知识层**（本目录） | 8 篇稳定工程知识 | `knowledge-base/` |
| **治理 / 状态 / 台账 / 索引** | 口径基准、产品定位与观点、打包运维资料、现状时间线、偏差台账、原有文档索引 | `docs/project-records/` |
| **用户手册 / 教程 / 规范 / 计划** | 原有 39 份文档 | `docs/`、根目录、`deliverables/product-strategy/`、`.github/` |

判定原则：跨时点稳定、可复用、可传承 → 知识层；随日期或决策变化、会被修完 → 项目记录；只做导航或复述原文 → 索引；裁定口径本身 → 治理。

**编号规则（2026-11-12 修订）**：本目录 8 篇主题文档编号 `KB-01` ~ `KB-08` **连续**，且与文件名数字前缀一致；`KB-00` 是本导航。项目记录层使用独立的 `PR-00` ~ `PR-05` 前缀，不与知识层共用编号空间，避免同一编号指两份文档。重编号前的 2026-11-11 原始编号保留在每篇 frontmatter 的 `legacy_kb_id`，新旧对照表见 `docs/project-records/README.md §2`。全仓引用已于同日一次性同步，历史核对记录按该表换算即可解析。

## 2. 文档清单（8 篇）

| 编号 | 文件 | 覆盖范围 | 主要依据 |
|---|---|---|---|
| KB-01 | `01-architecture-and-dependencies.md` | 六层模块依赖图、共享内核、循环依赖规避、索引与报告产物 schema | `src/llmwiki/*.py` / `kb_core.py` / `gen_index.py` / `tests/fixtures/kb/kb-index.json` |
| KB-02 | `02-core-workflow-and-dataflow.md` | 从笔记到问答的端到端流程、索引刷新三条路径、产物生命周期与入库边界 | `cli.py` / `ingest.py` / `gen_index.py` / `recall.py` / `assistant.py` / `.gitignore` |
| KB-03 | `03-glossary.md` | 关键概念统一口径（compile / recall / lint / health / eval / channel / L0-L3 / D1-D12 / DoD 等）及多义冲突 | 全部文档 + `defaults.py` / `config.py` / `health.py` |
| KB-04 | `04-configuration-and-entrypoints.md` | 三层配置模型、repo 解析链、环境变量兼容层、运行入口矩阵与退出码总表 | `config.py` / `_env.py` / `defaults.py` / `cli.py` / 6 个 `scripts/` |
| KB-05 | `05-recall-algorithm.md` | BM25 公式、字段权重、中文 2-gram、别名扩展、覆盖度 ramp、via_link 补位、缓存与新鲜度、调参坐标 | `recall.py` / `defaults.py` / `tutorial-03` / `eval_reports/*.json` |
| KB-06 | `06-quality-gates.md` | lint 三检、eval 四态退出码、health 计分、召回基线门禁、pytest / pre-commit / CI 矩阵、阈值双口径 | `lint.py` / `eval_recall.py` / `health.py` / `check_recall_baseline.py` / `ci.yml` |
| KB-07 | `07-channels-and-service-security.md` | 通道抽象与两类驱动、4 通道端点与签名、iLink 协议、SSE、BRIDGE_TOKEN、暴露形态与安全边界 | `channels/*` / `wechat_bridge.py` / `SECURITY.md` / `webui-dashboard-design.md` |
| KB-08 | `08-business-rules-and-constraints.md` | 29 条规则按 A 硬不变量 / B 可执行 / C 阶段取舍 / D 流程纪律分级 | `SECURITY.md` / `CONTRIBUTING.md` / `scope-freeze.md` / DoD 契约 / 源码常量 |

## 3. 阅读路径（8 篇版）

| 场景 | 建议顺序 |
|---|---|
| 新接手项目 | KB-01 → KB-02 → KB-04 → KB-08 |
| 要改检索 / 调优 | KB-05 → KB-06 → KB-02 |
| 要改通道 / 服务 | KB-07 → KB-04 → KB-06 |
| 查配置 / 退出码 / 规则 | KB-04 → KB-08 → KB-03 |
| 判断现状或查待办 | 不在本目录，去 `docs/project-records/`（PR-03 / PR-04） |
| 判断「还能不能按原计划推进」 | 去 `docs/project-records/`（PR-03 → PR-01） |

## 4. 统一结构

每篇含：定位声明 → 背景 → 结论速览 → 关键关系 → 主体内容 → 注意事项与常见误读 → 不确定 / 待补充项 → 主要依据 → 相关主题。`frontmatter` 中 `kb_id` 是当前编号、`legacy_kb_id` 是 2026-11-11 原始编号；`status: derived` 表示由项目实际信息推导，冲突按 `口径基准 §0.4` 裁定；`reconciled_against` 表示已按基准统一口径。

## 5. 注意事项

- 本目录是静态沉淀，不随项目自动更新；`last_verified` 之后的代码变更需重新核对。
- 「不确定 / 待补充项」是刻意保留的审计入口，不是遗漏；把未验证信息写成结论比缺一段更危险。
- 文档内路径一律相对仓库根；`testkb/`、`stats/`、`dist/` 含历史产物，引用时注意时效。
- **索引隔离仍是待办**：本目录与 `docs/project-records/` 都未加入 `DEFAULT_EXCLUDE_DIRS`（`src/llmwiki/defaults.py:9-13`），且这些文档的 frontmatter 缺 `lint.py:36` 要求的 `description` / `tags` / `difficulty`。对仓库根跑 `llmwiki index` 会收录、`llmwiki lint` 会报 `fm.required`。方案 C 只收敛**内容范围**，未做技术隔离，见 `docs/project-records/04-known-deviations-and-open-items.md` P4-5。

## 6. 主要依据

`src/llmwiki/` 全部 22 个模块、根目录与 `docs/` 共 39 份原有文档、`pyproject.toml` / 3 个 workflow / 6 个脚本 / 2 组测试夹具 / `stats/` 85 份快照 / `dist/` 产物；取证方法与事实裁定见 `docs/project-records/00-canonical-baseline.md`。
