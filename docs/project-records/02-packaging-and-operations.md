---
title: 打包分发、发布流程与运维观测
description: 包元数据、PyPI 发布链、运维脚本与 stats 观测数据口径
tags: ["打包", "PyPI", "运维", "观测"]
difficulty: intermediate
categories: ["工具指南"]
record_id: PR-02
legacy_kb_id: KB-09
kind: project-record
status: derived
scope: 包元数据与构建产物、PyPI/GitHub 发布链、6 个运维脚本、stats 观测数据口径（覆盖 2026-09-01 ~ 2026-11-25）与趋势
audience: 发布执行者、维护者、数据分析者
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
relocated: 2026-11-12 方案 C · knowledge-base/ → docs/project-records/
confidence: medium
---

# 打包分发、发布流程与运维观测

> **归档状态（2026-11-12）**：按方案 C 从 `knowledge-base/` 迁至 `docs/project-records/`，属**项目记录 · 打包运维资料（含时点观测数据）**，不是知识层文档。正文记录 2026-11-11 时点状态，未改写；编号已于 2026-11-12 重排为 `PR-02`（旧 `KB-09`），全仓引用已同步更新，映射见 [README.md](README.md) §2。文中「14 篇派生文档」等表述是当时的历史事实，当前结构以 §2 为准，权威口径见 [00-canonical-baseline.md](00-canonical-baseline.md)。


> **定位**：回答「这个包怎么被装到别人机器上、怎么发版、每天在抓什么数据、数据能说明什么」。发布**动作规范**见 `docs/pypi-release-guide.md` / `release-plan.md`，本篇聚焦实际链路与已发生的偏差。

## 1. 背景

项目 2026-08-24 完成 PyPI 核名（`llmwiki` 与 `llmwiki-cli` 均被占用，最终用 **`llmwiki-suite`**），随后建立 CI / pre-commit / release 三条 workflow 与每日曝光快照。当前工作区存在**四套版本号并存**与**陈旧 dist 产物**，发布链路的实际状态需以文件为准而非文档。

## 2. 结论速览

