---
title: 配置三层模型与运行入口全景
description: 默认值、llmwiki.toml 与环境变量三层配置，运行入口矩阵与退出码总表
tags: ["配置", "CLI", "环境变量", "退出码"]
difficulty: intermediate
categories: ["参考手册"]
kb_id: KB-04
legacy_kb_id: KB-05
kind: knowledge-base
status: derived
scope: 默认值 / TOML / 环境变量三层配置，repo 解析链，全部运行入口与退出码总表
audience: 部署者、排障者、 CI 维护者
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 配置三层模型与运行入口全景

> **定位**：一次说清「配置从哪来、命令从哪进、失败了返回什么」。不重复 CLI 帮助文本，重点是**优先级、覆盖语义和入口之间的能力差异**。

## 1. 背景

`defaults.py` 开头明确声明三层配置模型：**套件默认 → 用户 `llmwiki.toml` → 环境变量**。但实现上第三层并非「覆盖所有配置」，而是只负责密钥与少数运行时开关；且 `serve` 路径没有把 TOML 配置完整注入（KB-01）。这篇把实际生效范围列清楚。

## 2. 结论速览

| 层 | 载体 | 生效范围 | 优先级 |
|---|---|---|---|
| L1 默认 | `defaults.py` 常量 | 排除目录、词表、别名、门槛、LLM 默认 | 最低 |
| L2 用户库 | `<repo>/llmwiki.toml`（`tomllib`） | 索引文件名、追加排除目录、词表、别名、recall 门槛、LLM base_url/model | 中 |
| L3 环境 | `LLM_WIKI_*`（`_env.getenv`） | 密钥、通道凭据、索引路径覆盖、开关、LLM 超时 | 最高（且多数时候是**唯一来源**） |

- `resolve_repo()` 三级链：`--repo` > CWD 向上找 `.git` > CWD 含任意 `.md` > 抛 `RepoNotFoundError`（`SystemExit` 子类）。**刻意不支持环境变量指定 repo**。
- 9 个 CLI 子命令 + 6 处 `python -m` 模块入口 + 2 个 serve 入口 + 6 个脚本 + 3 个 workflow，共 5 类入口；**模块级入口与 CLI 能力不完全对等**。

## 3. 关键关系

```
CLI 参数（--repo / --apply / --top-k ...）
      │
      ├─> resolve_repo() ──> repo 根 ──> load_config(repo)
      │                                     ├─ 读 llmwiki.toml（解析失败仅告警）
      │                                     ├─ 合并 defaults（追加/覆盖按字段）
      │                                     └─> Config（dataclass）
      │
      └─> _env.getenv() 读密钥/开关（不读 TOML、不读 .env 文件）
                └─> LLM 请求 / 通道适配器 / BRIDGE_TOKEN / 索引路径覆盖
```

## 4. 主体内容

### 4.1 L1：默认常量（`defaults.py`）

| 常量 | 值 |
|---|---|
| `DEFAULT_EXCLUDE_DIRS` | 14 项：`.git .workbuddy Excalidraw Templates scripts .claudian .claude .obsidian .idea .vscode .venv templates node_modules eval_reports` |
| `DEFAULT_CATEGORIES` | 7 类：知识库规范 / 软件架构 / 会议纪要 / 读书笔记 / 工具指南 / 参考手册 / **导航索引**（产物专用，必须保留） |
| `DEFAULT_LLM_BASE_URL` / `MODEL` | `https://api.openai.com/v1` / `gpt-4o-mini` |
| `DEFAULT_MIN_SCORE_PER_TERM` | `1.0`（0 = 关闭） |
| `DEFAULT_LINK_GATE` | `0.5`（0 = 关闭） |
| `DEFAULT_ALIAS_GROUPS` | 5 组 |
| `DEFAULT_MIN_SCORE=0.15` / `DEFAULT_TOP_K=6` | **死常量，全仓无引用**；实际 min_score 0.15 写在 `recall()` 签名，top_k 实际为 4 |

### 4.2 L2：`llmwiki.toml` 合并语义（易错）

