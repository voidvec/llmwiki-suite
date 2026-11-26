---
title: 质量保障体系与门禁
description: lint、eval、health 三套机制，召回基线门禁与 CI 阈值双口径
tags: ["质量", "lint", "eval", "CI"]
difficulty: intermediate
categories: ["知识库规范"]
kb_id: KB-06
legacy_kb_id: KB-07
kind: knowledge-base
status: derived
scope: lint / eval / health 三套机制、召回基线门禁、pytest 与 CI/pre-commit 矩阵、阈值双口径
audience: 维护者、贡献者、发布执行者
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 质量保障体系与门禁

> **定位**：区分「哪套机制会阻断、哪套只参考」，并给出所有门禁的真实阈值与触发点。项目把 lint/eval 视为一等公民，这篇是可执行的质量契约。

## 1. 背景

产品把「lint/eval 可观测性防漂移」列为差异化护城河（PR-01）。实际落地是三层：**阻断式 lint**、**参考式 health**、**回归式 eval 基线**，外层再由 pre-commit 与 GitHub Actions 包裹。但阈值存在双口径：代码 / CI 的 0.95/0.90 为执行口径、策略合同的 0.85/0.80 为历史计划口径（见 §4.6、口径基准 §0.3），引用时须标注区分。

## 2. 结论速览

| 机制 | 阻断？ | 判定 | 退出码 |
|---|---|---|---|
| `llmwiki lint` | ✅ 阻断 | `errors == 0` | 0 / 1 |
| `llmwiki eval` | ❌ 不判达标 | 只产出报告；缺集/缺索引报错 | 0 / 2 / 3 |
| `check_recall_baseline.py` | ✅ 阻断 | recall ≥0.95 且 MRR ≥0.90 | 0 / 1 / 2 |
| `llmwiki health` | ❌ 参考 | 0–100 分，不阻断 | 恒 0 |
| `pytest` | ✅ CI 阻断 | 53 个测试函数 | pytest 语义 |
| `python -m twine check dist/*` | ✅ CI 阻断 | 包元数据合法 | 构建语义 |

**公开基线实测**：8 条 query，全部 Top-1 命中，`contextual_recall@4 = 1.0`、`MRR@4 = 1.0`、`contextual_recall_prod = 1.0`、`missed_queries = []`。

## 3. 关键关系

```
用户笔记 .md
   ├─ lint（三检）────────────> lint-report.json ──> errors>0 阻断 pre-commit / CI
   ├─ health（三规则）─────────> health-report.{json,html} ──> 只展示
   └─ index ──> kb-index.json
                  └─ eval / check_recall_baseline ──> recall-eval-*.{json,md,svg}
                                     └─ 指标 <阈值 → exit 1 阻断

CI（4 个 Python 版本矩阵）：pytest → 基线回归 → build → twine check
pre-commit（本地）：check-yaml / whitespace / eof + kb-recall-baseline
用户库脚手架：llmwiki lint --staged（pre-commit）+ kb-lint.yml（每日 cron）
```

## 4. 主体内容

### 4.1 lint 三检（`lint.py`）

| 检查 | 级别 | 规则名 |
|---|---|---|
| 无 frontmatter（非 vendored） | error | `fm.missing` —— 并提前返回，不做链接细检 |
| 缺四项必填 `title/description/tags/difficulty` | error | `fm.required:<k>` |
| `difficulty` 不在枚举 | error | `fm.enum:difficulty` |
| `categories` 不在受控词表 | error | `fm.category`（**无词表时 warning 分支实际不可达**，因 `load_vocab` 永不返回 None） |
| wikilink 判死 | error | `link.wikilink.dead` |
| Markdown 链接判死 | error | `link.md.dead` |
| 锚点不存在 | warning | `link.anchor` |

链接判死复用 `kb_core` 的归一四铁律；外链跳过（交 lychee 等外部工具，lychee 不认 wikilink）；`.kb-lint-ignore.json` 用正则匹配 `"<rel> :: <detail>"` 隔离历史断链。`--staged` 取 `git diff --cached --name-only --diff-filter=ACMR`；`--sync-vocab` 把索引派生词表并入本次校验（不持久化）。

**索引外的目标不算断链**：索引是磁盘的**子集**（`[ingest].extra_exclude` 会把成篇文档排除出索引）。`.md` 目标在索引未命中时按磁盘存在性兜底，与「非 `.md` 目标按磁盘存在性判定」同口径；兜底用 `_exists_exact`（逐级 `listdir` 比对大小写、拒绝 `..` 逃逸、只认文件），因为 Windows / macOS 文件系统大小写不敏感，会让 `README.EN.md` 在本地「存在」、在 Linux CI 上不存在，同一提交两种结论。目录目标只由 `by_dir` 表判定：宽松口径算导航链接，`--strict-links` 下不认。

