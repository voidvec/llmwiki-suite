---
title: "LLMWiki 体系搭建：从零打造会生长、能问答的个人知识库"
description: "从零开始用 llmwiki-suite 工具链（Karpathy incremental wiki 方法论），打造可检索、可问答、可自维护的个人知识库。覆盖 Ingest/Query/Lint 三阶段与 PowerShell/bash 双版本命令。"
categories: ['知识库规范', '软件架构']
tags:
  - llmwiki
  - rag
  - knowledge-base
  - ingest
  - query
  - lint
  - tutorial
difficulty: "intermediate"
estimated_time: "40分钟"
created: "2026-08-18"
updated: "2026-08-24"
version: "3.0"
---

# LLMWiki 体系搭建：从零打造会生长、能问答的个人知识库

> 适用对象：想用 LLM 把自己的笔记 / 资料编译成一份「会生长、能问答」的个人 wiki 的人。
> 本文给出**从零到一**的完整教学流程，所有命令均提供 **PowerShell（Windows）** 与 **bash（Linux/macOS）** 双版本。
> 本文是一篇**入门向导**：一次读完、跑通即可。检索质量不满意？那是 [[llmwiki-tutorial-03-quality-tuning]] 的事，不在这里展开。

---

## 0. 这套体系是什么（先讲理念）

LLMWiki 源自 Andrej Karpathy 提出的 **「用 LLM 持续编译一份个人 wiki」** 的思路。它和常见的 RAG（每次查询都临时检索）不同：

| 维度 | RAG | LLMWiki（本文体系） |
|------|-----|--------------------|
| 知识形态 | 检索时临时拼上下文 | **持久化、可持续累积**的结构化 wiki |
| 谁写内容 | 不落盘，答案随会话消失 | **LLM 持续维护** markdown 页面，交叉引用已建好 |
| 检索 | 向量库 + 相似度 | BM25 关键词检索（正文索引 + Wikilink 图扩展）+ 章节级取数 |
| 健康度 | 无 | 有 **Lint** 阶段定期巡检，防止腐化 |

这套体系工程化为三个核心操作：

- **Ingest（摄入）**：把零散笔记 / 源文档变成「可被检索的规范文档」，并重建检索索引。
- **Query（检索问答）**：基于本地索引召回候选 → 拼 prompt → 调 LLM → 返回带来源的回答。
- **Lint（健康巡检）**：定期检查死链、frontmatter 缺失、分类不规范，保持知识库不腐化。

> 心智模型：知识库就是**一个带 git 的 markdown 仓库**。`kb-index.json` 是「单一事实源」——任何写入（新增文档、归一、lint 修正）最后都要重建它。

---

## 1. 环境准备

### 1.1 前置条件

| 项 | 说明 | 验证 |
|----|------|------|
| Python ≥ 3.11 | tomllib 依赖的版本下限 | `python --version` |
| git | 管理知识库版本（也是 `llmwiki` 定位仓库根的锚点） | `git --version` |
| LLM API Key | **可选**：不设也能跑，问答降级为「检索片段预览」 | `echo $LLM_WIKI_API_KEY` |

### 1.2 安装 llmwiki-suite

核心引擎零三方依赖，标准 `pip install` 即可：

```bash
# 推荐：一条命令装好【全部能力】（核心 + 微信/企业微信通道 fastapi+uvicorn）
pip install "llmwiki-suite[serve]"

# 轻量：只装核心（ingest / index / query / lint / eval，零第三方依赖）
# pip install llmwiki-suite
```

> 关键字提醒：包名是 **`llmwiki-suite`**（PyPI 上 `llmwiki` 已被其他项目占用），但安装后的命令仍是 `llmwiki`。
> 装好后确认：

```bash
llmwiki --help
```

> 无论 Windows 还是 Linux/macOS，`llmwiki` 命令都能直接调用（入口脚本由 pip 创建）；
> 若多 Python 环境并存，用 `python -m llmwiki.cli` 等价替代。

---

## 2. 目录结构与文档规范（先立规矩）

