---
title: 系统架构、模块与依赖关系
description: 六层模块依赖图、共享内核 kb_core、循环依赖规避与索引产物 schema
tags: ["架构", "模块依赖", "数据契约"]
difficulty: advanced
categories: ["软件架构"]
kb_id: KB-01
legacy_kb_id: KB-02
kind: knowledge-base
status: derived
scope: 源码分层、模块职责、依赖方向、共享内核、核心数据结构与产物 schema
audience: 要改代码或做架构评审的工程师
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 系统架构、模块与依赖关系

> **定位**：还原代码实际怎么分层、谁依赖谁、数据以什么结构流转。纯代码推导，不照抄 `docs/llmwiki-architecture.md` 的设计稿表述。

## 1. 背景

项目源码集中在 `src/llmwiki/`（14 个核心模块 + `channels/` 8 个模块），全部只依赖标准库，服务层才引入 fastapi。架构文档 `docs/llmwiki-architecture.md` 原写「五层职责」但表格有 6 行、mermaid 引用的 `_gen_query_index.py` 并不存在（两处已于 2026-11-11 修正，见 PR-04 §1 修订记录）；因此这篇以 import 关系为准重建分层。

## 2. 结论速览

- **六层单向依赖**，无循环依赖；`cli.py` 通过函数内延迟导入把重模块与可选依赖隔离在入口之外。
- **`kb_core.py` 是唯一共享内核**：frontmatter 解析、链接归一四铁律、链接索引被 `gen_index / ingest / lint / health / recall` 五处复用，是「链接判死」口径的事实源。
- **两处刻意防成环**：`recall → gen_index.content_hash` 单向；`config.load_vocab` 直接读 JSON 而不 import `gen_index`；`assistant` 延迟导入 `recall` 让 serve 启动不读索引。
- **索引 `kb-index.json`（schema 1.1）是运行时单一事实源**，所有检索、lint、health、eval、通道问答都从它派生。
- **服务层是薄装配层**，但 `wechat_bridge.py` 只把 `INDEX` 注入 `KbAssistant`，导致 `llmwiki.toml` 的多数配置在 serve 下失效（见 PR-04）。

## 3. 关键关系

```
L6  入口        cli.py ──(函数内延迟导入)──> L2..L5
L5  传输层      channels/{wechat_bridge, wecom, feishu, telegram, ilink,
                           wecom_crypto, channel_base}
                  └─ depends on → fastapi, assistant(L4), config(L2), _env(L0)
L4  编排/评估   assistant.py(惰性→recall) / eval_recall.py / telemetry.py
L3  业务引擎    ingest.py / lint.py / health.py / recall.py
L2  配置/产物   config.py / gen_index.py
L1  共享内核    kb_core.py（纯标准库）
L0  常量/环境   __init__.py / _env.py / defaults.py
```

依赖方向一律 L6→L0，**没有任何反向边**。模块级 import 清单要点：

| 模块 | 关键依赖 |
|---|---|
| `config.py` | `defaults`；函数内 `json` |
| `gen_index.py` | `kb_core`（FM_RE / parse_fm / strip_code_blocks / extract_headings） |
| `ingest.py` | `_env`、`kb_core`、`config`；**函数内**才 import `gen_index` |
| `lint.py` / `health.py` | `kb_core` + `config` |
| `recall.py` | `defaults`、`gen_index.content_hash`、`kb_core` |
| `assistant.py` | `_env`；`retriever` property 内才 import `recall.KbRetriever` |
| `cli.py` | 仅 `config.resolve_repo/load_config` 为模块级，其余全部命令函数内导入 |
| `channels/*` | `channel_base`、`.._env`、fastapi；`wecom_crypto` 可选 `Crypto.Cipher.AES` |

## 4. 主体内容

### 4.1 `kb_core.py` 承担的唯一事实源职责

