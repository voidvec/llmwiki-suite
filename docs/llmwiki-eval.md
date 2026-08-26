---
title: "llmwiki eval 命令参考：召回质量评估"
description: "llmwiki eval 的完整参考文档——全部命令行选项、评估集 schema、报告文件格式与字段、指标解读（recall@K/MRR/生产等价口径）与基线回归用法。"
categories: ['知识库规范', '软件架构']
tags:
  - llmwiki
  - eval
  - recall
  - mrr
  - reference
  - cli
difficulty: "intermediate"
estimated_time: "10分钟"
created: "2026-08-25"
updated: "2026-08-25"
version: "1.0"
---

# llmwiki eval 命令参考

> 面向：想量化检索质量、对比调参效果、或把召回基线接入 CI/pre-commit 的用户。
> 教程向（为什么评估、怎么建评估集、怎么调参）见 [[llmwiki-tutorial-03-quality-tuning]]；
> 本文是**参考向**——命令选项、文件格式、字段含义，一次查全。

---

## 1. 一句话

`llmwiki eval` 对**评估集**中每条 query 跑召回，产出 recall@K / MRR 指标 +
Markdown 报告 + JSON 快照。它是「调参前先留基线、调完后对比」的数字工具。

```
llmwiki eval [--repo <kb>] [--queries <file.json>] [--top-k N]
             [--min-score F] [--min-score-per-term F] [--prod-top-k N]
             [--out-dir <dir>] [--tag <label>]
```

---

## 2. 全部选项

| 选项 | 默认 | 作用 |
|------|------|------|
| `--repo <path>` | 当前目录（解析链） | 知识库根目录 |
| `--queries <file.json>` | `<repo>/eval_queries.json`，缺失时回退**包内置示例集** | 评估集路径 |
| `--top-k N` | 评估集 `top_k` 字段；再缺省 **4** | 召回截断 K（与生产 `build_context(max_chapters=4)` 同 K） |
| `--min-score F` | **0.15** | 绝对分数门槛（BM25 量纲），过滤无关键候选 |
| `--min-score-per-term F` | 套件/`llmwiki.toml` 配置值 | 每词阈值（查询长度感知），`0` 关闭 |
| `--prod-top-k N` | **4** | 生产等价口径的截断 K（见 §4.2） |
| `--out-dir <dir>` | `<repo>/eval_reports/` | 报告输出目录 |
| `--tag <label>` | `baseline-YYYY-MM-DD` | 报告/快照文件名标签（用于 before/after 对比） |
| `--retriever-desc <str>` | 内置检索器描述 | 覆盖 meta 中的检索器描述（记录用） |

---

## 3. 评估集 JSON 格式（schema）

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

字段：

- **`top_k`**（可选）：本次评估的 K，覆盖 CLI `--top-k` 的缺省值；
- **`queries`**：query 数组，至少 1 条；
  - **`query`**：用户视角的问法；
  - **`expected`**：期望命中的真实路径数组（必须都在检索索引内，启动时校验；**任一路径出现在 Top-K 即算命中**）；
  - **`note`**（可选）：说明文字，写进报告（如「同义改写挑战」「库外主题，预期 0 命中」）。

> 位置：放在知识库根目录 `eval_queries.json`，或任意路径用 `--queries` 指定。
> 编写要点（过拟合防护、库外负例）见 [[llmwiki-tutorial-03-quality-tuning]] §3.1。

---

## 3. 输出文件

默认落在 `<repo>/eval_reports/`（该目录被套件默认排除，**不会进检索索引、不触发 lint**）：

| 文件 | 内容 | 用途 |
|------|------|------|
| `recall-eval-<tag>.md` | 人读报告：meta + 汇总表 + 逐条命中/未命中 + 未命中 Top-K 明细 | 调参 review |
| `recall-eval-<tag>.json` | 机器快照：`{meta, summary, per_query}` | before/after diff、基线回归断言 |

控制台同时打印一条汇总与逐条结果（`+`/`-` 标记命中情况）。

---

## 4. 指标解读

### 4.1 summary 全部字段

| 字段 | 含义 |
|------|------|
| `count` | 评估 query 总数 |
| `hit_count` | 命中 query 数 |
| **`contextual_recall`** | recall@K = 命中数 / 总数。**「能不能找到」** |
| `prod_top_k` | 生产等价截断数（默认 4） |
| `contextual_recall_prod` | 命中且 rank ≤ `prod_top_k` 的占比——防「评估 K 能命中、生产截断后漏掉」的错位 |
| **`mrr`** | 命中条平均倒数排名（1/rank）。1.0 = 全部第 1 位。**「排得多靠前」** |
| `avg_rank_of_hits` | 命中条的平均排名（仅命中条） |
| `missed_queries` | 未命中 query 列表（定位根因入口） |

### 4.2 判断顺序

1. 先看 **recall@K**：找不到 → 检索/索引问题（R2/R3/R5，见 tutorial-03 §2）；
2. 再看 **MRR**：排得靠后 → 排序问题（R1/R4）；
3. 看 **missed_queries** 明细：逐条对照「期望 vs 实际召回」，归类根因；
4. 偶尔看 **prod-equiv recall**：生产截断会不会漏（正常应 ≥ recall@K）。

### 4.3 基线口径（与回归脚本一致）

- 历史基线（套件 `testkb` 实测）：**recall@4 = 100%，MRR@4 = 1.0**；
- CI / pre-commit 通用回调：**recall ≥ 0.95 / MRR ≥ 0.90**（防 flaky 下限）。

---

## 5. 常见用法

```bash
# 跑内置评估集（默认）
llmwiki eval

# 自定义评估集 + 关于 K
llmwiki eval --queries my-eval.json --top-k 4

# 打标签存快照（调参前留基线）
llmwiki eval --tag before-tune

# 改 min_score 后对比
llmwiki eval --min-score 0.10 --tag try-010

# 对比两个快照
python -c "
import json
b = json.load(open('eval_reports/recall-eval-before-tune.json'))
a = json.load(open('eval_reports/recall-eval-try-010.json'))
print('before:', b['summary']['contextual_recall'], b['summary']['mrr'])
print('after :', a['summary']['contextual_recall'], a['summary']['mrr'])
"

# 基线回归（不经 pytest，供 CI / pre-commit）：低于阈值退出码非 0
python scripts/check_recall_baseline.py --repo <kb> --build --recall 0.95 --mrr 0.9
```

---

## 6. 与其它命令的关系

| 命令 | 关系 |
|------|------|
| `llmwiki index` | **前置**。评估基于索引；改文档后必须重建再评估（索引不自动刷新） |
| `llmwiki lint` | 互补。lint 查结构（断链/词表/命名），eval 查检索质量 |
| `scripts/check_recall_baseline.py` | eval 的**断言化入口**（退出码 0/1/2），供 CI 与 pre-commit 集成 |

---

## 相关文档

- [[llmwiki-tutorial-03-quality-tuning]]（教程：评估集设计、调参循环、六类失效）
- [[llmwiki-tutorial-01-system]]（体系搭建）
- [[llmwiki-architecture]]（检索机制与性能细节）