知识库的健康度，七成取决于**规范是否一开始就被遵守**。请先读完本节再动手写第一份文档。

### 2.1 初始化一个库

套件以「目录 + `llmwiki.toml`」为一个知识库。`llmwiki init` 一键生成配置模板与脚手架（.gitignore / pre-commit / CI）：

```bash
# 进入你的笔记目录（可以是已有笔记仓库，或新建空目录）
cd ~/my-notes
llmwiki init      # 生成 llmwiki.toml + 拷入 .gitignore/pre-commit/CI 模板

# 树状结构概览：
# ├── llmwiki.toml        # 三层配置：套件默认 < 本文件 < 环境变量(仅密钥)
# ├── kb-index.json       # 检索索引（自动生成，不手改）
# ├── category-index.md   # 分类导航页（自动生成）
# └── 笔记.md ...         # 你的文档（frontmatter 规范见下）
```

`llmwiki.toml` 里可配置的核心项（均有默认值，不配也能跑）：

| 配置段 | 作用 | 示例 |
|--------|------|------|
| `[repo] index_file` | 索引产物文件名 | `kb-index.json` |
| `[ingest] extra_exclude` | 追加排除目录 | `["私人文档/", ".obsidian"]` |
| `[categories] allowed` | 受控词表（整体替换默认） | `["知识库规范", "软件架构", "读书笔记"]` |
| `[llm] model / base_url` | 非密钥 LLM 参数 | `gpt-4o-mini` |
| `[serve] host / port` | 桥接服务监听 | `127.0.0.1 / 8000` |

> 密钥**只走环境变量**（`LLM_WIKI_API_KEY` / `LLM_WIKI_BRIDGE_TOKEN` / `LLM_WIKI_WECOM_*` / `LLM_WIKI_ILINK_*`），套件不解析任何 `.env` 文件。
> 详见 `llmwiki.toml` 模板内注释与 [[llmwiki-architecture]]。

### 2.2 frontmatter 必填字段

每篇文档**必须**以如下 YAML 头开头（首尾 `---` 不能删，这是「链接铁律」的硬约束）：

```markdown
---
title: "文档标题"
description: "一句话描述，用于索引摘要"
categories: ['所属分类']
tags:
  - 标签1
  - 标签2
difficulty: "beginner"   # beginner | intermediate | advanced
estimated_time: "15分钟"
created: "2026-08-20"
updated: "2026-08-20"
version: "1.0"
---
```

- `title` / `description` / `tags` / `difficulty` 是 lint **必检四项**，缺任一会报 error。
- `difficulty` 只能取 `beginner` / `intermediate` / `advanced` 三值之一。

### 2.3 受控词表（categories）：默认集合 + 如何定制

`categories` 必须落在知识库**已启用的分类集合**内（初始化时由 `llmwiki init` 写入 `llmwiki.toml` 的 `categories.allowed`）。lint 据此检查，目的是防止拼写错误或随意新建游离分类造成碎片化。

- **查看当前词表**：`llmwiki lint` 的 `--report` 细节会列出词表；或直接看 `llmwiki.toml`。
- **如何定制（有意引入新分类）**：编辑 `llmwiki.toml` 的 `categories.allowed`（整体替换语义），然后保持全库一致。别制造一次性拼写变体（如 `Qt` / `QT` / `qt` 并存）。

> `llmwiki lint` 对「空 / 极少词表」会给出 warning，防止误删默认。

### 2.4 文件命名规范

归一规则（`llmwiki ingest` 会自动执行，但手写时请自觉遵守）：

- 全小写；空格 / 下划线 `_` → 连字符 `-`；
- 全角冒号 `：` → `-`；
- 中文原样保留（无大小写问题）。

✅ `meeting-notes-weekly.md`   ❌ `Weekly_会议纪要.md`
✅ `reading-notes-llm.md`      ❌ `Reading Notes LLM.md`

### 2.5 交叉引用（wikilink）

两种写法都支持：

- 路径式：`[[NN-xxx/主题文档]]`（含目录层级，推荐，迁移更稳）
- 裸名式：`[[主题文档]]`（按全局文件名解析）

