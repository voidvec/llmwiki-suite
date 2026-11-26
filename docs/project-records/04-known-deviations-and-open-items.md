---
title: 已知偏差与待补充台账
description: P0 到 P4 已知偏差、代码与文档不一致及待补充项台账
tags: ["审计", "偏差", "待办"]
difficulty: advanced
categories: ["知识库规范"]
record_id: PR-04
legacy_kb_id: KB-12
kind: project-record
status: derived
scope: 代码↔文档、计划↔现状的已知问题/待办台账：潜在故障点（含待验证/推测）、仓库内无记录的产物，按优先级排列
audience: 主理人、审计者、准备修 bug 或做一致性收敛的工程师
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
relocated: 2026-11-12 方案 C · knowledge-base/ → docs/project-records/
confidence: medium
---

# 已知偏差与待补充台账

> **归档状态（2026-11-12）**：按方案 C 从 `knowledge-base/` 迁至 `docs/project-records/`，属**项目记录 · 偏差与待办台账**，不是知识层文档。正文记录 2026-11-11 时点状态，未改写；编号已于 2026-11-12 重排为 `PR-04`（旧 `KB-12`），全仓引用已同步更新，映射见 [README.md](README.md) §2。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 为准，权威口径见 [00-canonical-baseline.md](00-canonical-baseline.md)。


> **定位**：这是全篇最有行动价值的一篇。逐条给出**现象、位置、依据、影响、建议**；凡未做运行时验证的，一律标注「推测 / 待验证」，不写成定论。

## 1. 背景与取证边界

三路盘点（文档 / 源码 / 配置运行数据）交叉核对后，发现偏差集中在三类：① 8 月底密集迭代后文档未同步；② 计划文档（08-31 产出）与仓库现实脱节；③ 部分实现存在静默降级，文档按「已可用」描述。

**已亲自复核的事实**（区别于推测）：`ingest.py:416-419` 确实自动重建索引；`wecom_adapter.py:48,123` 确实为绝对导入；`wechat_bridge.py:77` 确实只传 `INDEX`；`eval_recall.main()` 确实 `return 0`；`pyproject.toml` 确实写 `httpx2>=2.0`，且本地 `.venv` 确实装有 **httpx2 2.12.0**（pydantic 发布的真实包，非笔误），但普通 `import httpx` 在该环境失败；生成时工作区 `git status --short` 为空，2026-11-11 修订时工作区含未跟踪的 `knowledge-base/` 及本轮对原有文档的克制修正。

### 2026-11-11 口径统一与修订记录

> 本轮按当时的权威口径基准完成全仓口径统一。下表区分「已定点修正」「部分修正」「如实保留」三类，避免把修订前的核对结论误读为当前缺陷清单。

