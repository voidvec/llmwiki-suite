---
title: 现有文档资产索引与查阅路径
description: 原有 39 份文档的可信度分级、分类索引与按场景查阅路径
tags: ["文档索引", "分级", "查阅"]
difficulty: beginner
categories: ["参考手册"]
record_id: PR-05
legacy_kb_id: KB-13
kind: project-record
status: derived
scope: 原有 39 份文档 + 2026-11-11 新增 knowledge-base/ 14 篇的分类索引、可信度分级、按场景查阅路径与失效提示
audience: 需要回到原始文档查证的人
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
relocated: 2026-11-12 方案 C · knowledge-base/ → docs/project-records/
confidence: medium
---

# 现有文档资产索引与查阅路径

> **归档状态（2026-11-12）**：按方案 C 从 `knowledge-base/` 迁至 `docs/project-records/`，属**项目记录 · 原有文档索引**，不是知识层文档。正文记录 2026-11-11 时点状态，未改写；编号已于 2026-11-12 重排为 `PR-05`（旧 `KB-13`），全仓引用已同步更新，映射见 [README.md](README.md) §2。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 为准，权威口径见 [00-canonical-baseline.md](00-canonical-baseline.md)。


> **定位**：不是文档摘要合集，而是**回到原始证据的导航**。每篇标一句话作用 + 可信度分级，并指出哪些只能当历史快照读。

## 1. 背景与结论速览（分级标准）

原有文档共 39 份：根目录 6、`docs/` 25、`deliverables/product-strategy/` 4、`.github/` 模板 4；另有 2026-11-11 建立的 `knowledge-base/` 派生文档 14 篇。原有文档写作时间集中在 2026-08-24 ~ 09-01，此后工程代码在 0.1.6（2026-08-31）定格、计划文档与仓库现实脱节，因此按「能否直接当现状读」分三级（时间锚点截至 2026-11-11）：

| 标记 | 含义 |
|---|---|
| `[现行]` | 与当前代码基本一致，可直接照做 |
| `[部分过时]` | 主体可用，但含旧命令名、旧语义或缺项，须对照 PR-04 |
| `[历史]` | 计划 / 设计稿 / 某一时点快照，**不能当现状**；用于追溯决策意图 |

> 计划 / 历史类文档已于 2026-11-11 加统一状态标注头（`[未兑现]` / `[已过期]`），与下表分级并存；状态标注头是判断「能否当现状读」的第一依据，完整口径见口径基准 §0.4。

**关键关系**：文档分三类角色，查证时按「代码事实 → 现行文档 → 计划意图」的顺序回溯：

```
源码 src/llmwiki/  ──（事实基准）
   ↑ 对照
现行文档：README / getting-started / health / eval / obs / CONTRIBUTING / SECURITY
   ↑ 约束
计划与契约：scope-freeze / implementation-plan-dod / roadmap-update / release-plan
   ↑ 记录
历史快照：weekly/2026-W36 / RELEASE / eval-seed-design / webui-dashboard-design
   ↑ 佐证
运行数据：stats/ 85 份快照、testkb/eval_reports、dist/ 产物
```

`[部分过时]` 与 `[历史]` 的具体条目统一汇总在 PR-04；本索引负责让你快速找到原文。README 两版的「文档」表只列 9 / 11 篇，不能当完整清单用。

## 2. 分类索引

### 2.1 门面与治理（根目录 6）

| 文件 | 作用 | 级别 |
|---|---|---|
| `README.md` | 中文主门面：slogan、30 秒接入、命令表（2026-11-11 已补齐 `health`）、4 通道、厂商表、文档索引 | `[部分过时]`（文档索引仍不全） |
| `README.en.md` | 英文门面：Why compile instead of RAG 对比表、三条承诺、命令表含 health、docs 索引较全；回调路径已于 2026-11-11 修正为 `/wechat/callback` | `[部分过时]`（其余微调见 PR-04） |
| `CHANGELOG.md` | Keep a Changelog + SemVer 版本史（0.1.0–0.1.6，0.1.2 无正文，Unreleased 空） | `[现行]` |
| `CONTRIBUTING.md` | 开发安装、pytest 与独立召回基线、Conventional Commits、PR 四步 | `[现行]` |
| `SECURITY.md` | 私有漏洞报告 + 48h 确认、密钥只走 env、600s 熔断、最小权限、支持版本表 | `[现行]` |
| `LICENSE` | MIT，`Copyright (c) 2026 Luca` | `[现行]` |

