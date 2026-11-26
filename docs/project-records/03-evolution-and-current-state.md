---
title: 演进历程与当前项目状态
description: 0.1.0 至 0.1.8 版本时间线、L0 到 L3 路线与项目现状快照
tags: ["演进", "版本", "现状"]
difficulty: beginner
categories: ["参考手册"]
record_id: PR-03
legacy_kb_id: KB-11
kind: project-record
status: derived
scope: 版本时间线、能力演进（L0→L3）、Q4 九周计划、观测数据对计划的验证、当前真实状态与仓库内无记录项（截至 2026-11-11）
audience: 主理人、接手者、做「还能不能按原计划推进」判断的人
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
relocated: 2026-11-12 方案 C · knowledge-base/ → docs/project-records/
confidence: medium
---

# 演进历程与当前项目状态

> **归档状态（2026-11-12）**：按方案 C 从 `knowledge-base/` 迁至 `docs/project-records/`，属**项目记录 · 现状时间线 / 状态快照**，不是知识层文档。正文记录 2026-11-11 时点状态，未改写；编号已于 2026-11-12 重排为 `PR-03`（旧 `KB-11`），全仓引用已同步更新，映射见 [README.md](README.md) §2。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 为准，权威口径见 [00-canonical-baseline.md](00-canonical-baseline.md)。


> **定位**：把「计划说要做什么」和「仓库里实际留下了什么」放在一起对照。结论可能不好看，但这是继续投入前最需要的判断依据。

## 1. 背景

项目 2026-08-24 前后完成套件化，8 天内密集发版；2026-08-31 产出 Q4 九周防漂移执行契约（`scope-freeze` / `implementation-plan-dod` / `roadmap-update`），计划 W1–W9（2026-08-31 → 2026-11-02）以海外发布与观测收口。此后 `stats/` 每日快照持续到 2026-11-25，2026-11-11 建立 `knowledge-base/` 共 14 篇派生文档；**工程侧停滞 87 天（2026-08-31 → 2026-11-25），2026-11-26 以 `0.1.7` 恢复**（完整时间线见 §4.5、口径基准 §0.2）。

## 2. 结论速览

- **代码侧 2026-08-31 定格于 `0.1.6`，停滞 87 天后于 2026-11-26 连发 `0.1.7` / `0.1.8`**：0.1.7 含严格链接口径、CommonMark 围栏修正、检索章节稀有度加权、`gh_slug` 对齐、health 完整性分母修正；0.1.8 修「索引外文件的 md 链接被判死」与「双语仓库 `README.<lang>.md` 被判缺 frontmatter」。`[Unreleased]` 已清空，`pyproject.toml` / `__init__.py` / PyPI / Release 均为 0.1.8。
- **工程能力基本完整**：9 命令、BM25+wikilink 召回、lint/eval/health、4 通道、WebUI/Dashboard、SSE、CI/pre-commit 门禁、PyPI 发布链均已落地。
- **产品化计划仍大面积未落地**：HN 发布（计划 2026-09-22）、W37–W44 周报、`docs/cr/`、发布响应台账、pivot / 止损决策、范围冻结签署，仓库内仍无记录（原计划 W4 的 `v0.1.7` 已于 2026-11-26 延期落地，但无配套发布动作）。
- **观测数据连续 85 天为零外部信号**：stars / forks / open_issues / open_prs 全程 0，`version` 恒为 `v0.1.6`（快照取自 GitHub Release），PyPI 月滚动下载从 569 峰值 696 回落并稳定在 94。
- 按 `stats/` 数据，**止损触发条件成立**（star<20 且无外部 PR 且重试 2 次无效果），但 pivot / 止损决策仓库内无记录。

## 3. 关键关系：计划 vs 证据

```
计划（2026-08-31 契约）
  W1 范围冻结 ──> W2 观测就绪 ──> W3 物料完成 ──> W4 发布 v0.1.7 + HN
  ──> W6 首数据窗口 ──> W8 L1 观测 ──> W9 收口 / pivot
                    │
证据（仓库内）      ├─ ✅ D1 健康分、D2 埋点、D3 召回门禁、D4 曝光监控、D7 eval 报告、D12 首周报
                    ├─ 🔄 D5 README-EN（文件在，但人工终审记录缺失）、D6 HN 物料（草稿在）
                    └─ 仓库内无记录：D8 发布执行、D9/D10/D11 落地文件、W37–W44 周报、v0.1.7、pivot（定义差异见 PR-04 P2-2，属已知问题 / 待办）
```