**vendored 判定**（`kb_core.is_vendored`）覆盖本地化变体：`README.md` / `CHANGELOG.md` / `CONTRIBUTING.md` / `LICENSE.md` / `SECURITY.md` / `CLAUDE.md` / `CODE_OF_CONDUCT.md` 及其 `.<lang>.md` 形式（`README.en.md`、`README.zh-CN.md`、`CHANGELOG.zh.md`，语言标记为两位字母或 `xx-YY`）。这些文件不参与 FM 校验、不计入 health 完整性分母、不注入召回；`readme-linux.md` 这类"名字像但实为笔记"的文件不受影响。

### 4.2 eval 四态退出码（`eval_recall.py`）

来源优先级：`--demo`（内置集，与你的库无关）→ `--seed`（从索引采样 ≤20 条，写入 `<repo>/eval_queries.json`）→ `--queries` / 默认 `<repo>/eval_queries.json`。

| 退出码 | 条件 | 设计意图 |
|---|---|---|
| 3 | 索引缺失，或 `--seed` 无索引 | **优先级最高**；0.1.4 起「索引判断优先」 |
| 2 | 无评估集（且无 `--demo`/`--seed`） | 提示 `llmwiki index` / `--seed`，**不产出报告、不给假分数** |
| 0 | 成功 | 落盘 `.md` + `.json`（`--chart` 另出 920×560 自包含 SVG） |

索引过期只告警并写进 `meta.index_freshness`，**不改变退出码**。0.1.3 曾「无集回退内置集」造成假 100%，0.1.4 明确取消。`meta.queries_source ∈ {repo, explicit, seed, demo-builtin}`；`queries_is_builtin` 保留为兼容字段。

### 4.3 health（`health.py`）

`WEIGHTS = {meta: 0.40, link: 0.40, fresh: 0.20}`，`FRESH_WINDOW_DAYS = 90`；meta 看 FM 四项齐全率 + 正文非空，link 判死口径对齐 lint，fresh 看 `updated/date/modified` 是否在 90 天内。字母档 A≥90 / B≥75 / C≥60 / D<60 / F（空库）。额外规则：**链接数 <5 时扣 2 分**。输出 `llmwiki.health.v1` JSON + 自包含 HTML，零依赖、离线、全匿名、不阻断。

### 4.4 召回基线门禁

`scripts/check_recall_baseline.py`：参数 `--repo / --queries / --demo / --recall(0.95) / --mrr(0.90) / --top-k / --min-score(0.15) / --out-dir / --tag / --json / --build`；断言快照 `summary.contextual_recall`、`summary.mrr`、`summary.missed_queries`；`--build` 时先 `run_ingest(apply=True)` 再重载配置。退出码 0 通过 / 1 跌破基线 / 2 运行出错。

调用点：
- **pre-commit**：`python scripts/check_recall_baseline.py --repo tests/fixtures/kb --build --out-dir .pre-commit-eval`（`always_run: true`）。
- **CI**：同一脚本 `--out-dir "$RUNNER_TEMP/recall-eval" --tag ci-baseline --demo`。
- **pytest**：`tests/test_recall_baseline.py` 用子进程跑 `init → ingest --apply → index`（不注入 `PYTHONPATH`，强制走已安装包，注释称「测试的就是发布的」），再断言 `RECALL_BASELINE=1.0` / `MRR_BASELINE=0.90`。

### 4.5 测试与 CI 矩阵

`tests/test_core.py` 50 个用例 + `tests/test_recall_baseline.py` 3 个 = **53 个测试函数**，13 个测试类。分组覆盖：分词、FM 解析、repo 解析、配置合并（含 categories 增量）、锚点 slug（8 例）、eval 无集四态、git mv、iLink 激活、`/api/*` 路由、SSE 事件序（7 例）。

`.github/workflows/ci.yml`：push/PR 到 `main`，matrix `3.11 / 3.12 / 3.13 / 3.14`，步骤 `checkout@v7 → setup-python@v7 → pip install . → pip install ".[wechat,dev]" → pytest → 基线回归 → build → twine check`。其中 `[wechat]` 是 CI 沿用的 0.1.5 前兼容别名，新写命令一律用 `[serve]`（口径基准 §0.3）。`.pre-commit-config.yaml` 另有 `check-yaml(--unsafe)` / `trailing-whitespace` / `end-of-file-fixer`，但 `exclude` 把所有 workflow YAML 排除在外。

