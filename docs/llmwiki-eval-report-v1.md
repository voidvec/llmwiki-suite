---
title: "llmwiki-suite 公开评测报告 v1（eval baseline 2026-08-31）"
description: "llmwiki-suite 首份公开召回质量评测：8 条示例测试集，recall@4=1.0 / MRR@4=1.0；含测试方法、逐条明细与明确的场景局限声明。"
categories: ['评测报告', '知识库规范']
tags:
  - llmwiki
  - eval
  - recall
  - mrr
  - benchmark
difficulty: "beginner"
estimated_time: "5分钟"
version: "1.0"
created: "2026-09-01"
updated: "2026-09-01"
---

# llmwiki-suite 公开评测报告 v1

> 这份报告是套件对外发布时引用的**召回质量基线**（D7 交付物）。
> 所有数字可复现：一套指令在 `testkb/` 上重跑即可拿到相同结果。
> 关注点：**诚实地报告「测了什么、没测什么」**——没有刻意的基准美化，也不掩盖小样本的局限。

---

## 1. TL;DR

| 指标 | 值 |
|------|-----|
| 测试集 | 8 条 query（套件内置示例集 `demo-builtin`） |
| **recall@4** | **1.0**（8/8 命中） |
| **MRR@4** | **1.0**（8 条全部第 1 位命中） |
| 生产等价 recall（prod_top_k=4） | **1.0** |
| 未命中 query | 0 |
| 检索器 | BM25 + body_text + **wikilink 图**（零 embedding） |

一句话：**在示例知识库 `testkb/` 的 8 条「语义改写型」query 上，全部 Top-1 命中**。
这是会随发布公开的基线——不是「某一次跑得好」，而是仓库内 `check_recall_baseline.py` 每次 CI/pre-commit 都在断言的**防退化门槛**。

---

## 2. 测试方法与测试集来源

- **命令**：`llmwiki eval --repo testkb`（简化为 `--demo` 内置集，见下）。
- **测试集**：套件内置的 `demo-builtin` 示例集（8 条 query，期望指向 `testkb/` 内 4 篇笔记），来源 `src/llmwiki/data/eval_queries.json`。
- **为什么用示例集而非任意库**：`testkb/` 是可复现的「迷你知识库」（含脏笔记、命名不规范、待归一化内容），能检验真实场景，且**任何人克隆仓库重跑都能复现**——这比「你用我知识库得到的结果」更有可证伪性。

### 2.1 一条测试 query 示例

```json
{
  "query": "会议纪要把检索引擎换成了什么",
  "expected": ["notes/weekly-sync.md"],
  "note": "叙述型：从会议纪要找检索引擎选型结论"
}
```

### 2.2 8 条 query 全部明细（2026-08-31 快照）

| # | query | 期望命中（expected） | rank | 命中 |
|---|-------|----------------------|------|------|
| 1 | 会议纪要把检索引擎换成了什么 | notes/weekly-sync.md | 1 | ✅ |
| 2 | BM25 的参数怎么调 | notes/bm25-tuning-log.md | 1 | ✅ |
| 3 | nginx 反向代理在哪里讨论 | notes/messy-note-未归一.md | 1 | ✅ |
| 4 | 知识库分类导航在哪 | category-index.md | 1 | ✅ |
| 5 | 检索引擎选型会议记录 | notes/weekly-sync.md | 1 | ✅ |
| 6 | BM25 的停用词与字段权重 | notes/bm25-tuning-log.md | 1 | ✅ |
| 7 | 服务器配置和反向代理笔记 | notes/messy-note-未归一.md | 1 | ✅ |
| 8 | 索引包含了哪些文档 | category-index.md | 1 | ✅ |

> 8 条 query 中 4 条是**同义改写/口语化**（如「检索引擎选型会议记录」↔「会议纪要…」），4 条是**用词宽松**（如「nginx 反代」→ 命中 messy-note）——刻意覆盖「不那么精确的问法」，而非简单的关键词直配。

---

## 3. 环境与可复现性

| 项 | 值 |
|----|-----|
| 检索器 | `llmwiki.recall.KbRetriever`（BM25 + body_text + wikilink graph） |
| top_k | 4（与生产 `build_context(max_chapters=4)` 一致） |
| min_score | 0.15（阈值，过滤无意义候选） |
| 依赖 | **零第三方 Python 依赖**（标准库实现） |
| 数据新鲜度 | `index_freshness: stale=false`（索引与笔记一致，无过期） |
| 复现命令 | `python scripts/check_recall_baseline.py --repo testkb/ --demo`（退出码 0=达标） |

---

## 4. 局限声明（发布时必读）

这份数字**不代表**以下场景，请不要过度解读：

1. **样本太小**：8 条 query、4 篇文档，**不是**大规模真相评测。它在产品底线门禁（≥0.95/≥0.90）之上，不声称「任何库都 1.0」。
2. **非真实用户库**：`testkb/` 是套件自带的示例库（含刻意埋的脏数据），**不等价于**任何真实用户笔记的规模、领域与写法。
3. **中文为主**：测试集是中文 query；英文/多语表现需要独立测试集（v2 计划）。
4. **零 embedding**：本文检索是**纯词法（BM25）+ wikilink 图**，不做语义向量相似度。对「意图完全不同但字面相似」的问题，不是它的设计目标；后续可选 embedding 层（Phase 2 话题）会补语义维度。
5. **指标完整性**：recall/MRR 是**检索**质量，不评估 `query` 后接的 **LLM 回答质量**（生成净化、长引用整合）——那是另一套评测（待补）。
6. **没有交叉验证**：单库、单次、无置信区间。它定位是「可复现的工程基准」，不是学术 benchmark。

---

## 5. 后续计划（公开路线）

- **W3**：发布「如何复现」附录 + 把我们自己的 FAQ 长尾样例也纳入测试集；
- **Phase 2（Q10）**：新增语义召回（可选 embedding 层）后，公布「语义增强版本号」的对比基线；
- 每次 release 前 `eval` 快照自动进入 `eval_reports/`，长期趋势会随 `docs/` 归档可查。

---

## 附：原始报告引用

- 原始 JSON：`testkb/eval_reports/recall-eval-baseline-2026-08-31.json`
- 原始 Markdown：`testkb/eval_reports/recall-eval-baseline-2026-08-31.md`
- 等价命令：`python scripts/check_recall_baseline.py --repo testkb --build --out-dir <tmp> --demo`

---

未来版本：`v2`（语义增强后重跑）、`v3`（用户自建测试集模板发布）。