| 类别 | 公开接口 |
|---|---|
| frontmatter | `FM_RE`、`parse_fm`、`split_fm`（仅支持扁平结构：标量 / inline list / block list，**不处理嵌套映射**） |
| 文本剥离 | `strip_code_blocks`（只剥围栏）、`strip_code`（再剥 inline code）、`extract_headings` |
| 归一四铁律 | `normalize_token`、`gh_slug`、`anchor_slug`、`_rel_no_ext` |
| 链接 | `iter_md_files`、`build_link_index`（返回 `by_rel / by_base / by_dir / files` 四表）、`resolve_wikilink`、`resolve_md_link`、`heading_exists` |
| 工具 | `sha256_text`、`is_vendored` |

归一规则：路径分隔符统一 `/`、小写、`_`↔`-`、全角/半角冒号→`-`、折叠连字符、中文保留。`anchor_slug` 采用双段比对（0.1.3 把真实库误报从 199 降到 24）。

### 4.2 各模块职责一览

| 模块 | 职责 | 主要公开接口 |
|---|---|---|
| `defaults.py` | 三层配置模型底层常量 | 排除目录、7 类默认词表、5 组别名、门槛默认值 |
| `config.py` | repo 定位 + TOML 合并 | `resolve_repo`、`load_config`、`load_vocab`、`derive_vocab_from_index`、`Config` |
| `gen_index.py` | 建索引 + 分类导航 | `collect`、`build_index`、`gen_category_md`、`gen_index` |
| `ingest.py` | 归一写入 | `ensure_fm`、`infer_metadata`、`normalize_basename`、`run_ingest` |
| `lint.py` | 三检与报告 | `lint_file`、`run_lint`、`load_ignore`、`collect_staged_md` |
| `health.py` | 0–100 健康分 | `compute`、`grade`、`render_html`、`run_health` |
| `recall.py` | BM25 + 链接图召回 | `KbRetriever`、`RecallHit`、`FreshnessReport`、`check_freshness` |
| `eval_recall.py` | 召回评估与报告 | `run_eval_cmd`、`summarize`、`_seed_queries_from_index`、`render_chart_svg` |
| `assistant.py` | 上下文组装 + LLM 问答 | `KbAssistant.answer / answer_stream`、`PROMPT_TMPL`、`build_context` |
| `telemetry.py` | 本地事件追加 | `record`、`summarize` |
| `cli.py` | 9 子命令 + 脚手架 | `TOML_TEMPLATE`、`GITIGNORE_LINES`、`_install_scaffold`、`build_parser` |

### 4.3 核心数据结构：`kb-index.json`（schema_version `1.1`）

顶层：`schema_version`、`generated_at`（带时区 ISO）、`source`、`doc_count`、`documents[]`、`category_index{类别→路径[]}`、`tag_index{标签→路径[]}`。

单文档字段（共 20 项）：`path / mtime_ns / size / content_hash / basename / title / description / categories / tags / difficulty / estimated_time / updated / version / word_count / headings / summary / body_text / body_text_clean / kind`。

- `content_hash` = `hashlib.blake2b(digest_size=16)`；`mtime_ns + size + hash` 三向比对支撑新鲜度检查。
- `body_text` 只剥围栏代码块（保留 inline code），`body_text_clean` 再剥 inline code；两变体服务不同环节。
- `kind` 默认 `doc`，`category-index.md` 强制 `generated-index`（召回采样与新鲜度检查会豁免它）。
- frontmatter 必填四项 `title / description / tags / difficulty`，`difficulty ∈ {beginner, intermediate, advanced}`；可选 `categories / estimated_time / created / updated / version / kind`。

实测：`tests/fixtures/kb/kb-index.json` 为 4 文档 / 1 分类 / 6 标签；`testkb/kb-index.json` 为 4 文档 / 3 分类 / 9 标签。二者结构同构但内容不同，导致评估报告逐条分数不一致。

### 4.4 其他产物 schema

| 产物 | 关键字段 |
|---|---|
| `lint-report.json` | `schema_version 1.0 / generated_at / checked_files / errors / warnings / ignored / issues_by_file` |
| `ingest-report.json` | `generated_at / dry_run / llm_calls / planned_files / plan[]`（action 类型 `rename`、`suggest-move`、重复报告） |
| `recall-eval-*.json` | `meta{top_k, min_score, min_score_per_term, link_gate, queries_source, index_freshness}` + `summary{count, hit_count, contextual_recall, contextual_recall_prod, mrr, avg_rank_of_hits, missed_queries}` + `per_query[]` |
| `health-report.json` | `llmwiki.health.v1`（meta / link / fresh 三分项 + 字母档） |
| `category-index.md` | frontmatter `kind: generated-index`、`categories: ['导航索引']`，按类别文档数降序列 `[[basename]]` |

