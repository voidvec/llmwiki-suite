---
title: "设计：eval_queries.json 的生成时点与无评估集行为"
description: "针对『新用户没有 eval_queries.json 时 llmwiki eval 的行为』与『eval_queries.json 应该在哪个阶段被生成/更新』的设计决策文档：现状问题、三阶段生成策略、四场景矩阵、推荐方案与实施清单。"
categories: ['知识库规范', '软件架构']
tags:
  - llmwiki
  - eval
  - recall
  - design
  - architecture
difficulty: "advanced"
estimated_time: "15分钟"
created: "2026-08-27"
updated: "2026-08-27"
version: "1.0"
---

# eval_queries.json 的生成时点与无评估集时的召回成功率设计

> 背景：真实库排查中遇到「`llmwiki eval` 静默降分」与「新库无评估集时 eval 出现假 100%」两个问题。
> 本文回答两个问题：**u200b①无 eval_queries.json + 有索引时，召回成功率该如何设计？（不能是误导性的假 100%）**；
> **u200b② eval_queries.json 应该在什么阶段被生成 / 更新？**

---

## 1. 现状与问题

### 1.1 当前行为（0.1.3 实测）

| 场景 | 行为 | 结果 |
|---|---|---|
| 有 `<repo>/eval_queries.json` | 用它评估 | 正确 |
| 无评估集 + 有索引 | **回退到包内置 `data/eval_queries.json`**（8 条 demo 集，expected 指向套件 testkb 的笔记） | **假 100%（8/8）**：库内容与 demo 集无关但因恰好存在同名文件而全命中 |
| 无评估集 + 无索引 | 先回退内置集，再拦「索引缺失」退出 | 提示但 exit 0 |

实测输出（testkb 无 eval_queries.json）：

```
[eval] ⚠ 未找到 testkb/eval_queries.json，回退使用套件内置示例评测集。
[eval]   内置集 expected 指向套件 demo/notes 库，与你的知识库无关，分数不具参考意义！
[eval]   请放置 <库根>/eval_queries.json（见 docs/llmwiki-eval.md），或用 --queries 指定评测集。
[eval] 8 queries, recall@4 = 100.0% (8/8), MRR@4 = 1.0
```

> ⚠ 关键缺陷：**stderr 的 3 行警告是防伪标记，但 stdout 的 100% 是「假阳性」**——新用户会误以为自己的库检索质量很好，实际是在考另一套题。

### 1.2 结论：现状是不可信的「幻读」

- **不是 0%**（那至少说明「没考到」），而是**虚假高分**——最危险的一种失败模式；
- 真正的「无评估集」应该是**显式阻断 + 引导**，而不是给一个误导性分数。

---

## 二、设计目标

1. **诚实**：不给假分数；无评估集 = 明确告知「未评估」，而不是「100%」；
2. **可引导**：缺失时给出「如何生成」的具体步骤（不打断首次体验）；
3. **可自动生成**：减少人工建评估集的成本，让新用户 5 分钟内拥有第一版评估集；
4. **可持续更新**：ingest 改名后评估集能自动跟随，不产生静默假 miss（已通过
   `_resolve_expected_paths` 在 eval 侧兜底，见 llmwiki-eval.md）。

---

## 三、eval_queries.json 生成时机：三阶段策略

评估集生命周期分为三个时点，每个时点产出一个版本，难度和完整度递增：

| 阶段 | 触发时点 | 产物 | 完整性 | 自动化程度 |
|------|----------|------|--------|------------|
| **T0 骨架** | `llmwiki init` | `eval_queries.json`（种子模板，指向 `templates/` 或 `README.md` 等稳定文件） | 空壳可运行（2~3 条） | 全自动 |
| **T1 首版** | 首次 `llmwiki index` 后 | 基于真实索引自动采样：从文档标题/分类中生成 10~20 query，expected 用**索引内真实 path** | 可跑、真实命中率低（反映初始质量） | 半自动（可加开关） |
| **T2 维护** | `ingest` 后 / 手动 | 人工补充领域 query + `_resolve_expected_paths` 自动修复过期路径 | 完整、有代表性 | 手动 + 自动修复 |

---

## 四、设计：无评估集时的 eval 行为（推荐）

### 4.1 核心变更：把「假 100%」改成「显式未评估」

```
无 eval_queries.json + 有索引：
  → 不执行评估
  → stdout 清晰提示「未评估：库中无评估集」
  → 退出码 = 2（区别于真实评估命中的 0 / 未达标的 1）
  → 引导：`llmwiki eval --seed` 一键生成 或 手动放置 eval_queries.json
  → stderr 不再输出误导性的「回退内置集 100%」
```

### 4.2 新增子命令 / 选项（选择一种接口）

