---
title: 业务规则与边界约束清单
description: 29 条硬不变量、可执行约束、阶段性取舍与流程纪律
tags: ["规则", "约束", "红线"]
difficulty: intermediate
categories: ["知识库规范"]
kb_id: KB-08
legacy_kb_id: KB-10
kind: knowledge-base
status: derived
scope: 把散落在文档与代码里的「硬规则 / 红线 / 取舍」收敛为可执行的条目化清单
audience: 贡献者、评审者、做合规或实现一致性检查的人
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 业务规则与边界约束清单

> **定位**：PR-01 讲「为什么有边界」，这篇讲「具体哪些规则必须遵守、在哪能查到、违反会怎样」。每条都标注来源与强度。

## 1. 背景

项目规则分散在 `SECURITY.md`、`CONTRIBUTING.md`、`scope-freeze.md`、DoD 执行契约、教程「铁律」、以及源码常量里。有些是**强制不变量**（零依赖、密钥不入文件），有些是**阶段性取舍**（本期不做向量检索），有些是**已过时但仍被文档引用的口径**。把它们分级，才能判断改代码时哪些不能碰。

## 2. 结论速览

| 强度 | 含义 | 条目数 |
|---|---|---|
| **A 硬不变量** | 违反即破坏产品承诺，改动需重新评审 | 8 |
| **B 可执行约束** | 代码/流程里已落地，改动需同步文档与测试 | 9 |
| **C 阶段性取舍** | 本期范围决定，可随下一阶段变更 | 7 |
| **D 流程纪律** | 团队协作约定，影响交付而非功能 | 5 |

## 3. 关键关系：规则从哪来

```
产品承诺（README.en / roadmap）
   ├─> A 硬不变量 ──> SECURITY.md / pyproject.toml / config.py / kb_core.py
   ├─> B 可执行约束 ──> CLI 退出码 / LLM 预算 / 索引语义 / 脚手架
   └─> C 阶段性取舍 ──> scope-freeze.md / evolution-roadmap.md
协作契约（DoD / CONTRIBUTING）
   └─> D 流程纪律 ──> 变更控制、提交策略、周报、人审
```

## 4. 主体内容

### 4.1 A 类：硬不变量（8 条）

| # | 规则 | 来源 | 违反后果 |
|---|---|---|---|
| A1 | **核心链路零第三方依赖**，仅标准库；新增依赖只能进 `pyproject.toml` 的 extras | `pyproject.toml:25`、`CONTRIBUTING.md` | 破坏「pip 一条命令、离线可用」的核心卖点 |
| A2 | **密钥只走 `LLM_WIKI_*` 环境变量**，套件不读取任何 `.env` 文件；密钥绝不写入 `llmwiki.toml` / README / 示例 | `SECURITY.md`、`config.py:8`、`cli.TOML_TEMPLATE` | 凭据泄露风险 |
| A3 | **内容所有权永远属于用户**：建议可驳回、可回滚；L1/L2 不碰用户 `.md`；L3 只动 `kb-evolution/` 且强制人审 | `README.en.md`、`evolution-roadmap.md` §2.3/§4.3/§7、DoD §2 | 破坏信任模型 |
| A4 | **零编辑器依赖**：规范由体系定，编辑器只负责输入；frontmatter `---` 不可删、用路径式 wikilink、文件名按归一规则 | `docs/obsidian-guide.md`、`kb_core.normalize_token` | 索引与链接判死失效 |
| A5 | **全本地、零遥测上传、无云端组件**：health / telemetry 全匿名，事件只追加到 `~/.llmwiki/telemetry/events.jsonl` | `README.en.md`、`telemetry.py`、`SECURITY.md` | 隐私承诺失效 |
| A6 | **套件永远只监听 `127.0.0.1`**，不直连公网；暴露形态只 A / B 两种 | `webui-dashboard-design.md` §0/§3、`cli.py` serve 默认 host | 安全边界失守 |
| A7 | **`kb-index.json` 是运行时单一事实源**，任何笔记变更后必须重建 | `config.py`、`gen_index.py`、`getting-started.md` 铁律 1 | 检索结果过期 |
| A8 | **工具只操作 `--repo` 指向的库**，不扫系统目录；所有 `os.walk` 跳过隐藏目录与排除集 | `SECURITY.md`、`kb_core.iter_md_files` | 越权访问 |

