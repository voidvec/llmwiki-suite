---
title: 核心业务流程与数据流
description: 从笔记到问答的端到端流程、索引刷新三条路径与产物生命周期
tags: ["流程", "ingest", "index", "产物"]
difficulty: intermediate
categories: ["软件架构"]
kb_id: KB-02
legacy_kb_id: KB-03
kind: knowledge-base
status: derived
scope: 从原始笔记到答案的端到端流程、索引刷新规则、产物生命周期与版本库边界
audience: 使用者、排障者、要改主链路的工程师
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 核心业务流程与数据流

> **定位**：把散在 README / 三篇教程 / 源码里的流程合并成一条可执行的因果链，并纠正「索引是否自动刷新」这一高频误读。

## 1. 背景

对外宣传的主链路是「五步接入」：`init → ingest → index → query`（`README.md:32-38`）。但文档对「什么时候必须重建索引」存在历史口径与代码口径两种表述：getting-started 的「3 条铁律」是笼统旧口径（曾写作「索引不自动刷新」），而 `tutorial-01-system.md` §3.2 写明 `ingest --apply` 会自动重建索引。以代码为准（`ingest.py:416-419`）：`ingest --apply` 自动重建、`llmwiki index` 手动重建、`query` / `recall` 不自动重建只做新鲜度告警（口径基准 §0.3）。

## 2. 结论速览

| 结论 | 依据 |
|---|---|
| `kb-index.json` 是运行时单一事实源，改任一 `.md` 后必须重建 | `config.py` / `recall.py` 一律从索引取数 |
| **`ingest --apply` 会在 `run_ingest` 末尾自动调用 `gen_index()` 重建索引** | `ingest.py:416-419`，无需手工跑 `index` |
| `ingest`（dry-run，默认）**不写文件、不重建索引、不发任何 LLM 请求** | `run_ingest` apply 分支；LLM 条件含 `apply` |
| `lint` / `eval` / `health` 是旁路只读流程，不改变索引 | 三模块均无写索引路径 |
| 索引新鲜度检查只**告警不阻断**（mtime/size/hash 三向） | `recall.check_freshness` + `cli._warn_stale` |
| 所有产物中，只有用户 `.md` 与 `llmwiki.toml` / `eval_queries.json` 属于资产，索引与报告可再生成 | `.gitignore` + `cli.GITIGNORE_LINES` |

## 3. 关键关系

```
用户 .md 笔记（资产，入库）
   │
   ├─[1] init ──> llmwiki.toml / .gitignore / .pre-commit / templates/（资产+脚手架）
   ├─[2] ingest（dry-run 只出报告；--apply 才写）
   │        ├─ 补 frontmatter（缺则建、残则补四项）
   │        ├─ 文件名归一（git mv）
   │        ├─ SHA256 重复「仅报告不删」
   │        ├─ 建议目录「仅报告，--move 才动」
   │        └─ ★ 自动 gen_index() 重建索引
   ├─[3] index ──> kb-index.json + category-index.md（产物，不入库）
   └─[4] query / serve ──> recall → build_context → LLM → answer + 来源
              │
              ├─ 旁路 lint ──> lint-report.json（阻断式，errors>0 exit 1）
              ├─ 旁路 eval ──> eval_reports/recall-eval-*.{md,json,svg}
              ├─ 旁路 health ──> health-report.{json,html}（不阻断）
              └─ 旁路 telemetry ──> ~/.llmwiki/telemetry/events.jsonl（本地，不上传）
```

## 4. 主体内容

### 4.1 阶段 1：`init`（幂等、不覆盖）

写出 `TOML_TEMPLATE`（`[repo] / [ingest] / [categories] / [aliases] / [llm]` 五节）；若 `llmwiki.toml` 已存在且未加 `--force`，只打印提示不改写。`.gitignore` 采用**追加 marker**方式加入 6 行产物忽略项（`# --- llmwiki 产物`），不覆盖用户原有内容。脚手架文件（pre-commit 配置、`.github/workflows/kb-lint.yml`、两份模板）**已存在则跳过**。