| 处置 | 条目 | 说明 |
|---|---|---|
| ✅ 已修正 | P1-2 | `README.md` 命令表补 `llmwiki health`；`docs/llmwiki-local-verify.md` 改「CLI 9 命令」 |
| ✅ 已修正 | P1-4 | `tutorial-03` 对比脚本 `summary['recall']` → `summary['contextual_recall']`（`mrr` 是真实字段，保留） |
| ✅ 已修正 | P1-5 | `docs/llmwiki-eval.md` §2 补 `--chart` 行 |
| ✅ 已修正 | P1-7 | `README.en.md` 回调路径 `/wecom/*` → `/wechat/callback` |
| ✅ 已修正 | P1-12 | `docs/llmwiki-architecture.md`「五层」→「六层」、「16 字段」→「20 字段」 |
| ✅ 已修正 | P3-9 / 补充段落 | `discussion-welcome-post.md` 图片路径改为 `../../assets/`；教程错别字 `llmmwiki index`、「离」、「飞到回调」；`eval-seed-design.md` 失效 wikilink、零宽空格 `u200b`、错别字 |
| ✅ 已修正 | 补充段落·章节编号 | `docs/hn-launch-timing.md` 末章 `## 4.` → `## 5.` |
| ◐ 部分修正 | P1-3 | 文档侧两处「整体替换」→「增量追加」已改；`cli.TOML_TEMPLATE` / `config.py` docstring / `testkb/llmwiki.toml` 注释属代码与配置，不在文档修订范围 |
| ◐ 部分修正 | P1-10 | 7 处文档的 `[wechat]` → `[serve]` 已改；`ci.yml`、`cli.py` help 中的旧名属代码 / 工作流，保留兼容 |
| ◐ 部分修正 | P1-11 | 架构文档 mermaid 的 `_gen_query_index.py` → `llmwiki index (gen_index.py)` 已改；源码 docstring 引用不在范围 |
| ◐ 部分修正 | P2-14 | `eval-seed-design.md` 的 wikilink / 零宽空格 / 错别字已改；正文否决 T0 与 mermaid 仍画 T0 的历史口径差异保留 |
| ⏸ 如实保留 | P0-1 ~ P0-8 | 实现层潜在故障，需干净环境实跑验证；未经实跑一律标「待验证 / 推测」 |
| ⏸ 如实保留 | P1-1 / P1-8 / P1-9 / P2-7 | 需重写措辞体系或改代码，克制修订不覆盖 |
| ⏸ 如实保留 | P2-1 ~ P2-6、P2-8 ~ P2-13 | 历史计划文档之间的口径差异，靠状态标注头解决，不改写历史记录 |
| ⏸ 如实保留 | P3-1 ~ P3-8、P4 | 仓库内无记录的产物与待验证 / 待决策项 |

> 下表 P1 / P2 / P3 原有条目编号不变，「现象」列描述的是 2026-11-11 修订**之前**的核对结果，作为历史核对痕迹保留；当前状态以本表为准。

---

## 2. 结论速览与关键关系

| 优先级 | 类别 | 条数 | 一句话 |
|---|---|---|---|
| **P0** | 可能导致功能不可用 | 8 | 集中在 serve 装配、可选依赖与 CI 可安装性 |
| **P1** | 代码 ↔ 文档不一致 | 12 | 多为 0.1.3–0.1.6 迭代后未同步文档 |
| **P2** | 文档 ↔ 文档不一致 | 14 | 计划体系自身口径冲突 |
| **P3** | 缺失产物 / 未落地约定 | 9 | 计划要求的文件仓库内无记录 |
| **P4** | 待验证 / 待决策 | 6 | 需实跑或主理人拍板 |

偏差的来源链路（三类根因 → 四类后果）：

```
根因 A：08-24~08-31 密集迭代 ──> 文档/TOML 模板/注释未同步 ──> P1
根因 B：08-31 计划文档与仓库现实脱节 ──> 口径冲突、缺失产物 ──> P2 + P3
根因 C：实现里大量静默降级 ──> 文档按「已可用」描述 ──> P0
                                    └─> 未被运行时验证的推测 ──> P4
```

P0 与 P1 的修复互不依赖；P2/P3 属计划体系的历史口径差异与已知问题 / 待办，建议在 P0 坐实后统一处理（2026-11-11 已完成文档侧定点修正，见 §1 修订记录）。

## 3. P0：潜在功能故障（建议优先实测）

> 除已标注「推测 / 待验证」者外，本节均为静态推断；未经实跑的一律按「待验证 / 推测」处理（截至 2026-11-11）。