### 4.5 包内数据资产

`src/llmwiki/data/`：`eval_queries.json`（内置 8 条 demo 评估集）、`scaffold/.pre-commit-config.yaml`、`scaffold/kb-lint.yml`、`templates/book-notes.md`、`templates/meeting-notes.md`。`llmwiki init` 把它们拷入用户库；`templates/` 在默认排除集内，**不进索引**。

## 5. 注意事项与常见误读

1. **架构文档原写「五层」实为六行表**，mermaid 曾引用不存在的 `_gen_query_index.py`；两处已于 2026-11-11 修正为「六层」与 `llmwiki index (gen_index.py)`，以本依赖图为准。
2. **无循环依赖是刻意设计**，不是偶然：新增模块时若在模块级反向 import 高层模块，会破坏 `cli` 的延迟导入隔离（尤其 `serve` 缺 fastapi 时应仍能用核心命令）。
3. **`ChannelAdapter` 并非强制抽象**：`channel_base.py` 导入了 `abstractmethod` 但没有任何 `@abstractmethod`，四个方法都有默认实现，基类可实例化；「契约」靠约定维持。
4. **`serve` 装配与 CLI 装配不对称**：`cli.cmd_query` 全量注入 cfg 的 LLM/recall/aliases/exclude 参数，`wechat_bridge.py:77` 只传 `KbAssistant(INDEX)`。这是当前最重要的架构级偏差（PR-04）。
5. `parse_fm` 只认扁平 frontmatter，写嵌套映射会被静默跳过；这是格式约束而非 bug。
6. `defaults.py` 的 `DEFAULT_MIN_SCORE = 0.15`、`DEFAULT_TOP_K = 6` **全仓无引用**（死常量），实际流通的 top_k 是 4；不要拿 6 当默认值。
7. 多个模块 docstring 引用 `docs/llmwiki-suite-design.md`，该文件在仓库中不存在。

## 6. 不确定 / 待补充项

- `wecom_crypto.AES` 依赖 `pycryptodome`，但 `pyproject.toml` 的 `serve` / `wechat` extras 均未声明；企业微信通道在干净安装下能否工作需要实测（PR-04）。
- `wecom_adapter.py:48,123` 使用绝对导入 `from wecom_crypto import ...`，异常被 `except Exception` 静默吞掉，推测会导致 `/wechat/callback` 恒返回 hint；未做运行时验证。
- 架构文档原写「16 字段文档」，与代码实际的 20 个字段不一致；该处已于 2026-11-11 修正为「20 字段」。
- `health.py:140-143` 跨文件锚点校验传入当前文件而非解析目标，疑似缺陷，待用例覆盖。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/*.py` 全体 | 模块级 import 声明、`__init__` / property 内延迟导入 |
| `src/llmwiki/kb_core.py` | :3-13 自述「唯一事实源」、四铁律、链接解析函数 |
| `src/llmwiki/gen_index.py` | `SCHEMA_VERSION="1.1"`、`collect` :88-152、`build_index` :156-172、`gen_category_md` |
| `src/llmwiki/config.py` | `Config` dataclass :74-97、`load_config` :100-166 |
| `src/llmwiki/channels/wechat_bridge.py` | :46-52 导入、:77 `KbAssistant(INDEX)`、:83-91 适配器装配 |
| `tests/fixtures/kb/kb-index.json`、`testkb/kb-index.json` | 真实字段与数值 |
| `src/llmwiki/data/` | scaffold、templates、eval_queries.json |
| `docs/llmwiki-architecture.md` | 用于对照其历史表述（六层 / 6 行、生成器名称；2026-11-11 已修正） |

## 8. 相关主题

- KB-02 核心业务流程与数据流（本篇是静态结构，那篇是动态流转）
- KB-04 配置三层模型与运行入口
- KB-07 通道与服务层及安全边界
- PR-04 已知偏差与待补充台账
