---
title: "Getting Started：五步接入你已有的笔记库"
description: "llmwiki-suite 的快速上手入口：装包 → init → ingest → index → query。把任意 Markdown 笔记目录变成可检索、可问答、可自维护的个人知识库。"
categories: ['知识库规范']
tags:
  - llmwiki
  - getting-started
  - tutorial
difficulty: "beginner"
estimated_time: "10分钟"
created: "2026-08-24"
updated: "2026-08-24"
version: "1.0"
---

# 五步接入你已有的笔记库

> 目标：**`pip install` 后指向你的笔记目录，五步内完成接入**：装包 → init → ingest → query →（可选）接通道。

---

## 第 0 步：安装

> 当前发布状态：**套件尚未推送到 PyPI**（核名已确认 `llmwiki-suite` 可发布，待正式发布）。
> 因此其他电脑/用户的接入，从 GitHub 直装即可：可装最新 main，且升级即 `pip install --upgrade`（或带 `@<commit/tag>` 锁版本）。

```bash
# 核心（零依赖，纯标准库）—— 从 GitHub 直装（main 分支最新）
pip install "llmwiki-suite @ git+https://github.com/voidvec/llmwiki-suite.git"

# 锁定某个已验证版本（推荐给远端用户）：直接安装某个 commit 的源码
pip install "git+https://github.com/voidvec/llmwiki-suite.git@7be91c9"

# 需要微信/企业微信通道时（额外装 fastapi + uvicorn）
pip install "llmwiki-suite[wechat] @ git+https://github.com/voidvec/llmwiki-suite.git"
```

要求 Python ≥ 3.11（内置 `tomllib` 的下限）。安装后命令是 **`llmwiki`**（注意：包名是 `llmwiki-suite`，PyPI 上 `llmwiki` 已被其他项目占用）。

> **Windows 注意事项**：不要用 `git+file:///D:/...` 本地盘符直装——pip 会把盘符转小写导致 Git 无法解析（已知平台缺陷）。必须走 `git+https://` 或先 `git clone` 再 `pip install .`。

若仓库公开，别的电脑无需账号直接可装；若日后改为私有，远端需先配置 GitHub 认证（`gh auth login` 或 SSH key，并用 `git+ssh://git@github.com/voidvec/llmwiki-suite.git`）。

验证：

```bash
llmwiki --help
```

---

## 第 1 步：进入你的笔记目录并初始化

```bash
cd ~/my-notes            # 你的 Markdown 笔记目录（新建或已有都行）
llmwiki init             # 生成 llmwiki.toml + 拷入脚手架（.gitignore/pre-commit/CI）
```

`llmwiki init` 会：

- 生成 `llmwiki.toml`（三层配置：套件默认 < 本文件 < 环境变量，密钥只走环境变量）；
- 拷入 `.gitignore` 片段（忽略 `kb-index.json` 等产物）、`.pre-commit-config.yaml`、GitHub Actions lint 工作流；
- 在库根 `templates/` 放入**会议纪要 / 读书笔记两份通用模板**。

> `llmwiki.toml` 不配也能跑（纯默认）；想定制受控词表 / 排除目录 / LLM 模型时再编辑它。

---

## 第 2 步：归一并建索引（把 Markdown 变成可检索结构）

```bash
llmwiki ingest            # 先 dry-run 预览（补 frontmatter / 归一文件名 / 查重）
llmwiki ingest --apply    # 确认后真正写入
llmwiki index             # 建 BM25 + wikilink 图索引 → kb-index.json
```

- `ingest` 是**行级编辑**：补缺失的 frontmatter、把 `Weekly_会议纪要.md` 归一为 `weekly-meeting.md`，绝不整篇重写。
- `index` 后产物：`kb-index.json`（检索索引）+ `category-index.md`（自动分类导航页）。

---

## 第 3 步：查询你的知识库

```bash
llmwiki query "本周例会行动项"                 # 召回 + LLM 生成完整回答
llmwiki query "本周例会行动项" --recall-only  # 仅看召回候选（不调 LLM，离线调试）
llmwiki query "哪个文档讲 BM25" --top-k 4     # 显式控制候选数
```

