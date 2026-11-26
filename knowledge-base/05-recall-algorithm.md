---
title: 检索与召回算法口径
description: BM25 打分、字段权重、中文 2-gram、别名组、覆盖度 ramp 与 wikilink 补位
tags: ["检索", "BM25", "调优"]
difficulty: advanced
categories: ["软件架构"]
kb_id: KB-05
legacy_kb_id: KB-06
kind: knowledge-base
status: derived
scope: BM25 实现、字段权重、中文分词、别名扩展、覆盖度 ramp、链接补位、缓存与新鲜度、调参坐标系
audience: 做检索调优、评估回归或二次开发的工程师
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 检索与召回算法口径

> **定位**：把 `recall.py` 的实现参数、设计动机与调优方法整理成可查的工程口径。教程 `tutorial-03` 讲「怎么调」，这篇讲「到底在调什么」。

## 1. 背景

召回是本项目唯一的核心算法，完全自研、零第三方依赖：BM25 + wikilink 图补位，无 embedding。0.1.0 起经历了 P1 别名组 / R1 每词阈值 / R2 覆盖度线性 ramp / R3 打分缓存（约 170×）/ P3 索引新鲜度 / P4 via_link 补位门槛 / top_k 收紧 4 等迭代（`CHANGELOG.md`）。这些字母编号是版本史里的改进代号，不是模块名。

## 2. 结论速览

| 项 | 值 |
|---|---|
| 打分 | `idf * tf*(K1+1) / (tf + K1*(1-B+B*dl/avgdl))`，K1=1.5、B=0.75，**按字段分别统计 avgdl** |
| 字段权重 | title 3.0 > tags 2.0 > headings 1.5 > body_text / description / summary 1.0 > categories 0.8 |
| 中文 | 连续汉字串切滑动 2-gram；单字停用表「含任一即弃」；重复 token 保留以维持 tf |
| 门槛 | `effective_min = max(min_score=0.15, min_score_per_term=1.0 * len(terms))` |
| 覆盖度 | 线性 ramp：`cov=0 → ×0.7`，`cov≥0.34 → ×1.0` |
| 链接补位 | 只补位不顶替，`link_boost = min(direct.score) * 0.5`，需过 `link_gate=0.5` 门槛 |
| 默认 top_k | **4**（`recall()` 签名 / CLI `--top-k` / `QueryReq` / `build_context.max_chapters` / `prod_top_k`） |
| 公开基线 | 8 条 query，`contextual_recall@4=1.0`、`mrr@4=1.0`、未命中 0 |

## 3. 关键关系：一次查询的流水线

```
query 文本
  → tokenize（英文整词 / 中文 2-gram / 停用字过滤）+ expand_aliases
  → terms（dict.fromkeys 去重，保序）
  → _candidates（categories 用倒排并集；tags 用倒排交集；无过滤则全库）
  → _score_doc（7 字段 × terms 累加 BM25*boost → 覆盖度 ramp）
  → effective_min 过滤 → direct（按分降序）
  → via_link 补位（仅 direct 非空且链接图非空）
  → 重排 → 取 top_k
  → build_context(4 章 / 1200 字每章) → LLM
```

## 4. 主体内容

### 4.1 索引与缓存（R3）

`KbRetriever.__init__` 一次性构建：`_blobs`（各字段别名扩展后的文本）、`_blobs_low`、`_field_tf[path][field] = Counter`、`_field_dl`、`df`（文档级去重计数）、`avgdl`（按字段）、`_link_graph`。之后 `_bm25` 变成纯查表算术，单次查询从约 854 ms 降到约 5 ms（约 170×）。

### 4.2 分词与别名

- `tokenize` 用 `re.findall(r"[一-鿿]+|[a-zA-Z0-9_]+", text.lower())`；英文/数字整体成词，中文长度 >1 切 `[c[i:i+2] for i in range(len-1)]`。
- 停用字集 `_CJK_STOP = "与的了这那是在和对如何怎么一个可以我们你们做哪些"`，`cjk_stop=True` 时**丢弃含任一停用字的 gram**。
- **保留重复 token**：早期去重会让 tf 恒 ≤1，使 K1 饱和调节失效（`recall.py` docstring 明确记录）。
- `expand_aliases`：组内任一变体命中即把其余变体追加到文本末尾；ASCII 变体用词边界正则，中文变体用子串匹配。**索引侧与查询侧双向扩展**，故 k8s ↔ kubernetes 可互命中。默认 5 组（kubernetes/k8s、end-to-end/e2e/端到端、系统架构/architecture、可观测性/observability、反向代理/reverse-proxy）。

### 4.3 打分与门槛

`_score_doc` 对 7 个字段逐 term 累加 `BM25 × FIELD_BOOST`；`matched_headings` 记录命中标题，供 `build_context` 取整章。覆盖度 ramp：

```
factor = 0.7 + 0.3 * min(coverage / 0.34, 1.0)
score *= factor
```

用线性替代旧硬阶跃，消除约 43% 的分数跳变。`effective_min = max(0.15, per_term × len(terms))` 实现「查询长度感知」：`min_score_per_term=1.0`，0 可关闭。设计注释给过判别区间：真查询最弱约 3.60 分/词，库外主题 Top-1 最高约 2.08 分/词，因此 1.0 能挡住库外噪声又保留真命中。

### 4.4 wikilink 图补位（P4）

`_build_link_graph` 用 `body_text_clean` 扫 `WIKILINK_RE`，经 `kb_core.build_link_index` 解析，只收索引内真实文档；异常降级为空图。补位规则：

