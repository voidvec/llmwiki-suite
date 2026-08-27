---
title: "晒出你的 llmwiki 知识库"
labels: ["show-and-tell"]
---

# 晒出你的 llmwiki 知识库

> 用 llmwiki-suite 把你自己的笔记库搬上了「会问答」的轨道？来 Show & Tell 晒出来。
> 最有价值的反馈 = 真实使用案例，这会直接帮到 repo 的召回质量与文档迭代。

## 📁 你搭了什么

- 笔记库主题 / 领域（如「后端工程」「LLM 论文」「项目管理」）
- 规模：多少篇笔记 / 多少字 / 是否有图片
- 用了哪些命令（ingest / index / lint / eval / serve…）

## 🛠 你的接入路径

```bash
# 贴一下你实际跑过的命令（可附关键输出）
llmwiki init
llmwiki ingest
llmwiki query "你的一个真实问题"
```

## ✨ 让人眼前一亮的地方

- 你问过最满意的一个问题 + 它的回答（截图或文本）
- 发现的坑 / 绕过的弯（这就是给维护者的 gold）

## 📊 质量自评（可选）

- `llmwiki eval` 的输出摘要（recall / MRR）
- 或直接说「质量还一般，帮我看看怎么提」

---

> 提交前：确认没贴出密钥 / token 哦（`LLM_WIKI_*` 都是私有的）。