用户库脚手架 `kb-lint.yml`：`cron "0 19 * * *"`（UTC，约北京次日 03:00）+ `workflow_dispatch` + push `**/*.md`，跑 `llmwiki lint` 并上传 `lint-report.json`。

### 4.6 阈值双口径（必须区分）

| 来源 | recall | MRR |
|---|---|---|
| 代码 / pre-commit / `ci.yml` / `docs/llmwiki-eval.md` / W36 周报 / HN 稿 | **0.95** | **0.90** |
| `scope-freeze.md` D3、`implementation-plan-dod` §2/§5/§6/§11、`roadmap-update` §6 | 0.85 | 0.80 |

`scope-freeze.md` 自己在 D3 行内加括号「（阈点 0.95/0.90）」承认差异。工作日志 `.workbuddy/memory/2026-08-31.md` 记录「门禁已挂 CI + pre-commit 双处，阈值严于合同」，并实测通过路径 EXIT=0、`--recall 2.0` 拦截 EXIT=1。**以代码为准：0.95/0.90**。

## 5. 注意事项与常见误读

1. **`eval` 本身不判达标**：CI 靠 `check_recall_baseline.py` 阻断，别把 `llmwiki eval` 退出码 0 当成质量合格。
2. **health 不能当门禁**：官方定性「健康度参考值，非质量标准」。
3. **`lint` 的 warning 不阻断**，只有 errors 才返回 1。
4. **两套阈值不要混引**：写周报/对外材料时用 0.95/0.90；引用策略合同原文时标明 0.85/0.80 是历史口径。
5. `python -m llmwiki.eval_recall` 恒返回 0（KB-04），**不能用于 CI**。
6. 基线用的是 `tests/fixtures/kb`（4 文档 / 1 分类）而非 `testkb`（4 文档 / 3 分类），两者逐条分数不同；比较报告时先确认库。
7. `testkb/eval_reports/` 与 `.pre-commit-eval/` 是历史快照，不能代表当前代码状态。

## 6. 不确定 / 待补充项

- 未实跑 `pytest` 与干净环境的 `pip install ".[wechat,dev]"`（沿用 CI 的兼容别名写法，等价于 `.[serve,dev]`）；CHANGELOG 0.1.5 记录「42 passed」，而当前测试文件含 53 个测试函数，两者差异未核实（可能是版本演进，也可能含参数化）。
- `httpx2` 与 `fastapi.testclient` 的模块别名兼容性可能导致 `TestApiRoutes` / `TestSseStream` 在干净环境失败（PR-04），需实测。
- `scaffold/kb-lint.yml` 含 `<you>` 占位符；`upload-artifact` 的 `lint-report.json` 是否稳定产出未验证。
- `docs/llmwiki-eval.md` 的「全部命令行选项」原漏 `--chart`、`tutorial-03` 的对比脚本原用错字段名，两处均于 2026-11-11 修正（PR-04 §1 修订记录）；`llmwiki-eval.md` 的章节编号重复仍需重排。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/lint.py` | `REQUIRED_FM` :36、`DIFFICULTY_ENUM` :37、`lint_file` :80-140、`run_lint` :143-208 |
| `src/llmwiki/eval_recall.py` | `run_eval_cmd` :328-461、`summarize` :113、`render_chart_svg` :198 |
| `src/llmwiki/health.py` | `WEIGHTS` / `FRESH_WINDOW_DAYS` / `compute` :79-190 |
| `scripts/check_recall_baseline.py` | 默认 0.95/0.90、退出码 0/1/2 |
| `tests/test_core.py` / `tests/test_recall_baseline.py` | 用例分组与基线断言 |
| `.pre-commit-config.yaml` / `.github/workflows/ci.yml` | hook 与 4 版本矩阵 |
| `src/llmwiki/data/scaffold/kb-lint.yml` | cron 与 lint 步骤 |
| `docs/llmwiki-eval-report-v1.md` / `testkb/eval_reports/*.json` | 8 条 query、1.0/1.0、逐条分数 |
| `docs/scope-freeze.md` D3 / `implementation-plan-dod-*.md` | 0.85/0.80 历史口径 |
| `.workbuddy/memory/2026-08-31.md` | 「阈值严于合同」与实测 EXIT 记录 |

## 8. 相关主题

- KB-05 检索与召回算法口径
- KB-04 配置三层模型与运行入口
- PR-02 打包分发与发布运维
- PR-04 已知偏差与待补充台账