### 4.2 阶段 2：`ingest`（默认 dry-run）

`run_ingest(cfg, apply, move, report, use_llm)` 逐文件生成计划：

1. `ensure_fm`：无 FM 前置完整块；有 FM 但缺必填项则在闭合 `---` 前补行。**行级编辑，不整篇重写、不删 `---`**。
2. LLM 推断：条件为 `apply AND 有 API_KEY AND use_llm AND 字段仍缺失`，**每文件至多一次**，只填仍为空的 categories / tags；单次 30s、全局预算默认 600s（`LLM_WIKI_INGEST_LLM_TOTAL_TIMEOUT`），任何异常静默降级。因此 dry-run 零调用，`--no-llm` 或未配 key 时 categories 留空（lint 不报错）。
3. `normalize_basename` → 记 `rename` action（全小写、空格/`_`→`-`、全角 `：`→`-`、中文保留）。
4. SHA256 去重 → **仅报告，不自动删除**。
5. `suggest_dir` → **仅报告，默认不跨目录移动**，`--move` 且目标目录存在、目标文件不存在才动。

输出 `ingest-report.json`；`--apply` 时写文件 → `git mv` → 可选 move → **重建索引**。

> **实现注记**：去重字典 `hashes` 建自原始文本，而检测用的是补全 FM / LLM 推断后的文本，两者 hash 口径不一致，重复检测基本难命中（见 PR-04）。

### 4.3 阶段 3：`index`

`os.walk` 跳过 `exclude_dirs` 与所有隐藏目录，只收 `.md`；**无 frontmatter 的文件被跳过**（不会进索引）。生成文档 20 字段、`category_index`、`tag_index`，并写出 `category-index.md`。这一步也是 `llmwiki.toml` 里 `[repo].index_file` 生效的地方。

### 4.4 阶段 4：问答

`cmd_query` 或 `serve` → `KbAssistant.answer()` → `KbRetriever.recall()` 取 Top-K → `build_context(max_chapters=4)` 组装上下文（命中 `matched_headings` 则取整章，否则全文；每段截 1200 字）→ `PROMPT_TMPL` → `call_llm`（30s，temperature 0.2）→ 回答 + 来源列表。无 API key 或网络异常时降级为「检索片段预览」，**不中断**。

SSE 路径走 `answer_stream()`，事件序列 `meta → candidates → delta* → done`（详见 KB-07）。

### 4.5 索引刷新规则（重点）

| 场景 | 是否自动重建 | 说明 |
|---|---|---|
| `llmwiki ingest --apply` | ✅ 是 | `ingest.py:416-419` 包内直调 `gen_index(cfg.repo, cfg)` |
| `llmwiki ingest`（dry-run） | ❌ 否 | 只产出报告 |
| 手工编辑任意 `.md` | ❌ 否 | 必须 `llmwiki index`；retriever 会报 stale 告警但不阻断 |
| `llmwiki lint / eval / health` | ❌ 否 | 只读 |
| `llmwiki categories-sync --apply` | ❌ 否 | 只改 TOML 文本 |
| `llmwiki serve` 长驻进程 | ❌ 否 | `/api/*` 每次请求重跑 `check_freshness()` 复查文件变更 |

`check_freshness()` 用 `st_mtime_ns + size` 快路径，不一致再用 blake2b `content_hash` 决胜，另扫索引外新增 `.md`（只读前 8192 字节验 FM 规则）；返回 `FreshnessReport(stale, unknown, changed, added, deleted)`。`generated-index` 文档豁免。

### 4.6 产物生命周期与版本库边界

