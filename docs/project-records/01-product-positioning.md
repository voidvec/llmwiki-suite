---
title: 项目定位、业务背景与边界
description: 产品定位、目标用户、与 RAG 和 Obsidian 的对比及明确非目标
tags: ["产品", "定位", "Non-Goals"]
difficulty: beginner
categories: ["参考手册"]
record_id: PR-01
legacy_kb_id: KB-01
kind: project-record
status: derived
scope: 为什么要做这个产品、为谁做、与同类方案的差异、明确不做什么
audience: 新接手者、产品决策者、文档维护者
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
relocated: 2026-11-12 方案 C · knowledge-base/ → docs/project-records/
confidence: high
---

# 项目定位、业务背景与边界

> **归档状态（2026-11-12）**：按方案 C 从 `knowledge-base/` 迁至 `docs/project-records/`，属**项目记录 · 产品定位与观点**，不是知识层文档。正文记录 2026-11-11 时点状态，未改写；编号已于 2026-11-12 重排为 `PR-01`（旧 `KB-01`），全仓引用已同步更新，映射见 [README.md](README.md) §2。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 为准，权威口径见 [00-canonical-baseline.md](00-canonical-baseline.md)。


> **定位**：回答「这是什么、解决谁的什么问题、边界在哪」。不描述实现细节（见 KB-01/KB-02），不写发布动作（见 PR-02）。

## 1. 背景

`llmwiki-suite` 是一个把 Markdown 笔记目录「编译」成可检索、可问答个人知识库的 Python 工具链，方法论源自 Andrej Karpathy 提出的「用 LLM 持续编译一份个人 wiki」（`README.md:17`）。项目于 2026-08-24 前后启动，8 月底密集迭代到 `0.1.6`（此后工程侧停滞近三个月，直到 2026-11-26 的 `0.1.7` / `0.1.8` 同日两版），随后进入以海外发布、观测与留存为主的产品化阶段（`CHANGELOG.md`、`roadmap-update-*.md`）；该阶段多项计划产物截至 2026-11-11 仓库内无记录（见 PR-03、口径基准 §0.1）。

一句话定位（`README.md:9`）：**把一堆 Markdown 笔记，编译成「会生长、能问答」的个人知识库**。目标是「只进不退」——每条笔记都被规范化、可检索、可追问，而不是躺在文件夹里堆灰。

战略层后来把定位从「本地 RAG 工具」升级为「**知识库自进化基础设施**」，明确「别和 RAG 抢检索、和 Obsidian 抢工作流、和记忆层抢知识资产」（`deliverables/product-strategy/roadmap-update-llmwiki-2026-08-31.md` TL;DR）。这一升级写在策略交付物里，**代码侧尚未出现 L1/L2/L3 实现**（见 PR-03）。

## 2. 结论速览

| 维度 | 结论 |
|---|---|
| 核心范式 | **编译优先（compile-first）**：导入期一次性建 frontmatter / 链接 / 索引，而非查询期临时切片 |
| 硬约束 | 核心链路零第三方 Python 依赖，仅标准库；Python ≥ 3.11 |
| 资产形态 | 产物是可读、可 git-diff、可 lint 的 JSON / Markdown，索引 `kb-index.json` 是单一事实源 |
| 交付面 | 9 个 CLI 子命令 + 本地 Web/API + 4 类 IM 通道 |
| 隐私承诺 | 全本地运行、无遥测上传、无云端组件；密钥只走环境变量 |
| 明确非目标 | 向量/embedding 检索（本期）、自动改写用户笔记、云端多用户托管、编辑器插件生态、健康分 Pro |
| 当前状态 | Pre-release `v0.1.x`（当前 `0.1.8`，2026-11-26 发布）；健康分标注「经验版 Beta」；产品化计划大面积未落地，计划产物截至 2026-11-11 仓库内无记录（PR-03） |

## 3. 关键关系

```
方法论（Karpathy LLM-wiki）
   └─> 编译范式：ingest → index → recall → answer
          ├─> 可观测性护城河：lint / eval / health（防知识漂移）
          ├─> 交付面：CLI（零依赖） + serve（fastapi，可选依赖）
          └─> 定位升级：L0 固化 → L1 增量记忆 → L2 主动建议 → L3 自主进化
```

