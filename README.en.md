# llmwiki-suite

<p align="center">
  <img src="assets/banner.png" alt="llmwiki-suite — LLM-compiled personal wiki toolkit" width="100%"/>
</p>

> 🌐 English · [中文](README.md)
>
> Turn a pile of Markdown notes into a personal knowledge base that **grows and answers questions**.

[![PyPI version](https://img.shields.io/pypi/v/llmwiki-suite.svg)](https://pypi.org/project/llmwiki-suite/)
[![Python](https://img.shields.io/pypi/pyversions/llmwiki-suite.svg)](https://pypi.org/project/llmwiki-suite/)
[![CI](https://github.com/voidvec/llmwiki-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/llmwiki-suite/actions/workflows/ci.yml)
[![Release](https://github.com/voidvec/llmwiki-suite/actions/workflows/release.yml/badge.svg)](https://github.com/voidvec/llmwiki-suite/actions/workflows/release.yml)
[![License](https://img.shields.io/github/license/voidvec/llmwiki-suite)](LICENSE)

Inspired by Karpathy's LLM-wiki idea: instead of ad-hoc RAG slicing at query time,
this toolkit **continuously compiles** your notes — backfills frontmatter, builds a
BM25 + wikilink-graph index, lints broken links — and then answers via CLI or a
WeChat / WeCom / Feishu / Telegram channel.

> **Package name vs command name**: on PyPI this is **`llmwiki-suite`** (the bare
> `llmwiki` name is taken by another project), but the installed command is still
> **`llmwiki`** — you install `llmwiki-suite`, and run `llmwiki`.

## Install

> Published on PyPI. **Recommended: install the `serve` edition** (core + the
> fastapi/uvicorn runtime shared by all channels — WeChat / WeCom / Feishu / Telegram);
> for retrieval/lint only, the zero-dependency core works.

```bash
# Recommended: everything (core + channel bridge fastapi/uvicorn)
pip install "llmwiki-suite[serve]"

# Lightweight: core only (ingest/index/query/lint/eval, zero third-party deps)
# pip install llmwiki-suite
```

Requires Python >= 3.11.

### Local development install (from source)

Use a project-level virtualenv (mirrors CI, keeps deps isolated):

```bash
git clone https://github.com/voidvec/llmwiki-suite.git
cd llmwiki-suite
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[wechat,dev]"       # all channels + test/pre-commit deps
pre-commit install                   # optional but recommended
```

## Five steps to onboard your notes

```bash
cd ~/my-notes          # 1. enter your notes dir
llmwiki init           # 2. generate llmwiki.toml template
llmwiki ingest         # 3. backfill frontmatter + normalize wikilinks
llmwiki index          # 4. build retrieval index
llmwiki query "..."    # 5. retrieve / Q&A
```

Optional: `llmwiki lint` (broken links/vocab), `llmwiki eval` (recall@k / MRR
quality evaluation), `llmwiki serve` (HTTP chat bridge, needs `serve` extras).

## Commands

| Command | Purpose |
|---------|---------|
| `llmwiki init` | Generate `llmwiki.toml` template + scaffold (.gitignore / pre-commit / CI) |
| `llmwiki ingest` | Scan notes, backfill frontmatter, normalize wikilink naming |
| `llmwiki index` | Build BM25 + wikilink-graph retrieval index (`kb-index.json`) |
| `llmwiki query "..."` | Retrieve most relevant sections; generate a full answer when `LLM_WIKI_API_KEY` is set |
| `llmwiki lint` | Checks: broken links, vocab violations, naming conventions |
| `llmwiki categories-sync` | Derive all categories actually used and write back to `llmwiki.toml` (`--apply` to write) |
| `llmwiki eval` | Run recall@k / MRR against `<repo>/eval_queries.json`; `--seed` samples and writes a first eval set, `--demo` runs the built-in demo set (`--chart` outputs a self-contained SVG) |
| `llmwiki serve` | Start FastAPI bridge (`/chat` `/recall` `/healthz`) |

All commands accept `--repo <path>` to target a specific knowledge base (default: current dir).

## Channels (WeChat / WeCom / Feishu / Telegram)

Wire your knowledge base to instant messaging with `llmwiki serve`:

```bash
# ① channel edition installed already; otherwise install extras
pip install "llmwiki-suite[serve]"

# ② configure the LLM (OpenAI-compatible endpoint; KEY alone defaults to OpenAI)
export LLM_WIKI_API_KEY="sk-xxx"
export LLM_WIKI_BASE_URL="https://api.openai.com/v1"        # default OpenAI
export LLM_WIKI_MODEL="gpt-4o-mini"                          # default gpt-4o-mini

export LLM_WIKI_BRIDGE_TOKEN="my-secret"       # optional: protect the Q&A endpoint (can ignore for local channel testing)
llmwiki serve --host 127.0.0.1 --port 8000
```

- **Personal WeChat (recommended):** open `http://127.0.0.1:8000/ilink/webui` in a
  browser, scan the QR with your phone WeChat, and chat with the bot directly.
- **WeCom:** set the `LLM_WIKI_WECOM_*` env vars to enable callback/push channels.
- **Feishu (Lark):** set `LLM_WIKI_FEISHU_APP_ID` / `LLM_WIKI_FEISHU_APP_SECRET`
  (optionally `LLM_WIKI_FEISHU_VERIFY_TOKEN` for event signature verification);
  in the Feishu open platform point the event-subscription callback URL at
  `https://<your-domain>/feishu/callback` (the challenge is answered automatically).
- **Telegram:** create a bot with @BotFather, set `LLM_WIKI_TELEGRAM_BOT_TOKEN`,
  and point the webhook at `https://<your-domain>/telegram/callback`
  (`setWebhook`; `LLM_WIKI_TELEGRAM_SECRET_TOKEN` optionally guards the callback).

> **Routes are always registered**: at startup the bridge unconditionally mounts all
> four channel routes (`/ilink/*`, `/wecom/*`, `/feishu/callback`, `/telegram/callback`);
> missing credentials return a readable `hint` (no 404). Check each channel's
> `configured / enabled` status at `http://127.0.0.1:8000/healthz`. Channel callbacks
> do not use `LLM_WIKI_BRIDGE_TOKEN`. Telegram webhook needs a public-facing URL
> (frp / ngrok / Tencent Cloud Lighthouse reverse-proxy to 8000).

### Switching LLM providers / models (any OpenAI-compatible protocol)

The toolkit only calls OpenAI-compatible `/chat/completions` — it ignores vendor names:

| Vendor | `LLM_WIKI_BASE_URL` | `LLM_WIKI_MODEL` |
|--------|----------------------|------------------|
| OpenAI (default) | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Alibaba Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Kimi / Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Local Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` (any API key) |

> Any OpenAI `/chat/completions`-compatible service works (DeepSeek / Qwen / Kimi /
> local Ollama / vLLM, etc.). Full setup, session persistence and troubleshooting:
> see `docs/llmwiki-tutorial-02-channel.md`.

## Configuration & secrets

- **Knowledge base config**: `<kb>/llmwiki.toml` (categories vocab, exclude dirs, model name... — no secrets)
- **Secrets**: environment variables only (`LLM_WIKI_API_KEY`, `LLM_WIKI_BRIDGE_TOKEN` (optional),
  `LLM_WIKI_WECOM_*`, `LLM_WIKI_ILINK_*`, `LLM_WIKI_FEISHU_*`,
  `LLM_WIKI_TELEGRAM_*`). This toolkit never reads `.env` files.

## Documentation

All docs live in `docs/`, organized entry → advanced → reference:

| Doc | What it covers |
|-----|----------------|
| `docs/getting-started.md` | **Entry**: onboard an existing notes library in 10 minutes |
| `docs/llmwiki-tutorial-01-system.md` | Full architecture guide: layout, Ingest / Query / Lint, automation |
| `docs/llmwiki-tutorial-02-channel.md` | Channels: WeChat / WeCom bridge, serve deployment |
| `docs/llmwiki-tutorial-03-quality-tuning.md` | Retrieval tuning: eval sets, diagnosis, parameter tuning |
| `docs/llmwiki-eval.md` | **Command reference**: eval CLI options, eval-set schema, report fields, metrics |
| `docs/llmwiki-evolution-roadmap.md` | **Roadmap**: from passive Q&A to a self-evolving knowledge base (L0→L3) |
| `docs/llmwiki-architecture.md` | System architecture: layered design, channel abstraction |
| `docs/obsidian-guide.md` | Optional: use Obsidian as frontend editor |
| `docs/pypi-release-guide.md` | Maintainers: PyPI publishing guide (register / 2FA / token / twine) |

Suggested order: getting-started → tutorial-01 → 02/03 (as needed) → architecture.

## License

MIT

---

## Author & official account

Author: [voidvec](https://github.com/voidvec)

The author writes (in Chinese) about LLM / RAG / knowledge-base engineering,
the evolution of this toolkit (from L0 passive Q&A to L3 self-evolution), and
open-source journeys from 0 to 1.

<p align="center">
  <img src="assets/qrcode-wechat-placeholder.png" alt="WeChat official account QR (replace me)" width="160"/>
  <br/>
  Follow via WeChat: **公众号名待填** (QR placeholder, replace with real one)
</p>