## 4. 主体内容

### 4.1 版本时间线（`CHANGELOG.md`，Keep a Changelog 1.1.0 + SemVer）

| 版本 | 日期 | 关键内容 |
|---|---|---|
| 0.1.0 | 2026-08-24 | 套件化：`serve` 子命令、`channels` 包、6 篇文档；检索改进 P1 别名组 / R1 每词阈值 / R2 覆盖度 ramp / R3 缓存 ~170× / P3 索引过期 / P4 via_link 门槛 / top_k 收紧 4 |
| 0.1.1 | 2026-08-25 | 15 单测 + 3 召回基线、`check_recall_baseline.py`（0/1/2）、`ci.yml` / `release.yml`、CI/Release 徽章、PyPI 指南 |
| （0.1.2） | — | **正文无版本段**，仅文末 compare 链接 |
| 0.1.3 | 2026-08-26 | categories 增量语义、`categories-sync`、`lint --sync-vocab`、eval 双兜底、锚点双段比对（误报 199→24）、qrcode 入 `[serve]`、Py3.14 CI |
| 0.1.4 | 2026-08-27 | `eval --seed` / `--demo`、`queries_source`、**取消内置集自动回退**（避免假 100%）、退出码 2/3 与索引优先、**否决 init 生成 T0 种子** |
| 0.1.5 | 2026-08-27 | 仓库门面化（banner / README.en / CONTRIBUTING / SECURITY / Issue 模板 / pre-commit）、`eval --chart` SVG、飞书 + Telegram 适配器、进化路线图、**`/webui/chat`（P0）/ `/dashboard`（P1）/ `/dashboard/status`**、extras `[wechat]`→`[serve]`（保留别名） |
| 0.1.6 | 2026-08-31 | **`/api/*` 正式路由**（`/api/chat`、`/api/recall`，旧路径保留别名）、**SSE 流式** `meta→candidates→delta*→done`、WebUI 打字机 + 停止按钮、prompt 加多自然段约束 |
| 0.1.7 | 2026-11-26 | **`lint --strict-links`** 严格链接口径、CommonMark 围栏与行内码解析修正、检索章节按标题稀有度加权 + 上下文剥离 frontmatter/`<cite>`、`gh_slug` 对齐 GitHub、health 完整性分母剔除 vendored、BM25 排除 `kind: nav-index` 导航页 |
| 0.1.8 | 2026-11-26 | **索引外文件的 Markdown 链接不再判死**（`_exists_exact` 逐级 `listdir` 大小写严格比对 + 拒绝 `..` 逃逸，.md 与非 .md 两类目标统一口径）、`is_vendored` 认 `README.<lang>.md` 等本地化变体 |
| [Unreleased] | — | 空 |

> 「8 天 7 版」与正文 6 段（0.1.2 无正文、0.1.4 与 0.1.5 同日）属统计口径差异，归类为已知问题 / 待办，引用时须带口径说明。

### 4.2 能力演进路线（L0→L3）

`docs/llmwiki-evolution-roadmap.md`：

- **L0 固化（已完成）**：里程碑 `recall@4 = 100%`，即现有编译管线。
- **L1 增量记忆与回放**：计划新增 `kb-memory.json` / `kb-suggestions.md` / `kb-evolution-log.md` 与 `observe / nightly / suggest / evolve` 四命令；scope-freeze 把本期收窄为 `observe + suggest` 两命令精简版。**这些文件与命令在 `src/llmwiki/` 中仓库内无记录**（截至 2026-11-11）。
- **L2 主动学习与建议**：本期不做详细设计。
- **L3 自主进化**：「自动写 + 自动验证 + 人审」三段式，任何一步不通过不落地，eval 回退自动回滚；本期不实现。

策略文档把 L1=转化引擎、L2=留存引擎、L3=忠诚引擎；这是**产品假设**，无数据验证。

### 4.3 Q4 九周计划（W1–W9，2026-08-31 → 2026-11-02）

`scope-freeze.md` §1 的 D1–D12：健康分 MVP、最简埋点 3 事件、召回 CI 门禁、曝光监控、README-EN v1、HN 主帖 + 对比帖、eval 公开报告 v1、发布执行单、L1 observe 事件流设计、首轮外部反馈实施、公开 eval 基准页 v1、周报制度。