- 配了 `LLM_API_KEY`（OpenAI 兼容端点）→ 返回带来源引用的回答。
- 没配 → 返回「检索片段预览」，**离线也能联调**。

```bash
# 一键巡检知识库健康度（断链 / frontmatter / 词表）
llmwiki lint
```

---

## 第 4 步（可选）：接入微信 / 企业微信

```bash
pip install "llmwiki-suite[wechat] @ git+https://github.com/voidvec/llmwiki-suite.git"
cd ~/mykb
export LLM_API_KEY="sk-xxx"    # 建议；不设则降级预览
export BRIDGE_TOKEN="my-secret"# 建议：保护 /chat /recall
llmwiki serve --host 127.0.0.1 --port 8000
```

- 浏览器打开 `http://127.0.0.1:8000/ilink/webui` → 手机微信扫码 → 绑定个人微信 bot；
- 之后在微信里直接给 bot 发文本，即查即答。
- 企业微信、LLM 厂商切换、排错等详见 [[llmwiki-tutorial-02-channel]]。

---

## 在另一台电脑 / 别人的机器上接入（远端消费方）

> 适用：新机器、同事/朋友的知识库，与第 0～4 步完全一致的 CLI，唯一差异在**安装来源**。

```bash
# 1. 环境
python -m venv .venv && source .venv/bin/activate    # Linux/macOS
# 或 Windows: python -m venv .venv; .venv\Scripts\activate
pip install "llmwiki-suite @ git+https://github.com/voidvec/llmwiki-suite.git"

# 2. 进入他们已有的笔记目录（git 仓库或裸目录均可）
cd ~/their-notes
llmwiki init          # 生成 llmwiki.toml + 拷脚手架（已有不覆盖）
llmwiki ingest        # 先 dry-run 预览，再 --apply 真正写入
llmwiki index         # 建 kb-index.json
llmwiki query "随便问"   # 检索/问答
llmwiki lint          # 健康巡检
llmwiki serve         # 要跑 HTTP 服务时（需 [wechat] extras）
```

要点：

| 事项 | 说明 |
|------|------|
| **任意数量/任意位置** | 套件是「指向库」的 CLI，不是绑死库路径；`--repo <path>` 可切换到任何库，或 `cd` 进库直接用 |
| **Python ≥ 3.11** | 唯一硬依赖（内置 `tomllib`） |
| **配置不落地** | `llmwiki.toml` 随库走；密钥只读环境变量，绝不写进笔记仓库 |
| **私有仓库反向依赖** | 套件公开可直装；若套件仓库设为私有，远端需配认证（SSH key / `gh auth login`）后改用 `git+ssh://`，或为机器单独签发只读 token |
| **CI/pre-commit** | `llmwiki init` 拷入的 `.github/workflows/kb-lint.yml` 与 `.pre-commit-config.yaml` 已内置上游安装命令，双端（新建/既有仓库）共用 |
| **其它库迁移历史** | 别的库没有 `_deprecated/` 那些旧引擎，无需迁移；**不存在「必须带旧文件才能跑」** |
| **升级** | 改完套件跑 `pip install --upgrade "llmwiki-suite @ git+https://..."` 即升级到最新 main |

---

## 3 条铁律（避免踩坑）

1. **改文档后必重建索引**：新增 / 修改任一篇 `.md` 后跑 `llmwiki index`，否则新内容不进入召回。
2. **密钥只走环境变量**：`LLM_API_KEY` / `BRIDGE_TOKEN` / `WECOM_*` / `ILINK_*`，套件不读任何 `.env`。
3. **别乱建游离分类**：`categories` 必须落在 `llmwiki.toml` 词表内，否则 `lint` 报 error。

---

## 相关文档

- [[llmwiki-tutorial-01-system]]（体系搭建完整教程：目录规范、Ingest/Query/Lint、自动化）
- [[llmwiki-tutorial-02-channel]]（渠道接入：微信 / 企业微信）
- [[llmwiki-tutorial-03-quality-tuning]]（检索质量调优：评估、诊断、调参）
- [[llmwiki-architecture]]（系统架构：分层 + 通道抽象）
- [[obsidian-guide]]（可选：用 Obsidian 作为前端编辑器）