| # | 现象 | 位置 / 依据 | 影响 | 建议 |
|---|---|---|---|---|
| P0-1 | `serve` 下 TOML 配置失效 | `wechat_bridge.py:77` `assistant = KbAssistant(INDEX)`；对比 `cli.py:181-189` 全量注入 | `[llm] / [recall] / [aliases] / [ingest].extra_exclude` 在网页与 IM 问答全部失效，检索走默认值 | 改为 `load_config(resolve_repo(None))` 后全量注入；补集成测试 |
| P0-2 | 企业微信适配器绝对导入 | `wecom_adapter.py:48,123` `from wecom_crypto import ...`，异常被 `except Exception` 静默吞掉 | 推测 `_crypt()` 恒 None → `/wechat/callback` 只返回 hint，企微通道不可用 | 改 `from .wecom_crypto import ...`；加运行时冒烟 |
| P0-3 | `pycryptodome` 未声明 | `wecom_crypto.py:24` `try: from Crypto.Cipher import AES`；`pyproject.toml` extras 无此项 | 干净安装 `[serve]` 后企微加解密抛 `RuntimeError` | 加入 `[serve]` 或明确文档化可选依赖 |
| P0-4 | `httpx2` 与 `httpx` 模块别名 | `pyproject.toml:32,39` `httpx2>=2.0`；本地 `.venv` 装 2.12.0，其 `_alias.py` 需显式 `alias_httpx()` 才注册 `httpx`；`fastapi.testclient` 经 starlette 依赖 `httpx` | **待验证**：干净环境 `pip install ".[wechat,dev]"` 后 `TestApiRoutes` / `TestSseStream` 可能因 `ModuleNotFoundError: httpx` 失败 | 在干净 venv 实跑 pytest；必要时改为 `httpx>=...` 或显式声明兼容层 |
| P0-5 | `eval_recall.main()` 吞退出码 | `eval_recall.py:492-497` 调用 `run_eval_cmd` 后恒 `return 0` | `python -m llmwiki.eval_recall` 丢失 2/3，破坏 CI 阻断 | `return run_eval_cmd(...)` |
| P0-6 | 脚手架 CI 含占位符 | `src/llmwiki/data/scaffold/kb-lint.yml:22` 与 `testkb/.github/workflows/kb-lint.yml:22`：`git+https://github.com/<you>/llmwiki-suite.git` | `llmwiki init` 拷给用户后 CI 必失败 | 改为 `pip install llmwiki-suite` 或可配置仓库地址 |
| P0-7 | 飞书签名算法疑似自造 | `feishu_adapter._verify_signature` 从 body `header.signature` 取签名、`"".join(sorted([...]))` + HMAC-SHA256；`smoke_feishu_telegram.py` 只验证自洽 | 与飞书官方（HTTP header 传签名）可能不互通 | 对照官方文档重构并用真实事件验证 |
| P0-8 | `health` 跨文件锚点传错 | `health.py:140-143` 忽略 `resolve_md_link` 返回的 `_res`，用当前文件 `rel` 校验标题（`lint.py:136-139` 正确） | `[x](other.md#anchor)` 误报 | 改用 `_res` 并补测试 |

## 4. P1：代码 ↔ 文档不一致

> 状态：P1-2 / P1-4 / P1-5 / P1-7 / P1-12 已于 2026-11-11 定点修正，P1-3 / P1-10 / P1-11 部分修正。下表保留修订前的核对记录，最新状态见 §1 修订记录。