### 4.2 B 类：可执行约束（9 条）

| # | 规则 | 落地位置 |
|---|---|---|
| B1 | 索引刷新分三条路径：`ingest --apply` 自动重建、`llmwiki index` 手动重建、`query` / `recall` 不自动重建只做新鲜度告警 | `ingest.py:416-419`、`cli._warn_stale`、`recall.check_freshness` |
| B2 | 新鲜度告警**只提示不阻断**（mtime/size/hash 三向），不改退出码 | `recall.check_freshness`、`eval_recall.py` |
| B3 | `lint` 阻断（`errors>0 → exit 1`）、`health` 恒返回 0（不阻断） | `lint.py:208`、`cli.cmd_health` |
| B4 | `eval` 退出码 **3 索引缺失 > 2 无评估集 > 0 成功**；无集绝不回退内置集给假分数 | `eval_recall.run_eval_cmd` |
| B5 | 门禁**执行口径** recall≥0.95 / MRR≥0.90（代码 / CI / pre-commit 为准）；策略合同 0.85/0.80 为历史计划口径，引用须标注区分 | `check_recall_baseline.py:55-57`、CI、pre-commit、KB-06 §4.6 |
| B6 | LLM 预算熔断：单次 30s、ingest 全局默认 600s（`LLM_WIKI_INGEST_LLM_TOTAL_TIMEOUT`）；异常静默降级 | `ingest.py:118-122`、`assistant.py` |
| B7 | `ingest` 默认 dry-run；**SHA256 重复仅报告不删**、目录建议仅报告不移动（`--move` 才动） | `run_ingest` |
| B8 | 输出端长度上限：IM 1800 字（Telegram 4000）、上下文每段 1200 字、LLM 降级预览 600 字 | 各 adapter、`assistant.build_context` |
| B9 | 受控词表语义为**增量追加**（`replace_default=true` 才整体替换）；`[aliases].groups` 同为追加 | `config.load_config:125-149`、`TestCategoriesIncremental` |

### 4.3 C 类：阶段性取舍（7 条）

`docs/scope-freeze.md` §2 六条 Non-Goals：① 健康分不做 Pro / 图表库（只单文件 HTML/JSON，定性「经验版 Beta」）；② 埋点只上 3 事件，不做全链路漏斗；③ L1 只做 `observe + suggest` 两命令精简版，不做 nightly 智能汇总与 L2 详细设计；④ 不做中文物料、iLink 国内通道后置 Wave 3、Telegram 只保底；⑤ 不做多平台长跑（只 HN 主帖 + 对比文）；⑥ 不做向量/embedding 系统设计，retention 完整基线降为可观测周报。

补充（`roadmap-update` §8、`evolution-roadmap`）：本期不实现 L3 自主修复、不做云端多用户托管、不做「万物皆笔记」范围蔓延；L1 不自动改写用户笔记；P4 会话保护取消；iLink v1 仅文本问答。

> **状态提示**：C 类第 4 条是 2026-09-01 的范围冻结意图，与仓库现状存在已知偏差（中文 README、三篇中文教程、iLink 为默认通道），归类为已知问题 / 待办，不是现行约束（PR-04）。

### 4.4 D 类：流程纪律（5 条）

| # | 规则 | 来源 |
|---|---|---|
| D1 | **DoD**：每个 D1–D12 的「完成定义 = 全部打勾」；角色分 写 W（AI 起草）/ 审 R（主理人复核，**LLM 产物必须人审**）/ 验 A（能否经受外部用户检验） | `implementation-plan-dod` §2 |
| D2 | **四条防漂移宪法**：P1 范围冻结即冻结 / P2 先验收再交付 / P3 外部信号优先于内部手感 / P4 人为可控的等待不叫等待 | 同上 |
| D3 | **变更控制 C0/C1/C2**：C0 文案样式主理人自批；C1 增删交付物或影响 1 指标 ≤1 天答复；C2 改时间线/定位/≥2 指标需暂停重审、≥2 天 + 书面 CR 落盘 `docs/cr/` | 同上 §3 |
| D4 | **提交策略**：AI 本地高频小粒度 commit，**push 由主理人手动执行**；格式 `[type](module): 简述 [D#][CR-XXX]`；`main` 直推不 rebase / force-push；破坏性提交用 `git revert` | 同上 §11 |
| D5 | **周报纪律**：固定「周二 PT」，6 个必填栏目；连续 2 周 ≥2 项未验收触发防漂移预警；单周新增 Backlog >3 条则该周仅允许 1 张 C1 CR | `weekly-report-template.md` |

