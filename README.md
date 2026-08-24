# llmwiki-suite

把一堆 Markdown 笔记编成「会生长、能问答」的个人知识库。

源自 Karpathy 的 LLM-wiki 思路：不做每次查询临时切片的 RAG，而是用工具链
**持续编译**笔记——补 frontmatter、建 BM25 + wikilink 图索引、巡检断链，
最后通过 CLI 或微信通道问答。

> **包名 vs 命令名**：PyPI 发布名为 **`llmwiki-suite`**（`llmwiki` 已被占用），
> 安装后命令仍然是 **`llmwiki`**。

## 安装

```bash
pip install llmwiki-suite                          # 核心，零依赖
pip install "llmwiki-suite[wechat]"               # + 微信通道（fastapi/uvicorn）
pip install git+https://github.com/<you>/llmwiki-suite.git   # 从 GitHub 直接装
```

要求 Python >= 3.11。

### 本地开发安装（源码）

```bash
git clone https://github.com/<you>/llmwiki-suite.git
cd llmwiki-suite
pip install -e .                 # 或带微信通道：pip install -e ".[wechat]"
```

## 五步接入你已有的笔记库

```bash
cd ~/my-notes          # 1. 进入你的笔记目录
llmwiki init           # 2. 生成 llmwiki.toml 配置模板
llmwiki ingest         # 3. 补 frontmatter + 规范化 wikilink
llmwiki index          # 4. 建检索索引
llmwiki query "..."    # 5. 检索 / 问答
```

可选：`llmwiki lint`（巡检断链/词表）、`llmwiki eval`（评估召回质量）、
`llmwiki serve`（启动 HTTP 问答服务，需 `wechat` extras）。

## 命令一览

| 命令 | 作用 |
|------|------|
| `llmwiki init` | 在目标库生成 `llmwiki.toml` 模板 + 脚手架（.gitignore / pre-commit / CI） |
| `llmwiki ingest` | 扫描笔记，补齐 frontmatter，规范化 wikilink 命名 |
| `llmwiki index` | 生成 BM25 + wikilink 图检索索引（`kb-index.json`） |
| `llmwiki query "..."` | 召回最相关章节；配置 `LLM_API_KEY` 后生成完整回答 |
| `llmwiki lint` | 巡检：断链、词表越界、命名规范 |
| `llmwiki eval` | 用内置评估集跑 recall@k / MRR |
| `llmwiki serve` | 启动 FastAPI 桥接服务（`/chat` `/recall` `/healthz`） |

所有命令支持 `--repo <path>` 显式指定库路径（默认取当前目录）。

## 配置与密钥

- **库配置**：库根 `llmwiki.toml`（categories 词表、排除目录、模型名等非密钥项）
- **密钥**：只走环境变量（`LLM_API_KEY`、`BRIDGE_TOKEN`、`WECOM_*`、`ILINK_*`），
  本套件不读取任何 `.env` 文件

## 文档

全部文档在 `docs/`，按「入口 → 进阶 → 参考」组织：

| 文档 | 说明 |
|------|------|
| `docs/getting-started.md` | **入口**：五步接入已有笔记库（10 分钟上手） |
| `docs/llmwiki-tutorial-01-system.md` | 体系搭建完整教程：目录规范、Ingest / Query / Lint、自动化 |
| `docs/llmwiki-tutorial-02-channel.md` | 渠道接入：微信 / 企业微信桥接、serve 部署 |
| `docs/llmwiki-tutorial-03-quality-tuning.md` | 检索质量调优：评估集、诊断、调参 |
| `docs/llmwiki-architecture.md` | 系统架构：分层设计、通道抽象 |
| `docs/obsidian-guide.md` | 可选：用 Obsidian 作为前端编辑器 |

建议顺序：getting-started → tutorial-01 → 02/03（按需）→ architecture。

## License

MIT
