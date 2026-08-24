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

```bash
# 核心（零依赖，纯标准库）
pip install llmwiki-suite

# 需要微信/企业微信通道时（额外装 fastapi + uvicorn）
pip install "llmwiki-suite[wechat]"
```

要求 Python ≥ 3.11（内置 `tomllib` 的下限）。安装后命令是 **`llmwiki`**（注意：包名是 `llmwiki-suite`，PyPI 上 `llmwiki` 已被其他项目占用）。

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
pip install "llmwiki-suite[wechat]"
cd ~/mykb
export LLM_API_KEY="sk-xxx"    # 建议；不设则降级预览
export BRIDGE_TOKEN="my-secret"# 建议：保护 /chat /recall
llmwiki serve --host 127.0.0.1 --port 8000
```

- 浏览器打开 `http://127.0.0.1:8000/ilink/webui` → 手机微信扫码 → 绑定个人微信 bot；
- 之后在微信里直接给 bot 发文本，即查即答。
- 企业微信、LLM 厂商切换、排错等详见 [[llmwiki-tutorial-02-channel]]。

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