### 2.2 上手与验证（5）

| 文件 | 作用 | 级别 |
|---|---|---|
| `docs/getting-started.md` | 五步接入 + 网页问答 / SSE curl 示例 + 3 条铁律；frontmatter 停在 0.1.0 | `[部分过时]` |
| `docs/remote-onboarding.md` | 另一台机器 / 别人的库：PyPI 直装、多库切换、升级；公开/私有措辞矛盾 | `[部分过时]` |
| `docs/llmwiki-local-verify.md` | 知识库重建流程、**用户资产边界**（哪些可删）、editable 安装全链路；2026-11-11 已改为「CLI 9 命令」 | `[部分过时]`（其余按历史快照读） |
| `docs/llmwiki-channel-verify.md` | 飞书/Telegram 本机验证：env 清单、`/healthz`、SSE、challenge 与 HMAC 脚本、7 条验收 | `[部分过时]` |
| `docs/RELEASE.md` | S2/M6 发布检查记录：PyPI 核名、sdist/wheel 断言、clean venv 7 项验证、Windows `git+file:///` 限制 | `[历史]` |

### 2.3 体系与教程（5）

| 文件 | 作用 | 级别 |
|---|---|---|
| `docs/llmwiki-architecture.md` | 分层职责、BM25/通道参数、iLink 选型、契约时序、A/B 暴露形态、个人库 S3 验收 | `[部分过时]` |
| `docs/obsidian-guide.md` | 零编辑器依赖、三条硬约束、插件分层；**描述的是作者个人库，不是本仓库** | `[部分过时]` |
| `docs/tutorials/llmwiki-tutorial-01-system.md` | 40 分钟体系搭建教程：规范、Ingest/Query/Lint 三阶段、链接铁律、常见坑 | `[部分过时]` |
| `docs/tutorials/llmwiki-tutorial-02-channel.md` | 30 分钟渠道接入：4 通道架构、env 清单、iLink 扫码、排错 FAQ | `[部分过时]` |
| `docs/tutorials/llmwiki-tutorial-03-quality-tuning.md` | 25 分钟检索调优：R1–R6、评估集 5 要点、测-改-测、混合检索触发条件 | `[部分过时]` |

### 2.4 能力参考（6）

| 文件 | 作用 | 级别 |
|---|---|---|
| `docs/llmwiki-health.md` | 健康分 0–100：经验版 Beta 定性、40/40/20 三规则、字母档、schema、与 lint 对比 | `[现行]` |
| `docs/llmwiki-eval.md` | eval 命令参考：评估集 schema、报告字段、退出码 0/2/3、0.95/0.90 基线；**`--chart` 已于 2026-11-11 补齐，章节编号重复仍待重排** | `[部分过时]` |
| `docs/llmwiki-eval-seed-design.md` | 设计决策 v2.0：假 100% 问题、T0/T1/T2、四场景矩阵、08-27 拍板结果 | `[历史]` |
| `docs/llmwiki-eval-report-v1.md` | D7 公开评测报告：8 条 query 全 Top-1、逐条明细、6 条局限、v2/v3 计划 | `[现行]` |
| `docs/llmwiki-obs.md` | D4 曝光监控：每日抓取、幂等覆盖、429 降级且退出码仍 0、周报取 CSV 最近 7 行；观测快照覆盖 2026-09-01 ~ 2026-11-25 | `[现行]` |
| `docs/llmwiki-evolution-roadmap.md` | L0→L3 自进化路线图 v1.1、新文件与命令、验收标准、7 条风险边界 | `[历史]`（L1+ 未实现） |