### 4.5 其他操作红线

- 漏洞**不要开公开 Issue**，走 GitHub Private vulnerability reporting；**48 小时内确认收到**（`SECURITY.md`）。
- 支持范围：仅最新 release 提供安全修复；Python ≥3.11；Pre-release v0.1.x。
- 贡献流程：Conventional Commits（`feat(core):` / `fix(cli):` / `docs(*):` / `test(*):` / `chore(release):`）、Fork → `feat/xxx` → PR 写清动机与验证方式 → CI 全绿合并（`CONTRIBUTING.md`）。
- HN 养号红线：不拉票、不硬广、不群发、新号 14 天内不发主题帖、发帖当日不再发其他内容（`hn-account-growth.md`）。
- 发布红线：禁止 `-u -p` 明文进 shell history、发布前 48h 标题定稿「禁止临场改稿」、发布后 48h 内不大改主帖正文（`pypi-release-guide.md` / `release-plan.md`）。

## 5. 注意事项与常见误读

1. **C 类不是永久架构约束**：尤其「不做中文物料」与仓库现状不符，引用时须注明是 2026-09-01 的范围冻结意图（已知问题 / 待办，PR-04）。
2. **A2 与 DoD §11 冲突**：后者写「bot token / appsecret 一律进 `.env`」，与「套件不读 `.env`」直接矛盾；以 A2 为准，且根 `.gitignore` 确实忽略 `.env`。
3. **`GITIGNORE_LINES` 忽略 6 项产物，但不含 `.ilink_session.json` / `.obsidian/`**，尽管文档声称已忽略——这是 A2/A5 的潜在漏洞（PR-04）。
4. **B1 的三条路径以代码为准**；`getting-started` 的「3 条铁律」是笼统旧口径，写文档时应按口径基准 §0.3 给出完整三条路径。
5. D3 要求的 `docs/cr/` 目录、D5 要求的 W37–W44 周报仓库内无记录，属**规则已定但未落地**的已知问题 / 待办（PR-03 / PR-04 P3）。

## 6. 不确定 / 待补充项

- `scope-freeze.md` 签署栏空白，仓库内无签署记录；C 类规则是否正式生效以仓库内记录为准（PR-03 / PR-04 P3-6）。
- 「推理预算熔断默认 600s」在 `SECURITY.md` 是安全底线，但 `LLM_WIKI_INGEST_LLM_TOTAL_TIMEOUT` 可被环境变量任意调大，是否需上限约束未定。
- `resolve_md_link` 对非 `.md` 目标用 `os.path.exists(os.path.join(repo, joined))`，未见绝对路径 / 父目录穿越防护（仅判存在不读内容），是否需补强待评估。
- D 类规则的 enforcement 完全依赖人工，没有自动化检查；是否值得落脚本待定。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `SECURITY.md` | 漏洞流程、密钥、最小权限、600s 熔断、支持版本表 |
| `CONTRIBUTING.md` | 零依赖约束、测试原则、Conventional Commits、PR 流程 |
| `src/llmwiki/defaults.py` / `config.py` / `kb_core.py` / `ingest.py` | A/B 类代码落地 |
| `src/llmwiki/lint.py` / `eval_recall.py` / `health.py` | 退出码与阻断语义 |
| `docs/scope-freeze.md` | §1 D1-D12、§2 六条 Non-Goals、§3 止损线 |
| `deliverables/product-strategy/implementation-plan-dod-llmwiki-2026-08-31.md` | §2 宪法与 DoD、§3 C0/C1/C2、§11 提交策略 |
| `docs/weekly-report-template.md` / `docs/hn-account-growth.md` / `docs/release-plan.md` | 流程红线 |
| `docs/llmwiki-health.md` / `docs/llmwiki-evolution-roadmap.md` | Beta 定性、L1/L3 边界 |

## 8. 相关主题

- PR-01 项目定位、业务背景与边界
- KB-06 质量保障体系与门禁
- PR-03 演进历程与当前状态
- PR-04 已知偏差与待补充台账