- 仅当 `direct` 非空才扩展；只取 direct 文档的**出链**、且不在 direct、且在候选集内。
- `link_boost = min(h.score for h in direct) * 0.5` —— 任何补位文档都不可能压过最弱直接命中。
- `score = max(own_score, link_boost)`，并需 `own_score >= effective_min * link_gate(0.5)`；`link_gate=0` 关闭。
- 命中标记 `via_link=True`；补位后重排，最终仍取 `direct[:top_k]`。

设计动机：342 次命中里出现 3 条链接噪声，噪声得分 <0.5 分/词，低于期望文档最弱 0.7 分/词。

### 4.5 新鲜度（P3）

`check_freshness()`：`has_fp` 判断索引是否含 `mtime_ns`；快路径 `st_mtime_ns + size`，不一致再用 `content_hash()`（blake2b 16B）决胜；`deleted` 靠 `os.stat` 异常；`added` 用 `os.walk` 找索引外 `.md` 并读前 8192 字节验 `FM_RE`；`kind=="generated-index"` 与 `category-index.md` 豁免。实测约 11 ms / 188 篇。**只告警，不改变查询或退出码**。

### 4.6 上下文组装

`build_context(max_chapters=4)`：有 `matched_headings` 就 `fetch_chapter()` 取整章，否则 `read_doc()` 读全文；每段格式 `【title】\n<chunk[:1200]>`，用空行连接。从 6 章缩到 4 章约省 35% token。`assistant.PROMPT_TMPL` 要求「仅根据片段回答、不编造、不声称『知识库中未找到』、多自然段短列表、引用来源标题」。

### 4.7 失效分类与调优循环（tutorial-03）

六类失效编号 **R1–R6**（教程用于定位问题类型）；调参坐标系集中在 `llmwiki.toml [recall]` 的 `min_score_per_term / link_gate`，以及 CLI 的 `--min-score`。标准「测-改-测」循环：

1. `llmwiki eval --tag before-tune` 留基线；
2. **一次只改一个变量**；
3. `llmwiki index` 重建；
4. `llmwiki eval --tag after-tune`；
5. 对比两份 JSON 快照的 `summary.contextual_recall` / `mrr`。

评估集编写 5 要点：收录真实失败 query、覆盖 10+ 主题域、加语义改写挑战、expected 必须是索引内真实路径、**加库外主题 query（预期返回空）**。

### 4.8 混合检索的触发条件（当前未实现）

教程给出三条门槛：知识库 ≥2000 篇 / recall@4 <0.7 且扩集后长期如此 / 问法极大偏离关键字。路径是「bge-small-zh 或 OpenAI 兼容 embedding + RRF 融合 + cross-encoder 重排」。**代码里没有任何向量检索实现**，且 scope-freeze 明确本期不做向量/embedding 系统设计。

## 5. 注意事项与常见误读

1. **BM25 分数不是相似度也不是概率**，`min_score=0.15` 只是该量纲下的低门槛，跨库不可比。
2. **改任何 `.md` 都要重建索引再评估**；`ingest --apply` 已自动重建，但手工编辑没有。
3. **对比快照脚本曾用错字段**：`tutorial-03` 原写 `b['summary']['recall']`，真实字段是 `contextual_recall`；该处已于 2026-11-11 修正（PR-04 §1 修订记录）。
4. **`--demo` 的高分不代表你的库质量**：内置集指向 demo 库（KB-03）。
5. **公开基线的局限**（`llmwiki-eval-report-v1.md` 自述 6 条）：样本仅 8 条、非真实用户库、以中文为主、零 embedding、不评估 LLM 回答质量、无交叉验证。
6. `defaults.DEFAULT_TOP_K = 6` 是死常量；不要误当默认值。
7. `eval_recall.py` docstring 写 `max_chapters=6`，与实现 4 不符。

## 6. 不确定 / 待补充项

- `FIELD_BOOST` / `K1` / `B` / `COVERAGE_FULL` 是硬编码常量，**不通过 `llmwiki.toml` 暴露**；是否需要可配置化未定。
- 中文停用字表是硬编码的 20 余字，未见评估依据，扩库后可能需要重新校准。
- `min_score_per_term` 在 `serve` 路径下不生效（TOML 未注入，KB-04），因此 CLI 调好的参数在 Web/IM 问答里不一定生效，**需实测确认**。
- 覆盖度阈值 0.34 与 ramp 下限 0.7 的取值来自一次调优实验，缺少可复现实验记录。
- `open_prs` / 检索质量之外的统计口径缺陷见 PR-04；本篇只覆盖算法。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/recall.py` | `FIELD_BOOST` :98-106、`K1/B` :109、`COVERAGE_*` :113-114、`tokenize` :131-152、`expand_aliases` :168-186、`_bm25` :389-398、`_build_link_graph` :401、`_candidates` :426、`_score_doc` :445、`recall` :473-542、`check_freshness` :299-363 |
| `src/llmwiki/defaults.py` | 别名组、门槛默认值与注释里的判别区间 |
| `src/llmwiki/assistant.py` | `build_context` :148-156、`PROMPT_TMPL` |
| `CHANGELOG.md` 0.1.0 | P1/R1/R2/R3/P3/P4 改进代号与 ~170× / ~35% 数字 |
| `docs/tutorials/llmwiki-tutorial-03-quality-tuning.md` | 六类失效、调参坐标系、测-改-测循环、混合检索触发条件 |
| `docs/llmwiki-eval-report-v1.md` | 8 条 query / `contextual_recall@4=1.0` / `mrr=1.0` / 6 条局限 |
| `testkb/eval_reports/*.json` | Top-1 分数实例 23.301 / 6.024 / 28.803 / 32.832 / 34.254 / 11.897 / 41.054 / 10.026 |

## 8. 相关主题

- KB-02 核心业务流程与数据流
- KB-03 关键概念与术语词典
- KB-06 质量保障体系与门禁
- PR-04 已知偏差与待补充台账
