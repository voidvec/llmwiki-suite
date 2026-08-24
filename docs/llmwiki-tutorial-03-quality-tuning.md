---
title: "LLMWiki 检索质量调优：评估、诊断与调参"
description: "当知识库问答检索质量不满足时（答非所问、明明有却查不到、命中一堆无关文档），如何用评估集量化问题、对照根因归类定位、按测-改-测循环调参（BM25/min_score/停用词/正文索引/wikilink 图）。"
categories: ['知识库规范', '软件架构']
tags:
  - llmwiki
  - rag
  - bm25
  - retrieval
  - evaluation
  - tutorial
difficulty: "advanced"
estimated_time: "25分钟"
created: "2026-08-20"
updated: "2026-08-24"
version: "2.0"
---

# LLMWiki 检索质量调优：评估、诊断与调参

> 适用对象：已按《[[llmwiki-tutorial-01-system]]·体系搭建》建好知识库、把问答跑起来的用户，但检索质量不满意。
> 本文是**演进文档**，随评估集扩充与调参持续更新。核心心法：**先建评估集，再改，最后看数字说话**。

---

## 0. 什么时候看这篇

| 文档 | 定位 |
|------|------|
| [[llmwiki-tutorial-01-system]] | 一次读完整篇，从零跑通 Ingest / Query / Lint |
| **本文** | 已经跑起来了，但「答非所问 / 查不到明明存在的内容」——教你用数字定位问题 |
| [[llmwiki-architecture]] | 系统架构与设计决策总览 |

**核心心法一句话**：先建评估集，再改代码，最后看数字说话。不要凭手感调参——否则无法确认「改好了」还是「改歪了」。

---

## 2. 检索质量差，通常坏在哪（六类失效速查）

| # | 现象（用户视角） | 根因 | 对应机制 |
|---|----------------|------|---------|
| R1 | 问「XX 做了哪些性能优化」回「未找到」，但库里明明有答案 | **排序反转**：高频词（性能优化）把含它的无关文档顶到前面，真正含判别词（路由/绑定）的被压到后面 | BM25 的 idf 压高频词、抬判别词 |
| R2 | 答案只在**正文段落**就查不到 | **正文没进索引**：只索引元数据 | `body_text` 正文索引 |
| R3 | 中文换个词就问不出；被拆成噪声 gram | **中文无词边界 + 无停用词** | 2-gram + 单字停用词「含任一即弃」 |
| R4 | 匹配到一堆无关文档，真文档被稀释 | **min_score 量纲不对**：旧阈值与 BM25 量纲冲突 | `min_score=0.15`（BM25 量纲） |
| R5 | 真实文档排第 5，但答案里看不到 | **截断**：上下文只取 top-k | `build_context(max_chapters=4)`（P5 收紧） |
| R6 | LLM 回「知识库中未找到相关信息」 | **话术掩盖**：把「片段不足以回答」伪装成「查不到」 | 话术区分「真无候选」与「有候选但不足」 |

> 判断入口：「**答非所问**」→ R1/R4；「**查不到但内容存在**」→ R2/R3/R5；「**老是说未找到**」→ R5/R6。多数问题非单根因，先跑评估集拿数据再下结论。

---

## 3. 建立评估基准（先别急着调）

### 3.1 内置评估集 + 自定义评估集

套件自带一份**通用评估集**（`llmwiki eval` 直接可跑），覆盖会议纪要 / BM25 调优 / 部署 / 导航等通用主题，期望路径均为相对路径——任何库都能直接产出有意义的 baseline。

如果你想针对自己的库定制，新建一个 JSON 评估集（schema 如下）：

```json
{
  "top_k": 4,
  "queries": [
    {
      "query": "检索引擎用了什么方案",
      "expected": ["notes/weekly-sync.md", "notes/bm25-tuning-log.md"],
      "note": "任一路径命中即算 hit"
    }
  ]
}
```

