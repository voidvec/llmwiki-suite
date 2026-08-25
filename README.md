# llmwiki-suite

[![PyPI version](https://img.shields.io/pypi/v/llmwiki-suite.svg)](https://pypi.org/project/llmwiki-suite/)
[![Python](https://img.shields.io/pypi/pyversions/llmwiki-suite.svg)](https://pypi.org/project/llmwiki-suite/)
[![CI](https://github.com/voidvec/llmwiki-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/llmwiki-suite/actions/workflows/ci.yml)
[![Release](https://github.com/voidvec/llmwiki-suite/actions/workflows/release.yml/badge.svg)](https://github.com/voidvec/llmwiki-suite/actions/workflows/release.yml)

把一堆 Markdown 笔记编成「会生长、能问答」的个人知识库。

源自 Karpathy 的 LLM-wiki 思路：不做每次查询临时切片的 RAG，而是用工具链
**持续编译**笔记——补 frontmatter、建 BM25 + wikilink 图索引、巡检断链，
最后通过 CLI 或微信通道问答。

> **包名 vs 命令名**：PyPI 发布名为 **`llmwiki-suite`**（`llmwiki` 这个包名已被其他项目占用），
> 安装后执行命令仍然是 **`llmwiki`** —— 即「装的是 `llmwiki-suite`，用的是 `llmwiki`」。

## 安装

> 已在 PyPI 发布。**推荐直接装带微信渠道的版本**（一条命令搞定核心 + 全部功能）；
> 只看检索/巡检则装核心版即可（零依赖）。

```bash
# 推荐：一条命令装好【全部能力】（核心 + 微信/企业微信通道 fastapi/uvicorn）
pip install "llmwiki-suite[wechat]"

# 轻量：只装核心（ingest / index / query / lint / eval，零第三方依赖）
# pip install llmwiki-suite
```

要求 Python >= 3.11。

### 本地开发安装（源码）

```bash
git clone https://github.com/voidvec/llmwiki-suite.git
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

可选：`llmwiki lint`（巡检断链/词表）、`llmwiki eval`（评估低质量子集并输出诊断）、
`llmwiki serve`（启动 HTTP 问答服务，需 `wechat` extras）。

## 命令一览

| 命令 | 作用 |
|------|------|
| `llmwiki init` | 在目标库生成 `llmwiki.toml` 模板 + 脚手架（.gitignore / pre-commit / CI） |
| `llmwiki ingest` | 扫描笔记，补齐 frontmatter，规范化 wikilink 命名 |
| `llmwiki index` | 生成 BM25 + wikilink 图检索索引（`kb-index.json`） |
| `llmwiki query "..."` | 召回最相关章节；配置 `LLM_WIKI_API_KEY` 后基于召回结果生成完整回答 |
| `llmwiki lint` | 巡检：断链、词表越界、命名规范 |
| `llmwiki eval` | 用内置评估集跑 recall@k / MRR |
| `llmwiki serve` | 启动 FastAPI 桥接服务（`/chat` `/recall` `/healthz`） |

所有命令支持 `--repo <path>` 显式指定库路径（默认取当前目录）。

## 微信渠道接入（个人微信 / 企业微信）

用 `llmwiki serve` 把知识库接到微信，直接发消息问答：

```bash
# ① 已装渠道版则直接可用；否则先补装渠道依赖
pip install "llmwiki-suite[wechat]"

# ② 配置 LLM（OpenAI 兼容端点；只设 KEY 时默认走 OpenAI）
export LLM_WIKI_API_KEY="sk-xxx"
export LLM_WIKI_BASE_URL="https://api.openai.com/v1"        # 不设则默认 OpenAI
export LLM_WIKI_MODEL="gpt-4o-mini"                          # 不设则默认 gpt-4o-mini

export LLM_WIKI_BRIDGE_TOKEN="my-secret"       # 建议：保护 /chat、/recall
llmwiki serve --host 127.0.0.1 --port 8000
```

- **个人微信（推荐，免费官方 iLink 通道）**：浏览器打开
  `http://127.0.0.1:8000/ilink/webui` → 手机微信扫码 → 绑定成功后
  直接在微信里给 bot 发消息即查即答。
- **企业微信**：配置 `LLM_WIKI_WECOM_*` 环境变量后自动启用回调 / 主动推送通道。

### 换 LLM 厂商 / 模型（OpenAI 兼容协议即可）

套件只调 OpenAI 兼容的 `/chat/completions`，**不看厂商名**——任何提供该协议的服务都能用：

| 厂商 | `LLM_WIKI_BASE_URL` | `LLM_WIKI_MODEL` |
|------|---------------------|------------------|
| OpenAI（默认） | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Kimi / Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b`（API_KEY 随便填） |

> 换厂商只需把上面三个变量一起设；只有 OpenAI 时只用 `LLM_WIKI_API_KEY` 即可。
> 支持任意 **OpenAI `/chat/completions` 兼容**的第三方服务（DeepSeek / 通义 / Kimi / 本地 Ollama / vLLM 等），
> 完整对接步骤、会话持久化与排错，详见 [[llmwiki-tutorial-02-channel]]。

## 配置与密钥

- **库配置**：库根 `llmwiki.toml`（categories 词表、排除目录、模型名等非密钥项）
- **密钥**：只走环境变量（`LLM_WIKI_API_KEY`、`LLM_WIKI_BRIDGE_TOKEN`、
  `LLM_WIKI_WECOM_*`、`LLM_WIKI_ILINK_*`），本套件不读取任何 `.env` 文件

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
| `docs/pypi-release-guide.md` | 维护者：发布到 PyPI 的操作指南（注册/2FA/Token/twine） |

建议顺序：getting-started → tutorial-01 → 02/03（按需）→ architecture。

## License

MIT