lint 会按「归一 + 分隔符 + 大小写不敏感」判定存活，避免假死链。

### 2.6 最小示例文档（会议纪要）

```markdown
---
title: "会议纪要：项目周会"
description: "每周项目例会要点记录：进展、阻塞、行动项。"
categories: ['会议纪要']
tags:
  - meeting-notes
  - project
difficulty: "beginner"
estimated_time: "10分钟"
created: "2026-08-20"
updated: "2026-08-20"
version: "1.0"
---

# 会议纪要：项目周会

## 本周进展
- 知识库接入微信完成，手机扫码即可查询。
- RAG 召回优化落地，评估集 recall@6 从 93% 升到 100%。

## 阻塞
- 企业微信回调域名证书未配置，渠道暂不可用。

## 行动项
- 下月部署到轻量服务器，详见 [[项目部署文档]]。
```

> 用 `llmwiki init` 拷到库根的 `templates/` 里还有会议纪要 / 读书笔记两份通用模板，可直接复制改。

---

## 3. Ingest：把笔记变成可检索文档

### 3.1 手动书写规范文档（推荐先学这一条）

最稳妥的方式：按 §2 规范**直接手写** frontmatter + 正文，存放到对应目录下，然后跑 `llmwiki index`。适合「我在认真整理某一主题」的场景。

### 3.2 批处理归一（零散笔记的救星）

如果你有大量缺 frontmatter、文件名不规范的旧笔记（比如随手存的「Weekly_会议纪要.md」），用 `llmwiki ingest` 自动补齐：

```bash
# bash — 先 dry-run 预览（默认只报告，不写文件）
llmwiki ingest

# 真正写入（补 FM / 重命名），并在最后自动重建索引
llmwiki ingest --apply

# 额外执行「建议的目录移动」（谨慎：会触发 git mv，需人工确认后使用）
llmwiki ingest --apply --move
```

```powershell
# PowerShell — 等价
llmwiki ingest
llmwiki ingest --apply
```

它做的事（全部**行级编辑，绝不整体重写文件、绝不删 `---`**）：

1. 补 frontmatter（缺则建，残则补 `title/description/tags/difficulty`）；
2. 文件名归一（全小写 + 空格/下划线 → `-` + 全角 `：` → `-`）；
3. SHA256 去重检测（仅报告，**不自动删**）；
4. 建议归类目录（**仅报告**，默认不跨目录移动）。

> 配置了 `LLM_WIKI_API_KEY` 时，会尝试用 LLM 推断 `categories/tags/description`，
> 但推断值**必须落到受控词表**才写入，否则留空兜底；未配 key 照样离线跑通。

### 3.3 重建检索索引（Ingest 的必须尾声）

无论手动写还是自动归一，**新增 / 修改文档后必须重建索引**，否则新文档不会进入召回（索引不自动刷新）：

```bash
# bash
llmwiki index

# 在别处指定库位置（不 cd 到库目录也能建）
llmwiki index --repo ~/my-notes
```

```powershell
# PowerShell 等价
llmmwiki index
```

产物（写在库根）：

- `kb-index.json`：检索索引，含 `documents`（含 `path/title/description/categories/tags/headings/summary/body_text/body_text_clean`）+ `category_index` / `tag_index` 倒排表。
- `category-index.md`：按分类聚合的自动导航页。

> 会自动跳过无 frontmatter 的 vendored 文件（如 `CHANGELOG.md` / `CONTRIBUTING.md`）。这类文件**永远不会进入召回**，所以正式文档务必带规范 frontmatter。

### 3.4 验证索引

```bash
llmwiki query "任意词" --recall-only   # 无 LLM 也跑通，看召回候选
# 或用 Python 直接读索引
python -c "import json; d=json.load(open('kb-index.json')); print('文档数:', d['doc_count'], '| 分类数:', len(d['category_index']))"
```

---

## 4. Query：检索与问答

### 4.1 纯召回（KbRetriever）

只检索、不调 LLM，用于**调试召回质量**——确认「我的问题能不能命中正确文档」：

