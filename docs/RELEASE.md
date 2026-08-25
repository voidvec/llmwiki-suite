---
title: "发布检查清单（Pre-Release Checklist）"
description: "llmwiki-suite 发布 PyPI 前的核名、构建、安装链路验证记录（M6 后半）"
created: "2026-08-24"
status: "checklist"
---

# 发布检查清单（Pre-Release Checklist）

> 对应 S2 里程碑 M6 后半：`pip install git+file://` 直装验证 + PyPI 发布名最终核名。

## 1. PyPI 发布名核名（2026-08-24 最终确认）

| 候选名 | 状态 | 证据 |
|--------|------|------|
| `llmwiki` | ❌ 已被占用 | PyPI 已存在 v0.9.0（Hosuke 的 LLMBase） |
| `llmwiki-cli` | ❌ 已被占用 | 已被 ktrysmt 占用 |
| **`llmwiki-suite`** | ✅ **可发布** | `https://pypi.org/project/llmwiki-suite/` → 404；JSON API `https://pypi.org/pypi/llmwiki-suite/json` → `{"message": "Not Found"}` |

- 发布名：**`llmwiki-suite`**，CLI 命令仍为 `llmwiki`（见 README「包名 vs 命令名」）。
- PyPI 项目注册采用**先发布后核名**流程：实际占用发生在上传 wheel 时，因此发布名以本次核名为准，`twine upload` 前若冲突需再核。

## 2. 构建产物验证（sdist + wheel）

```bash
python -m build
```

产物：
- `dist/llmwiki_suite-0.1.0.tar.gz`（48 文件，含 6 篇 docs + scaffold 2 文件 + README）
- `dist/llmwiki_suite-0.1.0-py3-none-any.whl`（26 文件）

关键内容断言（wheel）：
- `llmwiki/channels/*`：channel_base / ilink_adapter / wechat_bridge / wecom_adapter / wecom_crypto ✅
- `llmwiki/data/scaffold/.pre-commit-config.yaml` ✅（M6 打包修复：隐藏文件显式入包）
- `llmwiki/data/templates/` + `eval_queries.json` ✅

## 3. 分发链路验证（clean venv）

| 验证项 | 命令 | 结果 |
|--------|------|------|
| wheel 安装 | `pip install dist/llmwiki_suite-0.1.0-py3-none-any.whl` | ✅ CLI 可用 `llmwiki --version` → 0.1.0 |
| 五步工作流 | `init → ingest --apply → index → query --recall-only → eval` | ✅ 全通（脚手架正确落到测试库，`.pre-commit-config.yaml` 来自 wheel 内 data） |
| wechat extras | `pip install "llmwiki-suite[wechat]"` | ✅ fastapi 0.141.1 / uvicorn 0.52.4 |
| serve 端点 | `/healthz`、`/recall`(POST)、`/chat`(POST) | ✅ 均 200；`/recall` 返回候选含 `index_stale:null`；无 LLM 密钥时 `/chat` 降级为片段预览 |
| git 检出源码树安装 | `git clone <repo> && pip install .` | ✅ 构建 wheel + 安装成功（等价 GitHub 直装链路） |

### 已知平台限制（非缺陷）

**Windows 下 `pip install git+file:///D:/...` 不可用**：pip 会把 `file://` URL 的盘符转小写（`d:/`），Git for Windows 无法解析小写盘符路径，报
`fatal: '/d:/...' does not appear to be a git repository`。此为 pip + Git-for-Windows 的已知组合问题，与套件本身无关。真实 GitHub 直装走 `git+https://`，Windows 下无此问题。

## 4. 回归基线

- 套件 testkb：`recall@4 = 100%`，`MRR@4 = 1.0`（与 P5 基线一致，M6 零行为变化）
- 个人知识库 57 条评估集：`recall@4 = 100%`，`MRR@4 = 0.9605`（P5 后基线）

## 5. 发布前待办（后续）

1. 配置套件仓库 GitHub remote（当前无 remote，所有提交都在本地 main）；
2. `twine check dist/*` + `twine upload`（需 PyPI 账号令牌，走 CI 优先）；
3. GitHub 直装 `pip install git+https://github.com/<org>/llmwiki-suite.git` 实测（跨平台最接近真实用户路径）。