### 2.5 设计稿、计划与运营（9）

| 文件 | 作用 | 级别 |
|---|---|---|
| `docs/scope-freeze.md` | M0 范围冻结公告（**待签署**）：D1–D12、六条 Non-Goals、四条决策、C0/C1/C2 | `[历史]` |
| `docs/release-plan.md` | W4 硬发布执行预案：周二 06:00-09:00 PT、发布日/次日/48h Checklist、回复窗口 | `[历史]` |
| `docs/pypi-release-guide.md` | 维护者 PyPI 六步指南：2FA、project-scoped token、twine 凭证、TestPyPI 先行、版本同步 | `[部分过时]`（示例停在 0.1.0） |
| `docs/llmwiki-webui-dashboard-design.md` | `/webui/chat` + `/dashboard` 设计稿：P0–P3（P4 取消）、安全原则、开放问题 | `[历史]` |
| `docs/hn-launch-timing.md` | HN 时机探测：karma/账号龄门槛、窗口、标题 <70 字符、首评节奏 | `[历史]` |
| `docs/hn-account-growth.md` | HN 养号作战计划：karma 1→+49、时间线、主题池、5 条红线；2026-11-07 回填提交 `c57c718`（D8 重排），正文仍为 9 月初计划（W4 发布日 09-22），发布仓库内无记录 | `[历史]` |
| `docs/weekly-report-template.md` | D12 周报模板：6 个必填栏目、防漂移预警、Backlog 规则；W37–W44 周报仓库内无记录（PR-04 P3-3） | `[现行]`（模板） |
| `docs/weekly/2026-W36.md` | 唯一周报 W1：D1/D2/D3/D7/D12 完成、4 项 DoD 未达、外部信号 0 star / 94·569 | `[历史]` |
| `docs/community/discussion-welcome-post.md` | Discussions 欢迎帖：6 分类、快速开始、「先搜索后提问」、二维码占位 | `[现行]`（图片链接已于 2026-11-11 修正为 `../../assets/...`） |

### 2.6 策略交付物（4）

| 文件 | 作用 | 级别 |
|---|---|---|
| `deliverables/product-strategy/hn-post-draft.md` | D6 HN 主帖草稿：6 个标题候选、英文正文、发布前 Checklist | `[历史]` |
| `deliverables/product-strategy/llmwiki-vs-rag-comparison.md` | D6 对比帖草稿：7 维表、3 论证、RAG 仍更好的 3 条诚实边界 | `[现行]`（观点）/ `[历史]`（数字） |
| `deliverables/product-strategy/implementation-plan-dod-llmwiki-2026-08-31.md` | 9 周防漂移执行契约：4 条宪法、D1–D12 DoD、C0/C1/C2、W9 指标、M0–M6、Q1–Q10、git 策略 | `[历史]` |
| `deliverables/product-strategy/roadmap-update-llmwiki-2026-08-31.md` | Q4 深度调研路线图：市场/竞品、3 Persona、差异化四板斧、Top8 需求、KPI、风险 | `[历史]` |

### 2.7 GitHub 模板（4）

| 文件 | 作用 | 级别 |
|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Bug 表单：先跑 lint/eval、版本环境、7 类组件、2 条自查 | `[部分过时]`（placeholder 0.1.1） |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 功能建议表单：6 类、要求附 eval 数字、影响范围（旧名已于 2026-11-11 统一为 serve extras） | `[现行]` |
| `.github/ISSUE_TEMPLATE/docs_usage.yml` | 文档改进 / 使用咨询表单（0.1.5 新增） | `[现行]` |
| `.github/DISCUSSION_TEMPLATE/show-and-tell.md` | Show & Tell 模板：库主题/规模、接入路径、踩坑、质量自评 | `[现行]` |

## 3. 关键关系：按场景的查阅路径