- 包名 `llmwiki-suite`，命令 `llmwiki`（console script `llmwiki.cli:main`），Python ≥3.11，MIT，核心 `dependencies = []`。
- 三组 extras：`serve` 与兼容别名 `wechat` 内容相同（fastapi / uvicorn / httpx2 / qrcode），`dev`（pytest / pre-commit）。
- `MANIFEST.in` 只有 2 行：`include README.md` + `recursive-include docs *.md`；**sdist 不含 scripts/、stats/、.github/、testkb/**。
- 发布：tag `v*` → `python -m build` → `twine check` → `twine upload --skip-existing`（`secrets.PYPI_API_TOKEN`）→ `softprops/action-gh-release@v3` 自动生成 Release Notes。
- 观测：`obs-daily.yml` 每日 01:00 UTC 抓 GitHub + PyPI，落 `stats/llmwiki-obs-*.json` 与 `stats/daily-series.csv`，并自动 commit/push。
- **当前实际状态**：pyproject `0.1.8`、`__init__.py` `0.1.8`、`dist/` 两个 `0.1.8` 产物、egg-info `Version: 0.1.8`、`.venv` editable dist-info `0.1.8` —— **本机四处已与 PyPI / GitHub Release 的 `0.1.8` 一致**（2026-11-26 对齐，见 PR-04 P4-6）；唯 `stats/` 全周期 `version = v0.1.6` 是历史快照，不再更新。`v0.1.7` 与 `v0.1.8` 于 2026-11-26 同日发布（各自 tag、PyPI wheel/sdist、GitHub Release 三处同时落地，推 tag 即触发 `release.yml`）。

## 3. 关键关系

```
源码 src/llmwiki + data/
   ├─ python -m build ──> dist/*.whl（33 文件）+ dist/*.tar.gz（含 docs/、tests/）
   ├─ tag v* ──> release.yml ──> twine upload ──> PyPI ──> GitHub Release
   └─ pip install ──> 用户库 llmwiki init ──> scaffold（pre-commit + kb-lint.yml）

每日 01:00 UTC
   obs_daily_snapshot.py
      ├─ fetch_github_stats.py（4 个 API 请求，匿名 60 次/时）
      ├─ fetch_pypi_stats.py（pypistats /recent + /overall，间隔 ≥1s）
      └─ stats/llmwiki-obs-YYYY-MM-DD.json + stats/daily-series.csv
            └─ git commit "obs(daily): 曝光快照 YYYY-MM-DD" + push
```

## 4. 主体内容

### 4.1 包元数据与产物

`pyproject.toml`：`setuptools>=68`、`version = "0.1.8"`、`readme = README.md`、`license = "MIT"`（PEP 639 SPDX，**不能再加 MIT classifier**，否则 setuptools 报 `InvalidConfigError`）、classifiers 覆盖 Python 3.11–3.14。包数据声明 `data/**/*.{json,toml,md,yaml,yml}` + `data/scaffold/.pre-commit-config.yaml`（其中 `*.toml` 无对应文件，模板是 `cli.py` 内嵌字符串）。

实测 `dist/` 两个 0.1.8 产物（2026-11-26 重建）：wheel **113,499 B / 33 文件**（22 个 .py + 5 个 data + 6 个 dist-info），sdist **229,785 B / 87 条目**（含 `docs/` 递归 32 篇 md、`tests/` 两个 .py）。两处订正历史结论：

- **`setup.cfg` 不是残留旧配置**：sdist 里的那份由 setuptools 构建时自动生成（仓库根从来没有这个文件），0.1.3 时代把它误读成「已删除的遗留物」。
- **sdist 结构已与仓库一致**：`MANIFEST.in` 用 `recursive-include docs *.md`，`tutorials/`、`community/`、`weekly/` 子目录一并入包；0.1.3 时「11 篇扁平 docs/*.md」的偏差已随目录重组自然消失。

### 4.2 发布链路

| 环节 | 实现 | 备注 |
|---|---|---|
| CI 构建校验 | `ci.yml`：`python -m build` + `python -m twine check dist/*` | 4 个 Python 版本矩阵都会跑 |
| tag 触发 | `release.yml`：`push.tags: ["v*"]`，`permissions: contents: write`，Python 3.12 | 无 `environment`、无 concurrency、无 trusted publishing |
| 上传 | `TWINE_USERNAME=__token__` + `TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }}`，`twine upload --skip-existing dist/*` | `--skip-existing` 为兼容本地 v0.1.0 重复 tag |
| Release | `softprops/action-gh-release@v3`，`generate_release_notes: true` | 自动建 GitHub Release |
| 人工指南 | `docs/pypi-release-guide.md` 六步：注册 → **强制 2FA** → project-scoped API Token → `~/.pypirc` 或 env（**禁止 `-u -p` 明文进 shell history**）→ build/twine check → TestPyPI 先行 → 安装验证 | 版本需同时改 `pyproject.toml` 与 `src/llmwiki/__init__.py` |

**已知平台限制**（`docs/RELEASE.md`）：Windows 下 `pip install git+file:///D:/...` 不可用（pip 把盘符转小写 `d:/`，Git for Windows 无法解析）。

### 4.3 六个运维脚本

| 脚本 | 输入 / 输出 | 依赖与错误码 |
|---|---|---|
| `check_recall_baseline.py` | 跑 eval 并断言阈值 / stdout + JSON 快照 | 无网络；0/1/2（KB-06） |
| `fetch_github_stats.py` | `--owner voidvec --repo llmwiki-suite --token --out` → stars/forks/open_issues/open_prs/latest_release | 4 个 GitHub API 请求，timeout 15s，`sleep(0.2)`；HTTP 错误降级为 `__http_error__` / `__net_error__`；三者全 None 才 return 1 |
| `fetch_pypi_stats.py` | `--name --out` → `pypistats.org/api/packages/<name>/{recent,overall}` | `sleep(1.0)`；429 降级；error 且 recent 为空才 return 1 |
| `make_repo_banners.py` | 无参数 → `assets/{banner.png 1280×628, social-preview.png 1600×630, demo-term.png 1360×800}` | **唯一依赖 Pillow 的脚本**（未进 dev extra）；硬编码 `C:/Windows/Fonts`（Linux 必失败） |
| `obs_daily_snapshot.py` | `--pkg/--owner/--repo/--token/--out-dir stats` → 当日 JSON + CSV | 仅标准库；同日重跑覆盖；`_pick()` 新值空则保留旧行值（防 429 冲空） |
| `smoke_feishu_telegram.py` | 无参数 → 6 个 `[PASS]/[FAIL]` 断言 | 不触网，stub `send_text` / `_api`；0/1 |

### 4.4 观测数据口径（`stats/`）

85 个 `llmwiki-obs-*.json` + `daily-series.csv`，覆盖 **2026-09-01 → 2026-11-25**，缺 2026-09-02。

CSV 8 列：`date, pypi_total_downloads, pypi_recent_downloads, stars, forks, open_issues, open_prs, version`。**列名有陷阱**：

- `pypi_total_downloads` ← `pypi.last_month`（**滚动 30 天**，不是累计总量）
- `pypi_recent_downloads` ← `pypi.last_day`（当日）
- `version` ← `github.latest_release`

JSON 顶层：`date / fetched_at / pypi{package,last_day,last_week,last_month,error} / github{stars,forks,open_issues,open_prs,latest_release,latest_release_at,error}`。文件大小直接反映降级状态：473 B（429 但取上次成功值 569/94）、455 B（pypi 全 null）、431 B（issues-query 降级）、409–412 B（正常）。

**趋势**：stars / forks / open_issues / open_prs **全程 0**；`version` 全程 `v0.1.6`；`latest_release_at` 恒定 `2026-08-31T06:54:50Z`；`last_month` 从 569 升至峰值 **696（09-23）**，再跌至 **94（10-06 起恒定）**；`last_day` 多为 0–3，约 15 天整行空值（429 且无旧值兜底）。

### 4.5 降级分层设计

1. 抓取层：单项失败置 `None` + `error` 字符串，不抛异常；
2. 汇总层：两侧 error 都保留进 JSON，全失败才 return 1；
3. CSV 层：`_pick()` 新值空则沿用旧行值（工作日志记录这是修复「429 重跑把 569/94 冲空」的真实 bug）；同日重跑先删同日旧行再追加（幂等）；
4. workflow 层：`git diff --cached --quiet` 判空，无变更跳过提交。

## 5. 注意事项与常见误读

1. **不要按「累计下载」解读 CSV**：`696→534→99` 是滚动窗口与上游数据变化，不是总量下降。
2. **`open_prs` 不是真实 PR 数**：`fetch_github_stats.py` 用 `per_page=1` 后取 `len(pulls)`，恒为 0 或 1；因此「无外部 PR」的结论应同时用 `open_issues` 与人工核对佐证。
3. **仓库内 2026-09-05~11-25 存在逐日 `obs(daily)` 提交**，但 11-06 之前的 `stats/` 文件是否由 workflow 真实逐日生成待验证：除 09-01（`fetched_at +0800`、手工运行）外，65 个 JSON 与 CSV 的 mtime 全部为 `2026-11-07 12:00`、`fetched_at` 全为 `+0000`，推测为一次批量回填（待验证）；11-07 及以后的快照由远端逐日提交补齐，mtime 未核验；缺 09-02。
4. **`dist/` 被 `.gitignore` 忽略却留在工作区**：2026-11-26 已重建为 0.1.8（此前停在 0.1.3）；本地 `twine check dist/*` 会同时校验目录内所有产物，别再往里放旧包。
5. **版本号有多个落点，`pyproject.toml` 才是唯一真源**：`llmwiki --version` 读 `src/llmwiki/__init__.py` 的 `__version__`，镜像/文档示例另算。改动后要核对四处：pyproject、`__init__`、egg-info、`.venv` 的 editable dist-info（后两者由 `python -m build` / `pip install -e .` 生成，不手改）。
5. `httpx2>=2.0` 是**真实存在的包**（本地 `.venv` 为 2.12.0，pydantic 发布的 httpx 后继），不是笔误；但其默认不注册 `httpx` 模块别名，需实测干净环境（PR-04）。
6. `scaffold/kb-lint.yml` 的 `pip install git+https://github.com/<you>/llmwiki-suite.git` 含未替换占位符；用户 `init` 后该 CI 必失败。
7. `fetch_pypi_stats.py` docstring 的 `--since/--days` 未实现，数据源写成 `/overview`（实际 `/overall`）；`make_repo_banners.py` docstring 写 `demo-usage.png 1400x760`（实际 `demo-term.png 1360x800`）。

## 6. 不确定 / 待补充项

- 未联网核验 PyPI 上的下载量与 GitHub star / issue 走势；本文趋势结论只基于仓库内 `stats/` 快照（覆盖 2026-09-01 ~ 2026-11-25）；版本事实已于 2026-11-26 定点核验（PyPI 元数据 + GitHub Release）。
- HN 发布（计划 2026-09-22）、W9 pivot / 止损决策：仓库内无记录（PR-03 / PR-04 P3）。`v0.1.7` 已于 2026-11-26 发布，不再属于此类。
- `release.yml` 依赖长期 `PYPI_API_TOKEN`（非 trusted publishing），是否需迁移未定。
- `obs-daily.yml` 无 `concurrency`、无 push 前 `git pull`，并发推送可能失败；未验证。
- 工作日志 `.workbuddy/memory/2026-08-27.md` 记录 fine-grained GITHUB_TOKEN 对仓库无写权限（HTTP 403），会影响 `obs-daily.yml` 的 `contents: write` 与仓库元数据设置，是否已修复未知。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `pyproject.toml` / `MANIFEST.in` / `LICENSE` / `.mailmap` | 元数据、extras、包数据、作者 |
| `dist/llmwiki_suite-0.1.8.*` | wheel 33 文件 / sdist 87 条目（2026-11-26 实测） |
| `src/llmwiki_suite.egg-info/PKG-INFO` | `Version: 0.1.8` |
| `.github/workflows/{ci,release,obs-daily}.yml` | 构建校验、tag 发布、cron `"0 1 * * *"` 与提交脚本 |
| `scripts/*.py` 六个 | 参数、API、限流、退出码 |
| `stats/daily-series.csv`、`stats/llmwiki-obs-2026-09-01.json` … `2026-11-25.json` | 字段口径、85 天数值、降级标记、mtime 痕迹 |
| `docs/RELEASE.md` / `docs/pypi-release-guide.md` / `docs/release-plan.md` | 核名、Windows 限制、六步发布指南、W4 执行单 |
| `.workbuddy/memory/2026-08-31.md` | 429 冲空 bug 修复、门禁实测记录 |

## 8. 相关主题

- KB-04 配置三层模型与运行入口
- KB-06 质量保障体系与门禁
- PR-03 演进历程与当前状态
- PR-04 已知偏差与待补充台账