编写要点：

1. **收录真实失败 query**：你实际问过且答错的问法都放进来；
2. **覆盖多主题域**：10+ 主题域起步，避免只测单一领域；
3. **加语义改写挑战**：同一意图换措辞，防止评估集过拟合；
4. **期望路径必须是索引内真实路径**：`llmwiki eval` 启动时会校验 expected 是否都存在；
5. **加库外主题 query（预期返回空）**：这是检验 `min_score` 门槛是否有效的唯一方式。

### 3.2 跑评估

```bash
# 用内置评估集（默认）
llmwiki eval

# 用自定义评估集
llmwiki eval --queries path/to/my-eval.json

# 打标签存快照（调参对比用）
llmwiki eval --tag baseline-2026-08-24

# 调参后对比
llmwiki eval --min-score 0.10 --tag try-010
```

输出落 `<库根>/eval_reports/`（**刻意不进 `docs/`**——评估快照不应进入检索索引，否则污染检索 + 触发 lint frontmatter）：

- `recall-eval-<tag>.md`：人读报告（逐条命中/未命中 + 汇总指标）；
- `recall-eval-<tag>.json`：机器可对比快照（before/after diff 用）。

### 3.3 指标怎么读

| 指标 | 含义 | 备注 |
|------|------|------|
| recall@4 | 期望文档出现在 Top-4 的 query 占比 | 与生产 `build_context(max_chapters=4)` **同 K**（P5 收紧） |
| MRR@4 | 命中 query 的平均倒数排名 | 1.0 = 全部 rank 1 |
| prod-equiv recall@4 | 生产等价口径 | 防止「生产能答、评估说失败」错位 |

判断顺序：先看 recall@4（能不能找到）→ MRR（排得多靠前）→ 未命中清单（定位是哪类根因）。

---

## 4. 当前检索机制速览（调参坐标系）

这是套件内置检索机制的现状，也是你调参的坐标：

| 机制 | 默认值 | 说明 |
|------|--------|------|
| 检索算法 | **BM25**（K1=1.5, B=0.75） | idf 压高频词、抬判别词 |
| 字段 boost | 标题 3.0 > 标签 2.0 > 章节 1.5 > 正文/描述/摘要 1.0 > 分类 0.8 | 标题命中权重最高 |
| 正文索引 | `body_text`（BM25 用，剥代码块、保留 inline）；`body_text_clean`（wikilink 扫描用，再剥 inline） | 双变体：代码可检索，又不让 C++ `[[ ]]` 误报 |
| 中文分词 | 滑 2-gram + 单字停用词「含任一即弃」 | 保留 `路由/绑定/性能`，丢弃 `由与/与绑/定做` |
| 覆盖面系数 | **线性 ramp**：cov=0 → 0.7；cov≥0.34 → 1.0；区间线性 | 替代硬阶跃边界跳变 |
| min_score | **0.15**（BM25 量纲） | 绝对门槛，过滤无关键候选 |
| min_score_per_term | **1.0**（每词阈值） | 与查询长度感知；设 0 关闭 |
| wikilink 图 | 出链图 + `via_link` 补位 | **只补位不顶替**：link 文档永远压不过最弱直接命中 |
| link_gate | **0.5** | via_link 补位文档自身分须达门槛×系数（设 0 关闭） |
| 打分缓存 | R3：init 一次性分词，打分纯查表 | 由 ~854 ms/条 → **~5 ms/条**（~170×） |
| 索引过期检测 | P3：mtime/size/hash 三向比对，`check_freshness()` | ~11 ms/188 篇；改文档后漏建索引会测到旧数据 |
| 上下文 | `build_context(max_chapters=4)` | P5 收紧：6 章 → 4 章省 ~35% token |
| 兜底话术 | 区分「真无候选」与「有候选但不足」 | 不再一刀切「未找到」 |