四条已拍板决策：海外优先、**W4 发布日打 `v0.1.7`**、固定「周二 PT」、W9 止损线。变更控制 C0/C1/C2、M0–M6 里程碑、Phase 2 承诺清单 Q1–Q10（健康分 Pro、全链路漏斗、README 中文版、PH/Reddit、iLink 前置、L1 nightly、回流闭环、L2 蓝图、留存体系、工程打磨）。

**落地核对**：

| 交付 | 状态 | 证据 |
|---|---|---|
| D1 健康分 MVP | ✅ | `health.py`、`docs/llmwiki-health.md` |
| D2 最简埋点 3 事件 | ✅ | `telemetry.py` 的 `cli-run / eval-run / health-run` |
| D3 召回 CI 门禁 | ✅ | `check_recall_baseline.py` + pre-commit + `ci.yml` |
| D4 曝光监控 | ✅ | `obs-daily.yml` + 85 份 `stats/` 快照（W36 周报当时标「进行中」，已过时） |
| D7 eval 公开报告 v1 | ✅ | `docs/llmwiki-eval-report-v1.md` |
| D12 周报制度 | ⚠️ 仅 1 份 | `docs/weekly/2026-W36.md`；W37–W44 周报仓库内无记录，DoD「9 份缺 ≤1」为硬性纪律（已知问题 / 待办） |
| D5 README-EN | ⚠️ 文件在 | `README.en.md` 完整，但 W36 记录「人工终审未执行（LLM 产物必须人审）」 |
| D6 HN 物料 | ⚠️ 草稿在 | `hn-post-draft.md` / `llmwiki-vs-rag-comparison.md`；HN 发布（计划 2026-09-22）仓库内无记录 |
| D8 发布执行 / `v0.1.7` | ⚠️ 延期落地 | 原定 W4（09-22），实际 2026-11-26 发布（tag + PyPI + Release）；配套的 HN 主帖、发布响应台账仍仓库内无记录；`dist/` 停在 0.1.3（陈旧产物为已知问题 PR-04 P4-6） |
| D9/D10/D11 | 仓库内无落地记录 | 两份计划定义本身不同（PR-04 P2-2，已知问题 / 待办），仓库内无落地文件 |
| CR 目录 / 发布响应台账 | 仓库内无记录 | `docs/cr/`、`docs/release-response-ledger.md` 仓库内无记录（PR-04 P3-1 / P3-2） |

### 4.4 观测数据对计划的验证（2026-09-01 → 11-25）

| 计划指标 | 实际 | 判定 |
|---|---|---|
| Wave1 star 0→20–100、issue/PR ≥5 | 全程 0 / 0 | ❌ 未达 |
| W9 硬性验收「外部 issue/PR ≥3 且采纳率 ≥30%」 | 0 / 未采集 | ❌ 未达 |
| PyPI 月下载较 475 提升即算 | 569 → 峰值 696(09-23) → 94(10-06 起) | ❌ 回落；「475 属一次性验证流量」被证实 |
| W4（09-22）发 `v0.1.7` + HN 主帖 | 发布延期至 2026-11-26（`version` 在快照中恒 v0.1.6，`latest_release_at` 恒 2026-08-31）；HN 主帖 | ⚠️ 版本已发，主帖仍无记录 |
| 周复盘 9 份 / 9 周 | 1 份 | ❌ 未达 |
| W9 pivot 决策 | 按 `stats/` 数据触发条件成立（star<20、无外部 PR、零信号持续 66 天） | 决策仓库内无记录 |

`docs/weekly/2026-W36.md`（唯一周报，2026-09-01）记录：D1/D2/D3/D7/D12 完成、D4/D5/D6 进行中、外部信号 0 star / PyPI 94·569、4 项 DoD 未达、W2 三个 Top 待办，并预告「2026-09-08 W2 周报」——该文件仓库内无记录。

### 4.5 最新进展时间线（截至 2026-11-11）