| 场景 | 先读 | 再读 | 注意 |
|---|---|---|---|
| 五步接入 | `getting-started.md` | `remote-onboarding.md` → `local-verify.md` | 铁律 1 需补 KB-02 的 ingest 例外 |
| 检索调优 | `tutorial-03` | `llmwiki-eval.md` → `eval-report-v1.md` | 对比脚本字段名已于 2026-11-11 修正为 `contextual_recall` |
| 通道接入 | `tutorial-02` | `channel-verify.md` → `llmwiki-architecture.md` §2-§4 | env 与路由以 KB-07 为准 |
| 质量门禁 | `llmwiki-eval.md` | `llmwiki-health.md` → `CONTRIBUTING.md` | 阈值以 KB-06 为准 |
| 发版 | `pypi-release-guide.md` | `RELEASE.md` → `release-plan.md` | 版本现状以 PR-02 为准 |
| 判断计划状态 | `scope-freeze.md` | `implementation-plan-dod` → `weekly/2026-W36.md` → `stats/` | 全部按 `[历史]` 读 |
| 一致性审计 | PR-04 | 本索引 + 对应原文 | 不要改写历史周报，加过时标注即可 |

## 4. 已知失效与错链

- ✅ 已修正（2026-11-11）：`docs/community/discussion-welcome-post.md` 原写 `../assets/...`（解析到不存在的 `docs/assets/`），现改为 `../../assets/...`；实际资源在仓库根 `assets/`。
- 多处源码 docstring 引用 `docs/llmwiki-suite-design.md`（仓库内无记录）；`eval-seed-design.md` §9 的 `[[llmwiki-getting-started]]` 原与实际文件名不符，已于 2026-11-11 修正为 `[[getting-started]]`。
- `docs/llmwiki-eval-seed-design.md` 流程图仍画已被否决的 T0 种子；`docs/llmwiki-webui-dashboard-design.md` §2.1 数据流仍写 `POST /chat`。
- README 两版的文档索引分别只列 9 / 11 篇，漏掉约 20 篇（含所有计划与验证文档）。
- `assets/qrcode-wechat-placeholder.png` 为占位图，尚未替换。

## 5. 注意事项与常见误读

1. **`[历史]` 不等于「错」**：它记录的是当时的决策意图，做追溯很有价值，只是不能用来回答「现在怎样」。
2. **计划文档之间存在历史口径差异**（D9–D11、Wave、M 编号、阈值），属已知问题 / 待办，见 PR-04 P2；引用时务必带文件名，并以口径基准 §0.4 的裁定顺序为准。
3. **frontmatter 的 `updated` 普遍没随正文更新**：`getting-started.md` / `llmwiki-architecture.md` / 三篇教程正文都已含 0.1.5/0.1.6 特性，元数据却停在 2026-08-24，不能用 frontmatter 判断文档新旧。
4. `obsidian-guide.md` 讲的是作者另一个笔记库，别拿它核对本仓库目录。

## 6. 不确定 / 待补充项

- 39 份原有文档 + 14 篇派生文档之外，是否还有仓库外资料（公众号文章、HN 帖子、邮件决策）未纳入，无法从仓库判断。
- 本索引的可信度分级基于 2026-11-11 的静态核对，未逐篇运行其中命令；同日已完成定点事实修正，见 PR-04 §1 修订记录。
- ✅ 已完成（2026-11-11）：全仓权威来源优先级与统一措辞已建立，见 口径基准（裁定顺序 §0.4、措辞规范 §0.3）。

## 7. 主要依据

`docs/` 25 份、`deliverables/product-strategy/` 4 份、根目录 6 份、`.github/ISSUE_TEMPLATE/` 3 份与 `DISCUSSION_TEMPLATE/` 1 份；交叉核对 `src/llmwiki/`、`CHANGELOG.md`、`stats/`、`README.md` 文档索引表；另含 2026-11-11 建立的 `knowledge-base/` 14 篇派生文档。

## 8. 相关主题

- PR-04 已知偏差与待补充台账（本索引中 `[部分过时]` 的具体条目）
- PR-03 演进历程与当前项目状态（判断 `[历史]` 文档的时间坐标）
- PR-01 项目定位、业务背景与边界