```bash
llmwiki query "本周例会待办事项" --recall-only --top-k 4
```

或用 Python API（更贴近库内调试）：

```bash
python -c "
from llmwiki.recall import KbRetriever
r = KbRetriever('kb-index.json')
hits = r.recall('本周例会待办事项', top_k=4)
for h in hits:
    print(h.path, round(h.score, 2), h.matched_headings)
"
```

检索机制一句话：**BM25 关键词检索**（K1=1.5、B=0.75，顺序系数 title>tag>section>body>category，单字去停词，`min_score=0.15` + 每词阈值 1.0 的查询长度感知门槛），已含正文索引（代码标识符可检索），命中文档出链 `[[wikilink]]` 文档以封顶分补位。**调参 / 评估 / 诊断见 [[llmwiki-tutorial-03-quality-tuning]]**——本文只负责让你先跑起来。

> `top_k=4` 是套件默认（P5 收紧值）：57 条评估 recall@4=100% 无损失，上下文较旧默认省 ~35% token；显式传更大值（如诊断用 `top_k=6`）不截断。

索引进度检测（P3）：KbRetriever 初始化时做一次磁盘指纹核对（~11 ms），结果在 `r.freshness`（`stale` / `changed` / `added` / `deleted`）；长驻进程可随时 `r.check_freshness()` 复查。

### 4.2 召回 + LLM 编排（KbAssistant）

纯逻辑层（与传输解耦，微信 / HTTP / CLI 都调它）：

```bash
llmwiki query "北京例会有什么行动项"        # 默认走 KbAssistant：召回 → 拼 prompt → 调 LLM → 附来源
```

```python
from llmwiki import KbAssistant
a = KbAssistant('kb-index.json')
ans, cands = a.answer('北京例会有哪些待办？')
print(ans)
print('来源:', [c['path'] for c in cands])
```

- 配置了 `LLM_WIKI_API_KEY` → 返回 LLM 基于检索片段生成的回答（简洁、引用来源标题）。
- 未配置 → 返回「（未配置 LLM_WIKI_API_KEY，以下为检索片段预览）」+ 片段开头，**离线可联调**。
- 知识库无相关内容 → 返回「知识库中未找到相关信息。离」

### 4.3 章节级取数（省 token）

默认只取命中章节（`matched_headings`）那段，而非整篇全文，显著降低 LLM token 成本：

```python
chunk = r.fetch_chapter(h.path, h.matched_headings[0])  # 只取首个命中章节
# 或整篇：r.read_doc(h.path)
```

---

## 5. Lint：健康巡检，防止知识库腐化

### 5.1 为什么必须自己实现（而不是用 lychee / markdown-link-check）

标准链接检查器**只认 `[](url)` 和 http(s) URL，不认 `[[wikilink]]`**，也不做「分隔符 / 大小写 + 子目录相对路径」归一。因此：

- **wikilink 判死 + frontmatter 校验 + 受控词表** 三检由本套件的内置 `llmwiki lint` 承担；
- lychee 等只作为**外链 / HTTP 链接**的补充（若你的库很看重外链状态）。

### 5.2 三检内容

1. **链接判死**（铁律）：`[[wikilink]]` 路径式 / 裸名分别解析 + 归一；`[text](path)` 按源文件目录相对解析；`# anchor` 校验章节存在。
2. **frontmatter 必填**：`title/description/tags/difficulty`；`difficulty` 必须 ∈ 受限枚举。
3. **受控词表**：`categories` 必须落在本库已启用的分类集合。

### 5.3 运行 lint

```bash
llmwiki lint                    #全量（CI / 本地兜底)
llmwiki lint --staged           #仅 Git 暂存区 .md（pre-commit 时用）
llmwiki lint -- files...        #指定文件集
```

退出码：errors == 0 → 0（通过），否则 1（pre-commit / CI 据此阻断）。报告写 `lint-report.json`。

### 5.4 链接铁律（四步归一，务必理解）