| # | 现象 | 依据 |
|---|---|---|
| P1-1 | 「索引不自动刷新」不完整：`ingest --apply` 会重建；`hn-post-draft.md` / `llmwiki-vs-rag-comparison.md` 还把 ingest 说成含 link lint | `ingest.py:416-419` vs `getting-started.md` 铁律 1、`tutorial-01` §3.2 |
| P1-2 | ✅ 已修正：README.md 命令表原有 8 条缺 `health`（README.en 有 9 条）；`local-verify.md` 原写「CLI 8 命令」 | `cli.py:213/422`；CLI 子命令共 9 个 |
| P1-3 | ◐ 部分修正：`tutorial-01` 文档侧两处已改为「增量追加」；`cli.TOML_TEMPLATE` / `config.py` docstring / `testkb/llmwiki.toml` 注释仍写「整体替换语义」，实际增量追加（`replace_default=true` 才替换） | `cli.py:40` TOML_TEMPLATE、`config.py:13` docstring、`testkb/llmwiki.toml:12`、`tutorial-01` §2.3 |
| P1-4 | ✅ 已修正：`tutorial-03` 对比脚本原用 `summary['recall']`，已改为 `summary['contextual_recall']`（`mrr` 是真实字段，保留） | 快照 JSON、`docs/llmwiki-eval.md` §4.1 |
| P1-5 | ✅ 已修正：`docs/llmwiki-eval.md` §2「全部选项」原漏 `--chart`，已补 | `cli.py:417`、CHANGELOG 0.1.5 |
| P1-6 | 门禁阈值双口径：代码/CI/pre-commit 0.95/0.90 为执行口径，策略合同 0.85/0.80 为历史计划口径（须标注区分，KB-06 §4.6） | `check_recall_baseline.py:55-57` vs `scope-freeze.md` D3、DoD §2 |
| P1-7 | ✅ 已修正：`README.en.md` 原写回调含 `/wecom/*`，已改为 `/wechat/callback` | `wecom_adapter.py:55,68` |
| P1-8 | 文档称 `.ilink_session.json` / `.obsidian/` 已加 `.gitignore`，实际没有 | 根 `.gitignore`、`cli.GITIGNORE_LINES`（仅 6 项） |
| P1-9 | 通道 env 是否需重启自相矛盾（§1 说热启停、§4 与 tutorial-02 说重启） | `channel-verify.md`；企微凭证确实模块级冻结，飞书/Telegram 运行时读 |
| P1-10 | ◐ 部分修正：`pypi-release-guide` / `tutorial-02` / `RELEASE` / `feature_request.yml` / README 双版的 `[wechat]` 旧名已统一为 `[serve]`；`ci.yml` 与 `cli.py` serve help 保留兼容别名 | CHANGELOG 0.1.5 已更名 `[serve]`，别名保留 |
| P1-11 | ◐ 部分修正：架构文档 mermaid 的 `_gen_query_index.py` 已改为 `llmwiki index (gen_index.py)`；源码 docstring 引用不存在的 `docs/llmwiki-suite-design.md`、`eval_recall.py` 写 `max_chapters=6`（实际 4）仍保留 | 源码注释与 `docs/` 目录 |
| P1-12 | ✅ 已修正：`llmwiki-architecture.md`「五层职责」→「六层」、「16 字段文档」→「20 字段」 | `llmwiki-architecture.md` vs `gen_index.collect` |

## 5. P2：文档 ↔ 文档不一致（计划体系）

| # | 冲突 | 双方 |
|---|---|---|
| P2-1 | 「不做中文物料、README 只英文、iLink 后置 Wave 3」 | `scope-freeze.md` §2 vs 中文 README / 3 篇中文教程 / iLink 为默认通道 |
| P2-2 | **D9/D10/D11 三套定义** | `scope-freeze.md` §1（事件流设计 / 外部反馈实施 / 公开 eval 基准页）vs DoD §2（反馈机制 / observe+suggest 两命令 / telemetry 复盘）vs `roadmap-update` §9.1（逐周排布第三套） |
| P2-3 | D4 是否完成 | DoD §2 已打勾、scope-freeze ✅ vs W36 周报 🔄「每日自动跑待接定时」 |
| P2-4 | W36 下载数 569/94 与「约 287」自相矛盾；策略文档另用 475 基数 | `docs/weekly/2026-W36.md` vs `stats/llmwiki-obs-2026-09-01.json` vs `roadmap-update` |
| P2-5 | HN 标题 <80 字符 / 78 字符 A1 / Tuesday evening PT vs <70 字符 / 周二 06:00-09:00 PT | `hn-post-draft.md` vs `hn-launch-timing.md` / `release-plan.md` |
| P2-6 | 对比帖「是否改为次日」仍标待拍板 | `hn-launch-timing.md` §5 结论（原 §4，2026-11-11 重编号）vs 已明确的 `release-plan.md` |
| P2-7 | 语义召回被错标 Phase 2（Q10），Q1 才是健康分 Pro | `llmwiki-eval-report-v1.md` §5 vs DoD §10.1 |
| P2-8 | 里程碑编号两套（S2 M6 后半 vs M0–M6） | `RELEASE.md` vs DoD §6 |
| P2-9 | 周复盘「周日 / 周二 / 周四 / 周五」四种说法 | weekly 模板、DoD、release-plan、W36 |
| P2-10 | 密钥「进 `.env`」vs「套件不读 `.env`」 | DoD §11 vs `SECURITY.md` / `config.py:8` |
| P2-11 | D9 issue 模板「Bug/Feature/打赏三型 + 48h 响应承诺」 | DoD §2 vs 实际 `docs_usage.yml` + CONTRIBUTING 无承诺（48h 只在 SECURITY） |
| P2-12 | Wave 编号 1/2/3 vs 0/1/2 | `roadmap-update` TL;DR vs §5 |
| P2-13 | 「8 天 7 版」vs CHANGELOG 6 段正文 | `roadmap-update` §1 vs `CHANGELOG.md` |
| P2-14 | ◐ 部分修正：正文否决 T0 种子、mermaid 仍画「init → T0 种子 3 条」的历史口径差异保留；零宽空格「u200b」、错别字、失效 wikilink 已于 2026-11-11 修正 | 该文档 §4.2/§6 vs §8/§9 |