> 各机制的默认值、别名组、词表等都在 `llmwiki.toml` 可控（见 [[llmwiki-tutorial-01-system]] §2.1）。

---

## 5. 调优实操（测-改-测循环）

### 5.1 先跑基线，再改一个变量

```bash
# ① 留基线
llmwiki eval --tag before-tune

# ② 调参（比如改 min_score）：
#    编辑 llmwiki.toml [recall] 段的 min_score_per_term / link_gate / min_score（0=关闭）

# ③ 重建索引（改文档后必须）
llmwiki index

# ④ 再评估
llmwiki eval --tag after-tune

# ⑤ 对比两个 json 快照
python -c "
import json
b = json.load(open('eval_reports/recall-eval-before-tune.json'))
a = json.load(open('eval_reports/recall-eval-after-tune.json'))
print('before:', b['summary']['recall'], b['summary']['mrr'])
print('after :', a['summary']['recall'], a['summary']['mrr'])
"
```

> 规则：**一次只改一个变量**。同时改多个参数，永远不知道哪一项起的作用。

### 5.2 调参优先级（按性价比）

1. **先扩评估集**：遇到新失败 query 就加；
2. **调 `min_score` / `link_gate`**：「没有却返回一堆」→ 升；「该命中没命中」→ 降或关；
3. **调 BM25 / 词表**：改 `llmwiki.toml [recall]` 或 `[categories]`；改了必须建索引；
4. **看 link 补位是否显形**：fast 候选充足时 link 天然不显形（只补位），如果评估集里 direct 命中太少，问题在 BM25 本身。

### 5.3 改文档后的铁律

知识库是「带 git 的 markdown 仓库」：**改任何 `.md` → 跑 `llmwiki index` 重建 → 重新评估**。索引不自动刷新，忘重建 = 评估在测旧内容。

---

## 6. 什么时候考虑混合检索（语义向量）

默认 BM25 是**零依赖、本地化、可解释**的主线。要不要加语义检索？触发条件（满足其一）：

1. **知识库 ≥ 2000 篇**：规模上来后纯关键词的语义短板被放大；
2. **评估集显示 BM25 不足**：recall@4 < 0.7 且扩充集后仍长期如此;
3. **问法极大偏离关键字**（如「帮我总结上半年绩效评审结论」完全没命中任何文档）。

若要升级，常见路径：**稠密向量（bge-small-zh / OpenAI 兼容 embedding）+ RRF 融合 + cross-encoder 重排**。套件为后续留了接入点（`KbRetriever` 接口可期，但**如今尚未内置向量检索**，需要自行扩展或引入轻量向量库）。

> 贴上规模错配经验：< 2000 篇时，纯 BM25 + 检索优化（min_score/覆盖度/link 扩展）通常足以达标，向量检索是复杂度 + 资源，先量化再决定。

---

## 7. 常见坑

| 坑 | 说明 | 对策 |
|----|------|------|
| 期望路径不在索引里 | 评估启动会校验 | `llmwiki index` 重建后核对 |
| 改了正文忘重建 | 评估测旧内容 | 铁律：改文档 → 重建 → 评估 |
| `min_score` 用旧 1.0 | BM25 量纲下真文档被滤掉 | 用 0.1~0.5 量级（默认 0.15） |
| 评估集全是「用语复述」 | 过拟合，换个说法就挂 | 刻意加入同义改写、口语 query |
| 同时改多变量 | 无法归因 | 一次只改一个，存 before/after |
| 把评估报告写进 `docs/` | 进检索 + lint 报错 | 默认 `eval_reports/`，别改输出目录 |
| 以为向量检索是必需 | 小库 BM25 足够 | 先看数字，再决定 |

---

## 相关文档

- [[llmwiki-tutorial-01-system]]（体系搭建，一次跑通）
- [[llmwiki-tutorial-02-channel]]（渠道接入）
- [[llmwiki-architecture]]（架构细节与通道）
- [[getting-started]]（五步快速上手）