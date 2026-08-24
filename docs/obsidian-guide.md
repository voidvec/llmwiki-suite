---
title: "用 Obsidian 编辑 LLMWiki 知识库（可选前端配套指南）"
description: "LLMWiki 体系零编辑器依赖，Obsidian 只是可选的 Markdown 前端工具。说明用 Obsidian 编辑知识库时的规范输入（frontmatter/wikilink/文件命名）、插件分层使用建议、模板关系与安全注意（local-rest-api 明文密钥）。"
categories: ['知识库规范']
tags:
  - llmwiki
  - obsidian
  - frontmatter
  - wikilink
  - tools
difficulty: "beginner"
estimated_time: "15分钟"
created: "2026-08-20"
updated: "2026-08-20"
version: "1.0"
---

# 用 Obsidian 编辑 LLMWiki 知识库（可选前端配套指南）

> **定位：可选的**前端配套指南。LLMWiki 体系的全部核心——文档规范、索引、检索、巡检——都在「Markdown 文件 + ```` 工具链」里，**不依赖任何编辑器**。用 VS Code、vim 甚至记事本都能完整工作。
> 如果你已经在用 / 想用 Obsidian，本文告诉你如何**让前端工具服务于体系规范，而不是破坏它**。

---

## 1. 为什么这篇是「可选」的

| 体系组成部分 | 是否依赖 Obsidian |
|-------------|------------------|
| frontmatter + 正文规范 | ❌ 纯 Markdown |
| `kb-index.json` / `category-index.md` | ❌ 由 `llmwiki index` 生成 |
| 检索 / 问答 | ❌ 由 `llmwiki query` 承担 |
| lint 巡检 | ❌ 由 `llmwiki lint` 承担 |
| **Obsidian** | 只是**前端编辑工具**，零依赖 |

一句话：Obsidian 是「用起来更舒服的编辑器」，不是体系组件。它**不参与**索引、检索、巡检任何一环；它只是碰巧和体系一样以 Markdown + wikilink 为底层格式，所以天然契合。

体系搭建流程见 [[llmwiki-tutorial-01-system]]；本文只覆盖「用 Obsidian 编辑」这一件事。

---

## 2. 打开知识库（vault）

用 Obsidian 的「打开文件夹作为仓库（vault）」直接选择知识库**仓库根目录**即可：

```
知识库仓库/
├── NN-xxx/            # 分类目录
├── docs/              # 方法论文档（本文在这里）
├── ``           # LLMWiki 工具链
├── kb-index.json      # 检索索引（自动生成）
└── category-index.md  # 分类导航页（自动生成）
```

Obsidian 会在仓库根创建 `.obsidian/`（存放配置与插件）。**该目录已被 `.gitignore` 忽略**，不会进入 git——这是刻意配置，见 §5 安全注意。

---

## 3. 编辑规范：输入侧对齐体系

体系对文档的硬约束只有三条，Obsidian 编辑时**不要绕过**它们：

### 3.1 frontmatter：首尾 `---` 不能删

每份文档必须以 YAML 头开头。在 Obsidian 里编辑时，注意：

- **不要删掉首尾 `---`**——那是 frontmatter 的边界，删了文档不入索引；
- Obsidian 的「Properties」面板看到的字段就是 frontmatter，两种编辑方式等价，改完以文件内容为准；
- 必填四项 `title / description / tags / difficulty` 缺一会被 lint 判 error（见 [[llmwiki-tutorial-01-system]] §2.2）。

### 3.2 wikilink：两种写法都认，但用「路径式」更稳

| 写法 | 示例 | 说明 |
|------|------|------|
| 路径式 | `[[NN-xxx/主题文档]]` | 含目录层级，跨目录唯一 |
| 裸名式 | `[[主题文档]]` | 按全局文件名跳转（Obsidian 语义） |

