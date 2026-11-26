---
title: 关键概念与术语词典
description: 项目高频术语的统一定义、多义冲突与来源口径
tags: ["术语", "词典", "口径"]
difficulty: beginner
categories: ["参考手册"]
kb_id: KB-03
legacy_kb_id: KB-04
kind: knowledge-base
status: derived
scope: 统一项目内高频术语的定义、来源口径与已知问题/待办，避免跨文档误解
audience: 全体参与者；尤其适合接手者做「名词对齐」
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 关键概念与术语词典

> **定位**：不重复教程的讲解，只做**口径对齐**：一个词在项目里到底指什么、哪份文档是来源、哪些地方用法互相打架。遇到冲突时以「代码口径」为准并标注。

## 1. 背景

项目同时存在三套语言：工程实现（Python 常量 / 命令）、用户文档（中文教程 + 英文 README）、产品运营（Q4 九周计划、DoD、Wave、里程碑）。同一词在不同层含义不同，例如 `recall` 既是子命令结果、又是评估指标、又是模块名；`D9` 在两份计划里指完全不同的交付物。这篇把这些歧义集中标注。

## 2. 结论速览

- 核心工程术语以 `src/llmwiki/` 的常量与函数为准；评估指标以 `eval_recall.summarize()` 的字段名为准。
- **产品运营术语（D1–D12、Wave、M0–M6、CR）存在多套编号体系**，引用时必须带文件名，否则无法判断指哪一套。
- 两个最容易被误用的口径：`contextual_recall`（不是 `recall`）、`top_k=4`（不是 `defaults.py` 里的 6）。

## 3. 关键关系：概念分层

```
方法论层   compile（编译范式） / L0-L3（自进化等级） / 内容所有权
   ↓
数据层     frontmatter / wikilink / 受控词表 / 别名组 / kb-index.json
   ↓
流程层     ingest / index / query / lint / eval / health / categories-sync / serve
   ↓
算法层     BM25 / 2-gram / 覆盖度 ramp / via_link / 新鲜度 / build_context
   ↓
质量层     contextual_recall / MRR / baseline / DoD / 门禁阈值
   ↓
交付层     channel / Webhook / 轮询 / BRIDGE_TOKEN / SSE / WebUI / Dashboard
   ↓
运营层     D1-D12 / Wave / M0-M6 / C0-C2 CR / 周二 PT / pivot
```

## 4. 主体内容：术语表

### 4.1 工程核心

| 术语 | 统一口径 | 来源 / 冲突提示 |
|---|---|---|
| **compile（编译）** | 导入期一次性把笔记转成规范文档 + 索引 + 可巡检产物；与查询期切片 RAG 相对 | `README.en.md`；是**工作流选择**不是技术方案的唯一解 |
| **frontmatter（FM）** | 笔记开头 `---` 包裹的扁平 YAML 式元数据；必填 `title/description/tags/difficulty` | `kb_core.parse_fm` 只支持标量 / inline list / block list，**不支持嵌套映射** |
| **受控词表（vocab）** | `categories` 允许值集合；来源优先级 `llmwiki.toml` 显式 > 索引 `category_index` 派生 > 默认 7 类 | `config.load_vocab`；**0.1.3 起 `[categories].allowed` 是增量追加**，不是整体替换 |
| **别名组（alias groups）** | 同义词数组，检索时双向扩展；默认 5 组（k8s / e2e / 架构 / 可观测性 / 反向代理） | `defaults.DEFAULT_ALIAS_GROUPS`；TOML `[aliases].groups` 为**追加** |
| **kb-index.json** | 运行时单一事实源，schema `1.1`，20 字段/文档 + 分类/标签倒排 | `gen_index.py`；架构文档原写「16 字段」，2026-11-11 已修正为 20 |
| **generated-index** | `kind` 取值，专指 `category-index.md`；被 eval 采样与新鲜度检查豁免 | `gen_index.py` / `recall.py` |
| **ingest** | 归一写入：补 FM、重命名、重复报告、目录建议、`--apply` 时重建索引 | 默认 dry-run；**不删重、不改用户正文、不移动目录（除非 --move）** |
| **recall** | ① `recall.py` 模块；② `KbRetriever.recall()` 返回的 Top-K 命中；③ `/api/recall` 端点；④ 评估指标（口语） | 写文档时应写明具体所指；指标正式名是 `contextual_recall` |
| **via_link** | wikilink 图的补位命中，**只补位不顶替**；得分不超过最弱直接命中的 0.5 倍 | `recall.py:514-540`；需过 `link_gate` 门槛 |
| **freshness（新鲜度）** | 索引与磁盘文件 mtime/size/hash 三向比对，只告警不阻断 | `FreshnessReport(stale, unknown, changed, added, deleted)` |
| **build_context** | 把命中转成 LLM 上下文，`max_chapters=4`、每段截 1200 字 | `assistant.py`；`eval_recall.py` docstring 写 6 章是错的 |
| **channel** | IM/网页接入适配器；抽象基类 `ChannelAdapter`，分 Webhook 驱动与轮询驱动 | 注意基类无 `@abstractmethod` |
| **BRIDGE_TOKEN** | 保护 `/api/chat` `/api/recall` 及两个兼容别名的查询参数/请求头令牌 | 不保护 `/healthz` `/dashboard*` `/ilink/*` `/webui/*` 与各 callback |