三类目标用户（`roadmap-update-*.md` §3）与产品承诺的对应关系：

| Persona | 核心痛点 | 对应设计 |
|---|---|---|
| P1 技术博主（1000+ 篇 Obsidian 笔记） | 找不到、双链手动、RAG 答案不沉淀 | 编译式沉淀、零编辑器依赖 |
| P2 后端/DevOps 本地库管理员 | 隐私红线、手工维护索引与断链 | 纯本地可审计、lint 巡检、四通道降维护税 |
| P03 普通开发者（原文编号如此） | RAG 配置劝退、小模型幻觉 | pip 一条命令、自带 eval 自证质量 |

## 4. 主体内容

### 4.1 与 Classic RAG 的对比结论

| 维度 | Classic RAG | llmwiki（compile） |
|---|---|---|
| 工作时机 | 查询时切片 + embed | 导入时建 frontmatter / 链接 / BM25 索引 |
| 留存物 | 每次从零开始 | 可审计、可 diff、可 lint 的产物 |
| 检索质量 | 很少内置回归手段 | `llmwiki eval`（`summary.contextual_recall` / `summary.mrr`）一等公民 |
| 依赖 | 向量库 + embedding 模型 + chunking 旋钮 | 纯标准库 BM25 + wikilink 图 |
| 知识复利 | 重问成本相同 | 新笔记让旧答案变新 |

**诚实的边界**（`llmwiki-vs-rag-comparison.md` §4）：异构稠密语料（PDF/表格）、纯语义改写问题、以及「编译是工作流选择不是物理定律」——这些场景 RAG 仍更合适。对外结论是 **"llmwiki is a compile-first workflow tool, not a drop-in RAG replacement"**；混合检索（BM25 + embedding + RRF）被明确排到 L1/later，**当前代码没有向量检索**。

### 4.2 与 Obsidian 的关系

`docs/obsidian-guide.md` 的结论是「Obsidian 是**用起来更舒服的编辑器**，不是体系组件」：它不参与索引、检索、巡检任何一环。frontmatter 规范、wikilink 归一、文件名规范由体系说了算，用户用 VS Code / vim / 记事本都能完整工作（**零编辑器依赖**）。三条硬约束：`---` 首尾不能删、用路径式 wikilink、文件名按归一规则命名。

### 4.3 市场判断与差异化

策略文档调研的同赛道项目（AnythingLLM 62k / GPT4All 77k / Khoj 35k / mem0 50–63k / Letta 22k / Cognee 13k stars）**全部走向量路线**，据此判断「纯 Markdown 编译 + 零向量」无头部产品。差异化四板斧：① 定义「编译系」品类；② lint/eval 防漂移护城河；③ IM 多通道占国内工作流；④ pip 零依赖 vs Docker 重型部署。

> 注意：这组数字是 2026-08 的调研快照，未经复核，不应作为当前决策依据（见第 6 节）。

### 4.4 明确的非目标与非承诺

`docs/scope-freeze.md` §2（状态「待主理人签署」）六条 Non-Goals：① 健康分不做 Pro / 图表库，只做单文件 HTML/JSON 基础版；② 埋点不做全链路漏斗，只上 3 事件；③ L1 只做 observe + suggest 两命令精简版，不做 nightly 智能汇总与 L2 详细设计；④ 不做中文物料、iLink 国内通道后置 Wave 3、Telegram 只保底；⑤ 不做多平台长跑，只打 HN 主帖 + 对比文；⑥ 不做向量/embedding 系统设计，retention 完整基线降为可观测周报。

`roadmap-update-*.md` §8 补充：本期不实现 L3 自主修复、不云端多用户托管、不做「万物皆笔记」范围蔓延、不违背「内容所有权永远属于用户」。

### 4.5 架构级边界