两类写法 lint 都按「归一 + 分隔符 + 大小写不敏感」判活（见 [[llmwiki-tutorial-01-system]] §2.5）。**建议正文里用路径式**：重名文件多时不会歧义，且 lint 解析更直接。

### 3.3 文件命名：交给归一规则，手写时自觉遵守

- 全小写；空格 / 下划线 `_` → 连字符 `-`；全角冒号 `：` → `-`；
- 中文原样保留。

Obsidian 新文件默认带空格（如 `Untitled 1.md`），记得按规范改名，或直接让 ``llmwiki ingest --apply`` 归一（见 [[llmwiki-tutorial-01-system]] §3.2）。

---

## 4. 插件清单与分层使用建议

当前仓库 `.obsidian/community-plugins.json` 启用 11 个插件，按与体系的协同度分三层：

### 4.1 体系协同（建议了解用法）— 3 个

| 插件 | 用途 | 与体系的关系 |
|------|------|-------------|
| **templater** | 新建文档时套模板自动填 frontmatter | 直接服务 §2.2 规范：把必填四项固化进模板，从源头杜绝漏字段 |
| **obsidian-git** | 库内直接 commit / push | 和体系「带 git 的 markdown 仓库」心智模型一致，编辑即提交 |
| **local-rest-api** | 暴露本地 HTTP 接口读写 vault | 供外部桥接（如微信渠道）以文件系统外的路径访问知识库 |

### 4.2 内容增强（知道即可）— 1 个

- **dataview**：库内做动态查询 / 聚合视图（如「列出某分类下所有文档」）。**仅展示层**，不影响体系检索，也不进索引。

### 4.3 纯体验（不影响体系，按喜好用）— 7 个

realclaudian、excalidraw（画图）、quickadd、ace-code-editor、code-styler、table-editor、file-explorer-plus。这些只影响编辑体验，与规范、索引、检索无关，本文不展开。

---

## 5. 安全注意：local-rest-api 的明文密钥

`.obsidian/plugins/obsidian-local-rest-api/data.json` 中**明文存放 API key 与私钥**（默认端口 `27124`）。当前风险可控：

- `.obsidian/` 已被 `.gitignore` 忽略，`git status` 显示 **0 个文件被跟踪** → 密钥不会入库；
- 但**整个 `.obsidian/` 目录被复制**（换机器、打包分享 vault、压缩包发给他人）时会**连带携带明文密钥**。

规避动作：

- 换机器时不要整目录复制 `.obsidian/`，只复制 `community-plugins.json` + 需要的插件配置；
- 如果未来要把 vault 分享给他人，先删除 `obsidian-local-rest-api` 插件目录或其中的 `data.json`。

---

## 6. 模板与 templater 的关系

`Templates/` 目录（仓库根）存放 templater 模板，配置指向 `templates_folder`。

> **修复记录（2026-08-20）**：templater 的 `templates_folder` 曾配置为小写 `"templates"`，与实际目录 `Templates/` **大小写不匹配**——Windows 大小写不敏感所以本地不报错，但 vault 换到 Linux/macOS 或分享给他人时模板功能会失效。**已修复**：配置改为 `"Templates"`，与目录完全一致。

模板文件本身可按需定制：`llmwiki init` 会向库根 `templates/` 拷入**通用会议纪要 / 读书笔记模板**（见 [[llmwiki-tutorial-01-system]] §2.6），在此基础上按你自己的主题扩展即可。

---

## 7. 一句话总结

> Obsidian 是体系的**可选前端**：用它的模板、双链、git 插件提升编辑体验，但**规范（frontmatter/wikilink/命名）由体系说了算**，前端只负责让输入更顺。任何编辑行为都不应绕过 §3 的三条硬约束。

相关文档：

- [[llmwiki-tutorial-01-system]]（体系搭建教程，先读这篇）
- [[llmwiki-tutorial-02-channel]]（渠道接入）
- [[llmwiki-tutorial-03-quality-tuning]]（检索质量调优）
