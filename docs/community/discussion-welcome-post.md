# 👋 欢迎来到 llmwiki-suite 社区

这里是把 **纯 Markdown 笔记「编译」成会问答的个人知识库** 的项目。
不是每次查询临时切片的 RAG，而是由工具链持续编译：补 frontmatter、建
BM25 + wikilink 图索引、巡检断链，最后在微信 / 企微 / 飞书 / Telegram 里直接问。

## 快速开始

```bash
pip install "llmwiki-suite[serve]"
cd ~/my-notes
llmwiki init && llmwiki ingest && llmwiki index
llmwiki query "你的第一个问题"
```

完整入门见文档站的 [Getting Started](../../docs/getting-started.md)。

## 在 Discussions 里你可以

| 分类 | 能干嘛 |
|------|--------|
| **Announcements** | 只读：版本 / 路线图 / 维护公告 |
| **General** | 随便聊：想法、疑问、技术讨论 |
| **Ideas** | 提新功能点子（先搜 +1，避免重复） |
| **Q&A** | 使用 / 部署问题（**提问前先看 docs/**） |
| **Show & tell** | 晒你的知识库接入过程（模板欢迎用） |
| **Polls** | 小投票（路线图优先级等） |

## 想参与开发？

- [CONTRIBUTING](../../CONTRIBUTING.md) — 开发环境、测试、提交规范、PR 流程
- [SECURITY](../../SECURITY.md) — 漏洞报告、密钥与 env 规范
- 心法：**先搜索，后提问**；**有问题先看文档**（`docs/` 自洽、可能是你漏了某步）。

## 公众号

关注我的公众号，持续输出：
- LLM / RAG / 知识库第一手踩坑记录
- 这套工具链的演进连载（L0 被动问答 → L3 自进化）
- 开源项目从 0 到 1 的完整复盘

<!-- 二维码占位：将下方 img 换成真实公众号二维码 -->
<p align="center">
  <img src="../assets/qrcode-wechat-placeholder.png" alt="公众号二维码" width="160"/>
</p>

> 求个 ⭐ Star，让更多人看到这个项目。 🙏