| 接口 | 行为 |
|------|------|
| **A. `llmwiki eval --seed`** | 用当前索引自动生成 `eval_queries.json`（摘要→query 模板 → 期望 = 该 doc path），再立即跑一次评估 |
| **B. `llmwiki init --with-eval`** | init 时生成种子评估集（指向 templates/README），首次 eval 就有「最小可跑」 |
| **C. `eval` 检测到无评估集时自动提示** 用法 | 不改默认行为，只把提示从 stderr 提到 stdout 首行 + 退出码 2 |

> 我们倾向 **先做 B（init 生成） + 快速做 C（把警告提升到 stdout + 退出码 2）**，`--seed` 作为后续增强。

### 4.3 退出码语义（与 `check_recall_baseline` 对齐）

| 退出码 | 含义 |
|--------|------|
| 0 | 有评估集且达标 |
| 1 | 有评估集但未达阈值（供 CI/pre-commit 基线回归沿用） |
| **2（新增）** | **无评估集 / 无法评估**（避免「误当成 1 的真失败」与「误当成 0 的假通过」） |
| 3 | 索引缺失（把现在 exit 0 改成 3，供脚本判断） |

---

## 5. 对比：三种「无评估集」处理策略

| 方案 | 行为 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **现状（回退内置）** | 内置 demo 集跑出「100%」 | 总有一个数 | **假阳性**、误导新用户 | ❌ 淘汰 |
| **A. 硬报错** | 无评估集 exit≠0，提示先建 | 诚实、绝不会假 100% | 首次体验断点，无评估集时无法 warm | ✅ 作为「快速可用性」的一部分 |
| **B. 引导 + 种子 + 退码 2** | init 生成种子 → 无真评估集时 eval 打印「未评估」+ exit 2 | 不误导 + 可引导 + 保留自动生成路径 | 需实现 2 个新能力（seed/受退绿） | ✅ 推荐 |

---

## 6. 推荐实施清单（供拍板）

1. **T0 种子**：`llmwiki init` 时同步生成 `eval_queries.json`（3 条，expected 指向 `templates/meeting-notes.md`、`templates/book-notes.md`、`README.md`——这些是 init 必产的真实文件，避免「expected 指向不存在的文档」）；
2. **行为收紧**：`llmwiki eval` 找不到评估集 → **不评估**，stdout 打「[eval] 未在 <repo> 找到 eval_queries.json；已跳过。运行 llmwiki init（生成种子）或放置后重试」→ **退出码 2**；
3. **`--seed` 增强（可选，二期）**：`llmwiki eval --seed` 从索引采样标题生成首版评估集（18~30 条），一条命令完成「建集 + 跑分」；
4. **保留内置集**：内置 `data/eval_queries.json` 仅作为**该套件自己的冒烟测试**（跑 `llmwiki eval --queries <内置集>` 才能看到 demo 分），不再自动回退；
5. **文档**：在 `getting-started.md` 第 2 步告知「index 后可用 `eval --seed` 生成首版评估集」；在 `llmwiki-eval.md` 写明退出码 2 语义。

> **给新用户的一句话引导**：
> ```
> cd ~/my-notes && llmwiki init && llmwiki ingest && llmwiki index && llmwiki eval --seed
> ```
> 这样他第一条评估集是用**他自己的文档**生成的，分数才「有意义」。

---

## 7. 风险评估与对冲

| 风险 | 对冲 |
|------|------|
| `--seed` 生成的 query 与真实需求不符（过拟合） | 生成的 query 标记 `autogen: true`，报告里可过滤；文档明确「仅供参考，请人工补充」 |
| 种子评估集指向模板文件（非知识内容） | 模板由 init 保证存在；预期分数低（~50%）也**诚实**，正好提示用户补充 |
| 内退 2 导致 CI 首次失败 | CI 模板里 `eval` 挂接在 `--with-eval` 显式开启的 job 上，或在 T0 后种子必然存在 |
| 迁移成本 | 改动集中在 `eval_recall.main` + `cli.init` 两处，测试 `test_eval` 增加 1 个「无评估集→退 2」用例 |

---

## 8. 图：评估集生命周期

```mermaid
flowchart LR
    A[llmwiki init] -->|T0 种子 3 条| B[eval_queries.json 锁定]
    B --> C[llmwiki ingest]
    C --> D[llmwiki index]
    D -->|T1 首版/deep| E[eval --seed 生成 18~30 条]
    E --> F[llmwiki eval]
    F -->|T2 扩容| G[手工 + eval_queries.json 编辑]
    G --> F
```

---

## 9. 关联文档

- [[llmwiki-eval]]（命令参考/退出码语义）
- [[llmwiki-tutorial-03-quality-tuning]]（怎么建评估集、六类失效）
- [[llmwiki-getting-started]]（init/ingest/index 链路）
- [[llmwiki-architecture]]（检索机制）