补充（2026-11-11 修订后）：✅ 已修正 `hn-launch-timing.md` 的第二个 §4（→ §5）、教程截断句与错别字（`llmmwiki index`、`「离」`、「飞到回调」）、`eval-seed-design.md` 的失效 wikilink / 零宽空格 / 错别字。⏸ 仍保留：`llmwiki-eval.md` 两个 §3 且缺 §6、`llmwiki-vs-rag-comparison.md` 两个 §4（编号与交叉引用耦合，需重排）、`obsidian-guide.md` 描述作者个人库（11 插件、`.obsidian/`）、作者名 `Luca` / `voidvec` /「王小c」/「后端工程师 AI 落地手记」四种写法、`remote-onboarding.md` 公开/私有措辞。以上均归类为已知问题 / 待办或历史计划口径差异，不改写历史记录。

## 6. P3：缺失产物与未落地约定

> 以下各项统一表述为「仓库内无记录」，归类为已知问题 / 待办；P3-9 的图片链接已于 2026-11-11 修正（见 §1 修订记录）。

1. `docs/cr/` 目录（C2 变更单要求落盘）——仓库内无记录。
2. `docs/release-response-ledger.md`（发布后 48h 台账）——仓库内无记录。
3. `docs/weekly/2026-W37 … W44`（W2–W9 周报）——仓库内仅 W36 一份，W37–W44 仓库内无记录；DoD 把「9 份缺 ≤1」列为硬性指标（已知问题 / 待办）。
4. ~~`v0.1.7` tag / CHANGELOG 段 / PyPI 版本——仓库内无记录~~ **已于 2026-11-26 全部落地并关闭**：tag `0f4210a`、`CHANGELOG.md [0.1.7]`、PyPI wheel + sdist、GitHub Release `v0.1.7`（快照 `version` 仍记 v0.1.6，因快照取自 Release 字段，见 PR-02）。
5. W9 pivot / 止损决策文档——仓库内无记录（按 `stats/` 数据触发条件成立）。
6. `scope-freeze.md` 主理人签署——仓库内无签署记录（状态「待签署」、签署栏空白）。
7. `.kb-lint-ignore.json` 实例——代码与教程都支持，仓库内无记录；且格式是「纯正则串数组」，与「每条需附注释说明来源」的要求无落点。
8. 「how we measured」复现附录、`llmwiki query` 演示截图 / GIF——`hn-post-draft.md` 与对比文 TODO 仓库内无记录（已知问题 / 待办）。
9. `assets/qrcode-wechat-placeholder.png` 仍是占位图；`docs/community/discussion-welcome-post.md` 引用 `../assets/...`，从 `docs/community/` 解析到 `docs/assets/`，**链接原失效，已于 2026-11-11 修正为 `../../assets/...`**（实际文件在仓库根 `assets/`）。

另外：README 两版的「文档」索引分别只列 9 / 11 篇，均未收录 `scope-freeze / release-plan / RELEASE / remote-onboarding / *-verify / eval-seed-design / webui-dashboard-design / hn-* / weekly / community / weekly-report-template` 等 20 篇。