### 4.2 质量与评估

| 术语 | 统一口径 | 来源 / 冲突提示 |
|---|---|---|
| **contextual_recall** | 评估快照 `summary` 中「任一 expected 出现在 Top-K 即命中」的比例 | **不是 `recall`**；`tutorial-03` 对比脚本原写 `['recall']`，2026-11-11 已修正为 `['contextual_recall']` |
| **MRR** | 平均倒数排名；公开基线 1.0 | `eval_recall.summarize` |
| **contextual_recall_prod** | 按 `prod_top_k=4` 截断后的生产口径召回 | 与 `contextual_recall` 并列输出 |
| **queries_source** | 评估集来源枚举 `repo / explicit / seed / demo-builtin` | 0.1.4 取代 `queries_is_builtin`；旧快照两字段并存 |
| **baseline（基线）** | 两层含义：① 公开评测基线 8 条 query / recall@4=1.0 / MRR=1.0；② CI 门禁阈值 recall≥0.95 / MRR≥0.90 | **策略合同另记 0.85/0.80，属历史计划口径**；执行口径以代码 / CI 的 0.95/0.90 为准（KB-06 §4.6、口径基准 §0.3） |
| **health（健康分）** | 0–100「经验版 Beta」参考值，meta 40% + link 40% + fresh 20%，字母档 A≥90/B≥75/C≥60/D<60/F 空库 | **不阻断**，阻断用 lint；`llmwiki.health.v1` |
| **lint** | 三检：链接判死、FM 必填四项、受控词表；`errors==0 → exit 0` | `--staged` 走 pre-commit；`.kb-lint-ignore.json` 隔离历史断链 |
| **DoD** | 每个交付物 D1–D12 的「完成定义 = 全部打勾」，角色分工 写 W / 审 R / 验 A | `implementation-plan-dod-*.md` §2；LLM 产物必须人审 |

### 4.3 路线与运营