| 类别 | 文件 | 入库 | 处置 |
|---|---|---|---|
| **用户资产（勿删）** | `llmwiki.toml`、`eval_queries.json`、`README.md`、全部笔记 `.md` | ✅ | 保留、纳入备份 |
| **可再生成产物** | `kb-index.json`、`category-index.md`、`ingest-report.json`、`lint-report.json`、`eval_reports/`、`health-report.*` | ❌ | 可安全删除后重建 |
| **脚手架** | `.pre-commit-config.yaml`、`.github/workflows/kb-lint.yml`、`templates/`（默认排除） | ✅ | `init` 已存在则跳过 |
| **本地状态** | `.ilink_session.json`、`~/.llmwiki/telemetry/events.jsonl` | ❌（应排除） | 会话与事件，见 PR-04 |

`docs/llmwiki-local-verify.md` 的重建流程即按此边界：先声明勿删资产 → 删除产物 → 建 venv → `init → ingest --apply --no-llm → index → lint → categories-sync --apply → eval`。注意该流程里仍跑了一次显式 `index`（与自动重建重复但无害）。

## 5. 注意事项与常见误读

1. **「改文档必须重建索引」是对的，但 `ingest --apply` 已经替你做了**；把它当成纯粹的文本改写会漏掉这一步的副作用（会重写 `category-index.md`）。
2. **dry-run 不等于只读**：它仍写 `ingest-report.json`；只是不碰笔记、不碰索引、不发 LLM。
3. **LLM 是可选增强，不是编译必需**：`--no-llm` 离线秒级完成，唯一差别是 categories/tags 需要人工或 `categories-sync` 补。
4. **重复与归类建议都不自动执行**：这是「内容所有权」约束的落地，别期待 ingest 会整理目录或删重。
5. `serve` 长驻时手工改笔记，检索结果可能过期；告警只写 stderr / `index_stale` 字段，不会自动重建。
6. 报告产物（尤其 `testkb/eval_reports/`、`.pre-commit-eval/`）是历史快照，不是实时状态；审计时以重新生成的结果为准。

## 6. 不确定 / 待补充项

- `ingest --apply` 自动重建索引这一点，**README / getting-started 的「3 条铁律」未体现**；`hn-post-draft.md` 与 `llmwiki-vs-rag-comparison.md` 把 `ingest --apply` 描述成「compile: frontmatter + index + link lint」，其中 **link lint 并非 ingest 执行**，属表述过度。
- 去重 hash 口径不一致是否属有意设计（避免补全前误判）无注释说明，待确认。
- 新建的 `knowledge-base/` 目录未加入 `DEFAULT_EXCLUDE_DIRS`；若在对仓库根跑 `llmwiki index`，本目录的 `.md` 会进入索引（是否应排除待决策）。
- `llmwiki-local-verify.md` 记录的「规范化 65 个文件名（Drogon 教程）」指的是作者**另一个笔记库**，不是本仓库；复现时不要在本仓库找这些文件。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/ingest.py` | `run_ingest` :281-421，尤其 :330 LLM 条件、:344 hash、:390-419 apply 与重建索引 |
| `src/llmwiki/cli.py` | `cmd_init` :117-135、`cmd_ingest` :141-147、`cmd_index` :150-157、`_warn_stale` :160、`GITIGNORE_LINES` :58-66 |
| `src/llmwiki/gen_index.py` | `collect` 跳过无 FM、`gen_index` :224-234 |
| `src/llmwiki/recall.py` | `check_freshness` :299-363、`FreshnessReport` |
| `src/llmwiki/assistant.py` | `PROMPT_TMPL` :22-39、`build_context` :148-156、`answer` :159 |
| `README.md` / `docs/getting-started.md` | 五步接入、3 条铁律 |
| `docs/llmwiki-local-verify.md` | 资产边界与重建流程 |
| `.gitignore` / `src/llmwiki/cli.py` 模板 | 产物忽略清单 |

## 8. 相关主题

- KB-01 系统架构、模块与依赖关系（静态结构）
- KB-04 配置三层模型与运行入口
- KB-05 检索与召回算法口径
- PR-04 已知偏差与待补充台账