| 节 / 键 | 语义 | 陷阱 |
|---|---|---|
| `[repo].index_file` | 标量覆盖 | 默认 `kb-index.json` |
| `[ingest].extra_exclude` | **追加**到默认集合 | 字符串也兼容 |
| `[categories].allowed` | **增量追加去重**（0.1.3 起） | 仅 `replace_default = true` 才整体替换；TOML 模板与多处 docstring 仍写「整体替换」 |
| `[aliases].groups` | **追加** | 每组须 ≥2 个非空字符串 |
| `[recall].min_score_per_term` / `link_gate` | 标量覆盖，0 关闭 | 排除 bool 值 |
| `[llm].model` / `base_url` | 标量覆盖 | **API_KEY 绝不写入文件** |
| 其他节（如 `[llmwiki]`） | **被忽略** | `tests/fixtures/kb/llmwiki.toml` 只有 `[llmwiki] title=...`，等价于无配置 |

`Config` 字段：`repo / index_file / exclude_dirs / categories_allowed / llm_base_url / llm_model / alias_groups / min_score_per_term / link_gate / categories_source`，属性 `index_path = repo / index_file`。`categories_source ∈ {default, toml, index}` 决定 `load_vocab()` 走哪条分支（异常一律回退默认词表，**永不返回 None**）。

`init` 写出的模板含 5 节；`.kb-lint-ignore.json` 是代码支持但仓库内无实例的第四类配置（正则数组，匹配 `"<rel> :: <detail>"`）。

### 4.3 L3：环境变量（`_env.py`）

统一前缀 `LLM_WIKI_`。`getenv(name)` 先查 `LLM_WIKI_<name>`，否则回退旧名并**打印一次**弃用告警（`_WARNED` 去重）。旧名映射 15 条：

- LLM：`LLM_API_KEY / LLM_BASE_URL / LLM_MODEL` → `LLM_WIKI_*`
- 服务：`BRIDGE_TOKEN` → `LLM_WIKI_BRIDGE_TOKEN`；`KB_INDEX`；`ENABLE_ILINK`
- 企微：`WECOM_TOKEN / WECOM_AES_KEY / WECOM_CORPID / WECOM_SECRET / WECOM_AGENTID`
- iLink：`ILINK_BASE_URL / ILINK_CDN_BASE_URL / ILINK_SESSION_FILE / ILINK_BOT_TOKEN`
- 飞书 / Telegram：`FEISHU_*` / `TELEGRAM_*` **不在映射表内**：无前缀旧名仍可读但不告警，行为不一致。

`LLM_WIKI_INGEST_LLM_TOTAL_TIMEOUT`（默认 600）是唯一**绕过 `_env`、直接 `os.environ.get`** 的变量，无旧名兼容。GitHub 观测 token 不走环境变量，走 `--token` 参数。

### 4.4 运行入口矩阵

| 类型 | 入口 | 触发方式 / 前置 |
|---|---|---|
| 主 CLI | `llmwiki = llmwiki.cli:main` | console script；9 子命令 |
| CLI 模块 | `python -m llmwiki.cli` | `sys.exit(main())` |
| 独立模块 | `python -m llmwiki.{ingest,lint,eval_recall}` | 各自 `main()`；**能力不对等，见下** |
| 服务 | `llmwiki serve --host 127.0.0.1 --port 8000` | 需 `[serve]`；缺依赖返回 1 |
| 服务模块 | `python -m llmwiki.channels.wechat_bridge` | 硬编码 127.0.0.1:8000 |
| 离线自检 | `python -m llmwiki.channels.wecom_crypto` | 随机 AESKey 加解密往返 |
| 脚本 | 6 个 `scripts/*.py` | 见 PR-02 |
| CI | `pytest` / `check_recall_baseline.py` / `python -m build` / `twine check` / `obs_daily_snapshot.py` | KB-06 / PR-02 |
| 用户库脚手架 | `lint --staged`（pre-commit）、`kb-lint.yml`（cron 19:00 UTC） | 由 `init` 拷入 |

**CLI 9 子命令及关键参数**：`init(--force)`、`ingest(--apply/--move/--no-llm/--report)`、`index`、`query(--top-k=4/--recall-only/--categories/--tags)`、`lint(--staged/--sync-vocab/files)`、`categories-sync(--apply)`、`eval(--demo/--seed/--seed-limit=20/--queries/--top-k/--min-score=0.15/--prod-top-k=4/--tag/--out-dir/--chart/--retriever-desc)`、`health(--out-dir/--no-json/--no-html)`、`serve(--host/--port)`。除 `serve` 外全部支持 `--repo`。