- **套件永远只监听 `127.0.0.1`**，不直连公网；暴露形态只支持 A（Tailscale/ZeroTier，仅自己）与 B（团队内网反代 + Basic Auth）两种，「暂不做第三种」（`webui-dashboard-design.md` §0/§3）。
- **本项目无自有服务器端组件**，`llmwiki serve` 的 TLS / 反代 / 防火墙安全边界由部署方负责（`SECURITY.md`）。
- iLink v1 适配器**仅做文本问答**，图片/文件 CDN AES-ECB 本期未实现；消息经腾讯云而非 P2P，且需先有平台开放权限（`llmwiki-architecture.md` §3）。
- L1「**不做自动改写用户笔记**」，只生成容易采纳的建议；机器只改自己生成的东西（`kb-evolution/`），建议一律标注「由 llmwiki 自动生成，请人工核」（`llmwiki-evolution-roadmap.md` §2.3/§4.3/§7）。

## 5. 注意事项与常见误读

1. **不要把它当 RAG 替代品评估**：两者工作时机不同；用「语义改写召回率」衡量 llmwiki 会得出错误结论。
2. **「零依赖」只覆盖核心链路**：`serve` / `wechat` extras 引入 fastapi、uvicorn、httpx2、qrcode；企业微信加解密还需要 `pycryptodome`（未在 extras 中声明，见 PR-04）。
3. **零编辑器依赖 ≠ 不用编辑器**：指体系不依赖特定编辑器，Obsidian 可作为可选前端。
4. **Non-Goals 第 4 条与仓库现状存在已知偏差**：scope-freeze 说「不做中文物料、README 只英文」，但主 README 是中文、有三篇中文教程、中文 Issue 模板；iLink 实际是中文 README 的推荐默认通道。归类为已知问题 / 待办，不是新约束（PR-04）。
5. **「内容所有权」是可执行约束**：任何自动修改必须可驳回、可回滚；L1/L2 不碰用户 `.md`。
6. `docs/obsidian-guide.md` 描述的是**作者个人笔记库**（11 个插件、`Templates/` 大小写修复），不是本仓库；照搬会导致误判。

## 6. 不确定 / 待补充项

- `docs/scope-freeze.md` 签署栏空白，仓库内无签署记录（PR-03 / PR-04 P3-6）；文中「M0 门禁 2026-09-01 已写入」属计划原文，生效与否以仓库内记录为准。
- 竞品 stars / 下载数据是 2026-08 调研快照，未联网复核；`roadmap-update` 内部就存在 475 与 569 两个 PyPI 下载基数。
- 「知识库自进化基础设施」定位升级只见于策略文档，代码与 CHANGELOG 无对应落地，属于**意向而非现状**。
- 「8 天 7 版」说的是 2026-08-24 ~ 08-31 那波，而 CHANGELOG 正文当时只有 6 段（0.1.2 无正文）；截至 2026-11-26 全史共 **8 段**（新增 0.1.7 / 0.1.8，均为跨期补发，不计入「8 天」）。统计口径待统一。
- 作者/对外名不统一：LICENSE 为 `Luca`、README 为 `voidvec`、公众号出现「王小c」与「后端工程师 AI 落地手记」两种写法。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `README.md` / `README.en.md` | slogan（:9/:17-21）、包名 vs 命令名（:40）、Why compile instead of RAG 表、Your notes stay yours、Pre-release v0.1.x |
| `deliverables/product-strategy/llmwiki-vs-rag-comparison.md` | 7 维对比表、§4 When RAG is still better、§6 底线结论 |
| `deliverables/product-strategy/roadmap-update-llmwiki-2026-08-31.md` | TL;DR 定位升级、§3 Persona、§4 竞品与四板斧、§8 Non-Goals |
| `docs/scope-freeze.md` | §1 D1–D12、§2 六条 Non-Goals、§3 止损线 |
| `docs/obsidian-guide.md` | 「编辑器不是体系组件」结论、三条硬约束 |
| `docs/llmwiki-evolution-roadmap.md` | L0→L3、§2.3/§4.3/§7 边界 |
| `docs/llmwiki-webui-dashboard-design.md` | §0 P4 取消、§3 两种暴露形态 |
| `SECURITY.md` / `pyproject.toml` | 无自有服务端组件、`dependencies = []`、`requires-python >=3.11` |

## 8. 相关主题

- KB-08 业务规则与约束清单（把本节的「边界」转成可执行条目）
- PR-03 演进历程与当前状态（定位升级与计划兑现情况）
- PR-04 已知偏差与待补充台账（Non-Goals 与仓库现实的冲突）