## 7. 不确定 / 待补充项：P4 待验证与待决策

| # | 事项 | 现状 |
|---|---|---|
| P4-1 | `pytest` 全量结果与干净环境安装 | CHANGELOG 0.1.5 记「42 passed」，当前测试文件含 53 个测试函数；未实跑（涉及 P0-4） |
| P4-2 | `stats/` 是否由 workflow 逐日真实生成 | 仓库内 2026-09-05~11-25 存在逐日 `obs(daily)` 提交；但 11-06 之前除 09-01（`+0800` 手工）外 65 个 JSON + CSV 的 mtime 全为 2026-11-07 12:00、`fetched_at` 全 `+0000`，且缺 09-02，推测为批量回填（待验证）；11-07 及以后由远端逐日提交补齐 |
| P4-3 | `open_prs` 口径 | `per_page=1` + `len(pulls)` 恒 0/1，不能作为「无 PR」强证据 |
| P4-4 | 计划类动作是否在仓库外发生 | HN 发帖、养号、PyPI 上传、CR 评审可能只在站外/本地；仓库内无记录，不能断言绝对未执行 |
| P4-5 | 新建 `knowledge-base/` 是否应排除出索引 | 本目录未加入 `DEFAULT_EXCLUDE_DIRS`；对仓库根跑 `llmwiki index` 会收录这些 `.md` |
| P4-6 | 陈旧产物清理 | `dist/` 0.1.3、egg-info 0.1.5、`.venv` editable 指向 0.1.2、`bug_report.yml` placeholder 0.1.1、pypi-guide 全文示例 0.1.0 |

## 8. 建议的收敛顺序

1. **先实测**：干净 venv 跑 `pip install ".[serve,dev]"` + `pytest` + `scripts/smoke_feishu_telegram.py`，坐实或排除 P0-1~P0-4。
2. **再修 P0 代码缺陷**（多为小改动：相对导入、返回退出码、全量注入 cfg、占位符、锚点目标）。
3. **统一口径**：把 `[categories]` 增量语义、`ingest --apply` 自动重建索引、`contextual_recall` 字段名、`[serve]` 命名、`health` 命令补齐到 README / 教程 / TOML 模板。
4. **冻结或废弃计划体系**：D1–D12 / Wave / M 编号 / 阈值 / Q 编号至少选一套权威来源，其余标注「历史」。
5. **补决策记录**：pivot 与否、是否补发 v0.1.7、是否重启周报与 CR；这一步是产品决策，不是文档工作。

## 9. 注意事项

- 本台账是**静态核对结果**，不是 bug 跟踪系统；修完一条应同步更新本文件与对应主题文档（2026-11-11 修订记录见 §1）。
- 「文档不一致」中相当一部分属**计划文档的历史快照**（如 W36 周报）；2026-11-11 已按口径基准 §0.4 给计划 / 历史类文档加统一状态标注头，正文论证不改写。
- 涉及外部动作的结论（HN / PyPI / pivot）一律标注「仓库内无记录」，避免越界断言。

## 10. 主要依据

三路盘点的交叉结果；关键复核点：`src/llmwiki/ingest.py:416-419`、`src/llmwiki/cli.py:141-147`、`src/llmwiki/channels/wecom_adapter.py:48,123`、`src/llmwiki/channels/wechat_bridge.py:77-79`、`src/llmwiki/eval_recall.py:464-497`、`pyproject.toml:29-41`、`.venv/Lib/site-packages/httpx2-2.12.0.dist-info/METADATA` 与 `_alias.py`、`src/llmwiki/data/scaffold/kb-lint.yml:22`、`stats/`、`docs/weekly/`、`dist/`、根 `.gitignore`。

## 11. 相关主题

- KB-02 / KB-04 / KB-06 / KB-07 / PR-02 / PR-03 各篇的「不确定 / 待补充项」均汇总于此
- PR-05 现有文档索引与查阅路径（含失效链接）