1. 用**仓库相对路径**建立文件索引，不用绝对路径（绝对路径的盘符会被 `lower` 破坏）。
2. 目录 + 文件名都**归一再比对**：`_` ↔ `-`、全角 `：` → 、大小写、正斜杠统一。
3. 路径分隔符**一律转正斜杠**（Windows 反斜杠会让键永不匹配）。
4. wikilink 两种写法分别解析：`[[dir/file]]` 路径式按库根相对路径查；`[[basename]]` 裸名按全局 basename 索引查。

> 这条铁律是链接判死的唯一真值，写在套件的 `kb_core.py`，被 lint / ingest / recall 三方共用——**绝不要在各处各写一套**。

### 5.5 隔离历史遗留断链

仓库根的 `.kb-lint-ignore.json` 可登记历史遗留断链正则（每条需附注释说明来源），让基线可达 0；新增断链仍会失败：

```json
[
  "00-Inbox/草稿.md :: 断链 \\[\\[[^]]*\\]\\]"
]
```

---

## 6. 自动化（让体系自己转）

先装刹车再踩油门：先让 lint 自动化（不让新灰尘进库），再批量写、再对外开放。

### 6.1 pre-commit（推荐）

`pre-commit` 挂 `llmwiki lint`（local hook）+ lychee（仅构件 .md），保证「坏内容不进库」。用 `--staged` 过滤提速。

### 6.2 GitHub Actions cron（夜间全量）

见 `llmwiki init` 拷到仓库的 `.github/workflows/kb-lint.yml`，已内置每日 cron 全量 lint。

### 6.3 本地定时兜底（无 GitHub 也一样）

任意 cron / 任务计划程序跑：

```bash
llmwiki lint 2>&1 | tee lint-report.json
llmwiki index                        # 顺带定时重建索引，防忘记
```

> 迁移小贴士：`llmwiki index` 与 `llmwiki lint` 均是幂等哦，放心定时。

---

## 7. 最佳实践与常见坑

| 坑 | 说明 | 对策 |
|----|------|------|
| **改完文档没重建索引** | 新文档永不进入召回 | 每次写完跑 `llmwiki index`；或设每日自动化 |
| **乱建游离 categories** | lint 报 `fm.category` | 先查 `llmwiki.toml` 词表，保持一致（§2.3） |
| **手写时删了 `---`** | frontmatter 解析失败，文档不入索引 | 行级编辑，绝不删分隔符 |
| **把 vendored 文件当正式文档** | 无 frontmatter 被跳过 | 正式文档务必带规范 frontmatter |
| **以为 lychee 能查 wikilink** | 大面积假阳性 | 链接判死只交给 `llmwiki lint` |
| **LLM 未配置以为坏了** | 实际是降级预览 | 配 `LLM_WIKI_API_KEY` 即得完整回答 |

---

## 8. 端到端最小示例（一次走完）

以「会议纪要」为例，从零到可检索：

```bash
# ① 准备库（已有则跳过）
mkdir -p ~/my-notes && cd ~/my-notes
llmwiki init

# ② 按 §2.6 模板写一篇会议纪要，存为 meeting-weekly.md
# ③ 归一（dry-run 预览 → 真正写入）
llmwiki ingest --apply

# ④ 建索引
llmwiki index

# ⑤ 巡检
llmwiki lint

# ⑥ 检索验证
llmwiki query "本周例会行动项" --recall-only --top-k=4

# ⑦ 问答（配了 LLM_WIKI_API_KEY 即返回完整回答）
llmwiki query "本周例会行动项"
```

走完这几步，你就拥有一个**可检索、可问答、可自维护**的个人 LLMWiki 知识库。下一步把它接到微信/企业微信随时查：见姊妹篇《[[llmwiki-tutorial-02-channel]]·渠道接入》。

---

## 相关文档

- [[llmwiki-tutorial-02-channel]]（渠道接入：把知识库接到微信等渠道）
- [[llmwiki-architecture]]（系统架构总览：分层 + 通道抽象）
- [[llmwiki-tutorial-03-quality-tuning]]（检索质量调优：评估、诊断、调优）
- [[obsidian-guide]]（可选：用 Obsidian 作为前端编辑器）
- [[getting-started]]（五步快速上手）