| 术语 | 统一口径 | 冲突提示 |
|---|---|---|
| **L0 / L1 / L2 / L3** | 固化（已完成）→ 增量记忆与回放 → 主动学习与建议 → 自主进化 | `llmwiki-evolution-roadmap.md`；L1 新文件 `kb-memory.json` / `kb-suggestions.md` / `kb-evolution-log.md`，新命令 `observe/nightly/suggest/evolve` |
| **D1–D12** | Q4 九周（W1–W9）交付物编号 | **D9/D10/D11 在 scope-freeze 与 DoD 计划里定义完全不同**（PR-04） |
| **Wave** | 策略文档的三波节奏 | TL;DR 是 Wave 1/2/3（1-6 / 7-12 / 13-24 周），§5 表格却是 Wave 0/1/2 |
| **M0–M6** | 里程碑 | 两套编号：`RELEASE.md` 说「S2 里程碑 M6 后半」，DoD 计划是 M0 范围冻结 … M6 收口/pivot |
| **C0 / C1 / C2 CR** | 变更控制：文案样式 / 增删交付物或影响 1 指标 / 改时间线或 ≥2 指标 | C1 ≤1 天答复、C2 ≥2 天 + 书面 CR 落盘 `docs/cr/`（该目录仓库内无记录，PR-04 P3-1） |
| **周二 PT** | 固定复盘与发布锚点，HN 窗口校准为周二 06:00-09:00 PT | 周复盘模板同时出现「周日 / 周二 / 周四 / 周五」四种说法 |
| **pivot / 止损线** | W9 决策点：star<20 且无外部 PR 且重试 2 次无效果 → 转向 | `scope-freeze.md` §3；按 `stats/` 数据触发条件成立，但 pivot / 止损决策仓库内无记录（PR-03 / PR-04 P3-5） |

## 5. 注意事项与常见误读

1. **`recall` 与 `contextual_recall` 不可混用**：前者是动作/模块，后者是报告字段。引用评估 JSON 时按 `summary.contextual_recall`。
2. **`--demo` 的分数与你的知识库无关**：内置 8 条 query 的 expected 指向套件自带 demo 库，只用于套件自测；文档明确「不提供假分数」，所以 0.1.4 起取消内置集自动回退。
3. **`eval --seed` 生成的评估集是采样结果**（默认 ≤20 条，query 形如「<title> 是什么」），不是人工编写的高质量评估集；公开基线用的仍是内置 8 条。
4. **「零依赖」**指核心链路；`serve` extras 有 4 个第三方包。
5. **「健康分」不是质量标准**：官方定性「健康度参考值，非质量标准」，不要用它替代 lint 做门禁。
6. **`[serve]` 与 `[wechat]`** 内容完全相同，后者是 0.1.5 更名后保留的兼容别名；新文档一律用 `[serve]`。

## 6. 不确定 / 待补充项

- 没有一份权威的术语表文档；本词典是**推导产物**，若后续官方发布 glossary 应以其为准并回写。
- 「8 天 7 版」「Wave 编号」「M 编号」「D9-D11 定义」均无唯一口径，引用时务必带来源文件名。
- `Persona` 编号 `P1 / P2 / P03` 中的 `P03` 疑为笔误，未见说明。
- `queries_is_builtin` 在部分旧快照中存在，是否应彻底移除未定（代码保留为兼容字段）。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/defaults.py` / `config.py` / `kb_core.py` | 常量、词表语义、归一规则 |
| `src/llmwiki/eval_recall.py` | `summarize` 字段、`queries_source` 枚举、`_seed_queries_from_index` |
| `src/llmwiki/health.py` | `WEIGHTS` / `FRESH_WINDOW_DAYS` / `grade` |
| `docs/llmwiki-eval.md` / `docs/llmwiki-health.md` | 指标与退出码正式口径 |
| `docs/llmwiki-evolution-roadmap.md` / `docs/scope-freeze.md` | L0-L3、D1-D12、Non-Goals、止损线 |
| `deliverables/product-strategy/implementation-plan-dod-llmwiki-2026-08-31.md` | DoD、C0/C1/C2、M0-M6、W9 指标 |
| `testkb/eval_reports/*.json`、`.pre-commit-eval/*.json` | 真实字段名与新旧 meta 并存 |

## 8. 相关主题

- KB-05 检索与召回算法口径
- KB-06 质量保障体系与门禁
- KB-08 业务规则与约束清单
- PR-04 已知偏差与待补充台账