**独立模块入口的能力差异**（排障时最容易踩）：
- `ingest.main()` **没有 `--no-llm`**，也不传 `use_llm`；`lint.main()` **没有 `--sync-vocab`**。
- `eval_recall.main()` 有 `--min-score-per-term`（CLI 没有），但**丢弃 `run_eval_cmd` 返回值、恒 `return 0`**，退出码 2/3 在此入口全部丢失。
- `wechat_bridge.py` 在 import 时冻结 `BRIDGE_TOKEN`；测试需 `monkeypatch.setattr(wb, "BRIDGE_TOKEN", "")` 而非 `delenv`。

### 4.5 退出码总表

| 值 | 含义 | 来源 |
|---|---|---|
| 0 | 成功 / lint 无 errors / health 恒返回 | 各 `cmd_*` |
| 1 | `query` 缺索引；`serve` 缺 fastapi/uvicorn；**lint 有 errors**；基线脚本指标跌破阈值 | `cli.py:180,329`、`lint.py:208`、`check_recall_baseline.py` |
| 2 | **eval 无评估集**（不产出假分数）；基线脚本运行出错；`smoke` 有 FAIL | `eval_recall.py:367`、脚本 |
| 3 | **eval 索引缺失**（优先于 2）；`--seed` 无索引 | `eval_recall.py:346,361,379` |
| `SystemExit` | `resolve_repo` 找不到库（`RepoNotFoundError`） | `config.py:29` |

> `eval` 无独立「指标未达标」退出码：达标判定由 `scripts/check_recall_baseline.py` 承担（0/1/2）。

## 5. 注意事项与常见误读

1. **TOML 里的 `[categories].allowed` 不是白名单**：默认词表永远在场，除非显式 `replace_default = true`。TOML 模板注释写错了（PR-04）。
2. **密钥只走环境变量**：套件不读取任何 `.env` 文件；但 `GITIGNORE_LINES` 又忽略 `.env`，策略文档还写「密钥进 `.env`」——三处口径不一致，以 `SECURITY.md` / `config.py:8` 为准。
3. **serve 下 TOML 的 `[llm]`、`[recall]`、`[aliases]`、`[ingest].extra_exclude` 失效**：`wechat_bridge.py:77` 只传 `INDEX`。这是部署时最隐蔽的配置陷阱。
4. 不要用 `python -m llmwiki.eval_recall` 做 CI 门禁：退出码被吞。
5. `tests/fixtures/kb/llmwiki.toml` 是空操作配置，不要当作配置示例；看 `testkb/llmwiki.toml` 或 `cli.TOML_TEMPLATE`（但后者注释过时）。
6. `resolve_repo` 只认「最近的 `.git` 或当前目录含 md」，在多库并存时容易指错库；显式 `--repo` 最稳。

## 6. 不确定 / 待补充项

- `httpx2` 是真实包（本地 `.venv` 为 2.12.0，pydantic 发布），但**默认不注册 `httpx` 模块别名**，需显式调用 `alias_httpx()`；`fastapi.testclient`（经 starlette）依赖 `httpx` 模块名，干净环境安装 `[serve]` 后测试是否可用**未实跑验证**（PR-04）。
- `pycryptodome` 未列入 extras，企业微信加解密在干净环境的可用性待验证。
- `scaffold/kb-lint.yml` 的安装地址含未替换占位符 `<you>`，`init` 拷给用户后 CI 推测会失败（待实跑验证，PR-04 P0-6），需确认修复方案。
- `_env` 对 FEISHU_* / TELEGRAM_* 缺少旧名兼容告警，是否有意未定。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/defaults.py` | 全部默认常量与注释 |
| `src/llmwiki/config.py` | `resolve_repo` :55-71、`load_config` :100-166、`Config` :74-97、`load_vocab` :169 |
| `src/llmwiki/_env.py` | `_LEGACY` 15 条、`getenv` :57、`_warn_once` |
| `src/llmwiki/cli.py` | `build_parser` :343-436、`main` :439-455、`TOML_TEMPLATE` :28-56 |
| `src/llmwiki/channels/wechat_bridge.py` | :62/79/85 env 冻结、:77 单参数装配 |
| `src/llmwiki/ingest.py:424` / `lint.py:211` / `eval_recall.py:464` | 独立 `main()` 能力差异 |
| `pyproject.toml` | `[project.scripts]`、extras、pytest 配置 |
| `scripts/check_recall_baseline.py` / `CONTRIBUTING.md` | 退出码与基线命令 |

## 8. 相关主题

- KB-01 系统架构、模块与依赖关系
- KB-06 质量保障体系与门禁
- KB-07 通道与服务层及安全边界
- PR-04 已知偏差与待补充台账