| 日期 | 仓库内证据 | 说明 |
|---|---|---|
| 2026-08-31 | 0.1.6 发布；`scope-freeze` / `implementation-plan-dod` / `roadmap-update` 三份交付物 | 此后工程侧停滞 87 天 |
| 2026-09-01 | `docs/weekly/2026-W36.md`（唯一周报，W1）；`stats/` 首份快照 | 计划 W1 |
| 2026-09-02 | `docs/hn-account-growth.md` 养号计划 K=1 重排 | 文件 AuthorDate，非提交日 |
| 2026-09-05 ~ 11-25 | 逐日 `obs(daily): 曝光快照` 提交、`stats/` 85 份快照 | 唯一持续的仓库活动 |
| 2026-11-07 | 回填提交 `c57c718`（CommitDate 12:00），仅改 `docs/hn-account-growth.md` | 当时为 HEAD；不是养号执行记录 |
| 2026-11-11 | 新建 `knowledge-base/` 14 篇；全仓口径统一 | 口径基准 v1 建立 |
| 2026-11-12 | 方案 C 重排：知识层 8 篇 + 项目记录 6 篇，编号 `KB-*` / `PR-*` 分离 | 仅文档结构，无代码变更 |
| 2026-11-26 | 6 个功能 / 修复提交 + `release: 0.1.7`；tag 触发 `release.yml`，PyPI 与 GitHub Release 同日发布 | 工程侧恢复；HN 主帖等仍无记录 |

> HN 发布（09-22）、W37–W44 周报、`docs/cr/`、发布响应台账、W9 pivot/止损决策、范围冻结签署，仓库内仍无记录；不排除在仓库外发生。原计划 W4 的 `v0.1.7` 已延期落地。权威时间线见口径基准 §0.2。

## 5. 注意事项与常见误读

1. **不要把「有文档」当「已交付」**：`release-plan.md`、`hn-account-growth.md`、`llmwiki-evolution-roadmap.md` 都是计划/设计稿，不是执行记录。
2. **`stats/` 的存在不等于计划成功**：它恰好证明了 D4 落地，同时否证了几乎所有外部增长目标。
3. **W36 周报的 D4「进行中」已过时**：`obs-daily.yml` 与 85 份快照都在，读周报要按日期打折。
4. **不要按 CHANGELOG 推断 PyPI 现状**：仓库内 `dist/` 是 0.1.3、egg-info 是 0.1.5、pyproject 是 0.1.7、stats 是 v0.1.6；多套版本号并存（PR-02），PyPI 现状须直接查元数据。
5. **止损线不是失败结论**：它只是决策触发条件；是否 pivot、转向哪个方向仓库内无记录，需主理人判断。

## 6. 不确定 / 待补充项

- 未联网核验外部 star / 下载量走势；本文趋势结论时间锚点为截至 2026-11-25，仅覆盖仓库内证据（11-11/11-12 文档结构变更、11-26 `0.1.7` 发布已计入）。版本事实已于 2026-11-26 定点核验（PyPI 元数据 + GitHub Release）。
- HN 养号（karma 1→+49、09-17 终检≥50）、09-22 主帖、发布后 48h 复盘是否发生，**仓库内无任何记录**，可能在仓库外发生（如论坛、邮件），不能断言绝对未执行。
- `scope-freeze.md` 签署栏空白，仓库内无签署记录；九周计划是否正式启动 / 终止仓库内无决策记录（PR-04 P3-6）。
- 「Phase 2 Q1–Q10」只是承诺清单，无排期与负责人；`docs/llmwiki-eval-report-v1.md` 把语义召回错标为 Q10（实际 Q1 才是健康分 Pro），需统一编号。
- 若继续推进，优先补齐的决策：是否 pivot、是否补 v0.1.7、是否重启周报与 CR 机制、是否清理陈旧 `dist/` 与版本号。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `CHANGELOG.md` | 0.1.0–0.1.7 七段 + 空 [Unreleased]、0.1.2 缺正文 |
| `pyproject.toml` / `src/llmwiki/__init__.py` | `0.1.7` |
| `docs/llmwiki-evolution-roadmap.md` | L0→L3 分层、新文件与四命令、验收标准 |
| `docs/scope-freeze.md` | D1–D12、四条决策、W9 止损线、签署状态 |
| `deliverables/product-strategy/implementation-plan-dod-llmwiki-2026-08-31.md` | DoD、M0–M6、W9 指标总表、Phase 2 Q1–Q10 |
| `deliverables/product-strategy/roadmap-update-llmwiki-2026-08-31.md` | Wave 1/2/3、KPI、风险登记、475 下载基数 |
| `docs/weekly/2026-W36.md` | 唯一周报的进度与 4 项未达 |
| `stats/daily-series.csv` + 66 个 JSON | 66 天零信号、version 恒定、下载趋势、缺 09-02 |
| `dist/`、`src/llmwiki_suite.egg-info/PKG-INFO` | 版本漂移证据 |

## 8. 相关主题

- PR-01 项目定位、业务背景与边界
- PR-02 打包分发、发布流程与运维观测
- KB-08 业务规则与边界约束清单
- PR-04 已知偏差与待补充台账
