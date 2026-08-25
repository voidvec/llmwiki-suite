# 另一台电脑 / 别人的知识库：接入 llmwiki-suite

> 目标：**在任意新机器上，把别人的 Markdown 笔记目录变成可检索、可问答、可自维护的知识库**，全程与套件零耦合、无需拷贝旧引擎。

---

## 1. 前提

| 项 | 说明 |
|----|------|
| 套件仓库 | `https://github.com/voidvec/llmwiki-suite`（PUBLIC，当前可直接 clone/直装） |
| Python | ≥ 3.11（唯一硬依赖：内置 `tomllib`） |
| 笔记目录 | 任意含 `.md` 的目录即可（git 仓库或裸目录均可） |

---

## 2. 安装套件（一条命令）

```bash
# 二选一（不必两条都装）：
#   - 只用 query/lint/eval 等核心 → 装第 1 条；
#   - 要跑微信/企业微信渠道 → 装第 2 条（[wechat]，已含核心 + fastapi/uvicorn）。

# 1) 核心（零依赖，纯标准库）—— 从 GitHub 直装 main 分支最新
pip install "llmwiki-suite @ git+https://github.com/voidvec/llmwiki-suite.git"

# 2) 需要微信/企业微信通道时（额外装 fastapi + uvicorn）【必须显式写 [wechat]】
pip install "llmwiki-suite[wechat] @ git+https://github.com/voidvec/llmwiki-suite.git"
```

- 建议在 venv 中安装：`python -m venv .venv && source .venv/bin/activate`（Windows: `.venv\Scripts\activate`）。
- 锁定已验证版本：`pip install "git+https://github.com/voidvec/llmwiki-suite.git@<commit>"`。
- `llmwiki-suite` 尚未推送到 PyPI；若日后发布，则可直接 `pip install llmwiki-suite`。

**Windows 注意事项**：不要用 `git+file:///D:/...` 本地盘符直装——pip 会把盘符转小写导致 Git 无法解析（已知平台缺陷）。必须走 `git+https://` 或先 `git clone` 再 `pip install .`。

验证：`llmwiki --help`。

---

## 3. 接入你的知识库（五步）

```bash
cd ~/their-notes        # 1. 进入已有笔记目录（或新建）
llmwiki init            # 2. 生成 llmwiki.toml + 拷脚手架（.gitignore/pre-commit/CI）
llmwiki ingest          # 3. 先 dry-run 预览（补 frontmatter/归一/查重）
llmwiki ingest --apply  #    确认后真正写入
llmwiki index           # 4. 建 BM25 + wikilink 图索引 → kb-index.json
llmwiki query "随便问"    # 5. 检索 / 问答（配 LLM_WIKI_API_KEY 后生成完整回答）
```

其中第 5 步的 LLM 通过环境变量指定（OpenAI 兼容端点，均可换）：

```bash
export LLM_WIKI_API_KEY="sk-xxx"                          # 必填（否则降级为纯检索预览）
export LLM_WIKI_BASE_URL="https://api.deepseek.com/v1"    # 默认 https://api.openai.com/v1
export LLM_WIKI_MODEL="deepseek-chat"                     # 默认 gpt-4o-mini
```

> 支持任意「OpenAI `/chat/completions` 兼容」的第三方模型：DeepSeek / Qwen（通义）/ Kimi、本地 Ollama / vLLM 等，只要 endpoint 兼容即可，详见 [[llmwiki-tutorial-02-channel]] §2.1。

可选：`llmwiki lint`（健康巡检）、`llmwiki serve`（HTTP 服务，需 `[wechat]` extras）。

所有命令支持 `--repo <path>` 显式指定库；不指定则按 `CWD 向上找 .git → CWD 含 .md` 自动定位。

---

## 4. 多库 / 切换 / 多用户

| 场景 | 做法 |
|------|------|
| 同一台机器管理多个库 | `--repo <path>` 切换，或 `cd` 进对应库直接跑命令 |
| 同事/朋友接入 | 同一条安装命令 + 上面五步，无任何「必须带旧文件」的耦合 |
| 套件改了要升级 | `pip install --upgrade "llmwiki-suite @ git+https://github.com/voidvec/llmwiki-suite.git"` |
| 套件仓库转私有 | 远端先配认证（`gh auth login` / SSH key），改 `git+ssh://git@github.com/voidvec/llmwiki-suite.git` |
| CI / pre-commit | `llmwiki init` 已拷入 `.github/workflows/kb-lint.yml` 与 `.pre-commit-config.yaml`（内部已内置 `pip install llmwiki-suite`） |

---

## 5. 3 条铁律

1. **改完 .md 必重建索引**：`llmwiki index`，否则新内容不进召回。
2. **密钥只走环境变量**：`LLM_WIKI_API_KEY` / `LLM_WIKI_BRIDGE_TOKEN` / `LLM_WIKI_WECOM_*` / `LLM_WIKI_ILINK_*` 一律 env，套件不读 `.env`。
3. **别建游离分类**：`categories` 必须落在 `llmwiki.toml` 词表内，否则 `lint` 报 error。