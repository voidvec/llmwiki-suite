---
title: "发布到 PyPI 操作指南"
description: "从 pypi.org 注册、开 2FA、建 API Token，到本地 twine upload 的完整发布流程"
categories: ['知识库规范']
tags:
  - llmwiki
  - pypi
  - release
difficulty: "intermediate"
estimated_time: "15分钟"
created: "2026-08-25"
updated: "2026-11-26"
---

# 发布到 PyPI 操作指南

> 目标：把 `llmwiki-suite` 从「GitHub 直装」升级为「PyPI 可 `pip install llmwiki-suite`」。
> 前置：`pyproject.toml` 已就绪（含 `[project.optional-dependencies] serve`；`wechat` 为 0.1.5 前的兼容旧名）、构建/校验工具链已装（`build` + `twine`）、`dist/` 已产出通过 `twine check`。

---

## 第 1 步：在 pypi.org 注册账号

1. 打开 https://pypi.org/account/register/ 注册（用户名即账号，邮箱需验证）；
2. 登录后用 **GitHub / Google** 账号也可（Auth0 第三方登录，等价）；
3. 注册完成后先完善 Profile：
   - **Name / Display name**：填 `Luca`（与你 GitHub 保持一致，包页会显示发布者名）；
   - **Author / Maintainer 页**：邮箱建议用 `vilas900420@gmail.com`（与 git 身份一致，方便 DMCA / 安全联系）。

---

## 第 2 步：开启双因素认证（2FA）+ 生成 API Token（必须）

⚠️ **PyPI 现在强制 2FA**：2024 年起新用户/敏感操作必须开 2FA；且**密码登录 upload 已被禁用**，只认 API Token。因此必须先开 2FA：

1. 打开 https://pypi.org/manage/account/two-factor/ → **Enable two-factor auth**；
2. 推荐 **Authenticator app（TOTP）**：扫码绑定（Authy / Google Authenticator / 1Password 均可）；
   - 备份 2FA **恢复码**（Reusable recovery codes），抄好放安全处——丢了账号就进不去了。
3. 开启后，再到 **API tokens** 页：https://pypi.org/manage/account/token/
4. 点 **Add API token**：
   - **Token name**：填写用途，如 `llmwiki-suite-upload`；
   - **Scope**：选 **Project: llmwiki-suite**（最佳实践：只给这一个项目，不要选「整个账号」）；
   - 选中后点击 **Add token**，**立刻复制**生成的令牌（格式 `pypi-XXXXXXXXXXXXXXXX`）。
     ⚠️ **只有本次显示一次**，关掉页面就再也看不到；丢了就删掉重新建。

---

## 第 3 步：配置本地上传凭证（两种方式选一）

### 方式 A：环境变量（推荐，不进 git）

```powershell
# PowerShell
$env:TWINE_USERNAME="__token__"
$env:TWINE_PASSWORD="pypi-XXXXXXXXXXXXXXXX"
```

```bash
# bash / Git Bash
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-XXXXXXXXXXXXXXXX"
```

- `TWINE_USERNAME` **固定为字面量 `__token__`**（不是你的账号名）；
- `TWINE_PASSWORD` 填第 2 步拿到的 token。

### 方式 B：`~/.pypirc`（持久化，注：明文放家目录）

```ini
[distutils]
index-servers =
    pypi

[pypi]
username = __token__
password = pypi-XXXXXXXXXXXXXXXX
```

- 在 Windows 位于 `C:\Users\<你>\.pypirc`；
- 后缀要精确 `.pypirc`（无隐藏点之前缀歧义），内容按上写；
- 好处是以后不用每次 export；坏处是明文，别入库、别分享。

> **嵌到命令里直接传**也能用：`twine upload -u __token__ -p pypi-XXXX dist/*`，
> 但**别这么干**（口令会留在 shell history / 进程列表），一律走 env 或 .pypirc。

---

## 第 4 步：构建 + 校验（可重复安全做）

```bash
python -m build                # 产出 dist/llmwiki_suite-<version>-*.tar.gz 和 *.whl
python -m twine check dist/*   # 校验：README 渲染、元数据、包完整性
```

> 下文命令里的 `<version>` 一律替换成 `pyproject.toml` 的 `version`（用 `python scripts/version.py --next patch` 取下一个版本号，见第 1 步）。

- 若 `build` 未安装：`pip install build`；
- 若 `twine` 未安装：`pip install twine`；
- `twine check` 输出 `PASSED` 才能上传。

---

## 第 5 步：上传（先 Test PyPI，再正式）

### 5.1 先传 TestPyPI 验证（强烈建议）

```bash
# 装 TestPyPI 指明的发布用包（也可用 build 重出）
pip install --index-url https://test.pypi.org/simple/ llmwiki-suite==<version>   #（若已传）

# 上传到 TestPyPI
python -m twine upload --repository testpypi dist/*
```

但对上面那个 token，**TestPyPI 需要单独账号/令牌**（TestPyPI 与 PyPI 是两套账号体系）：
- 去 https://test.pypi.org/account/register/ 单独注册 + 同样方式建 token；
- 上传时用 `--repository-url https://test.pypi.org/legacy/`：

```bash
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

- 之后装体验包（不与正式冲突）：`pip install --index-url https://test.pypi.org/simple/ llmwiki-suite`

### 5.2 正式发布

```bash
python -m twine upload dist/*
```

- 若用 .pypirc，会选默认 `pypi` 目标；若用 env 变量，请确保已 export；
- 上传后打开 https://pypi.org/project/llmwiki-suite/ 就能看到包页；
- 版本冲突（同名同版本已存在）会上传失败，需 `bump version` 后再试。

---

## 第 6 步：验证 + 装后自检

```bash
pip install "llmwiki-suite[serve]"    # 推荐：核心 + 渠道一把装好
llmwiki --version                      # 应等于 pyproject.toml 的 version
```

- 可以 `pip download llmwiki-suite==<version> --no-deps -d /tmp/check` 看包内结构 `data/` scaffold 是否齐全。

---

## 版本号管理速记

| 场景 | 处理 | 命令 |
|------|------|------|
| 修 bug / 微调 | patch | `python scripts/version.py --next patch` |
| 加功能（不破坏兼容） | minor | `--next minor` |
| 破坏性变更 | major | `--next major` |
| 预发布（`0.2.0rc1`） | 脚本只认 `X.Y.Z`，手改三处 | — |

### 升版本：一条命令，不要手改

```bash
python scripts/version.py --next patch       # 先看下一个版本号（如 0.1.9）
python scripts/version.py --set 0.1.9        # dry-run：打印 diff，不写盘
python scripts/version.py --set 0.1.9 --apply --date $(date +%F)
python scripts/version.py --check            # 应输出「全部一致」
```

`--set` 只改**可写落点**：`pyproject.toml`（真源）、`src/llmwiki/__init__.py`、
`docs/getting-started.md` 的发布状态行与安装锁定版本。实现方式是「锚定正则 + 只替换捕获组」，
**不做全仓文本替换**——同一个版本号在文档里有三种语义（当前版本 / 历史事实 / 版本线叙述），
全局替换必然把 `0.1.3 起`、CHANGELOG 历史段一起改坏。

**仍需人工补齐**（脚本结束时会提示）：

1. `CHANGELOG.md` 加 `## [X.Y.Z] - YYYY-MM-DD` 段 —— `--check` 校验段头存在且等于真源
2. `docs/project-records/00-canonical-baseline.md` 的「当前版本 / 版本 tag / 时间线」

### 三道门禁

| 位置 | 检查 | 拦住什么 |
|------|------|---------|
| `ci.yml` 的 `version` job | `version.py --check` | 改了 `pyproject.toml` 忘改 `__init__.py`；文档锚点漂移；版本硬编码回潮 |
| `release.yml` 首步 | `version.py --check-tag $GITHUB_REF_NAME` | 打了 `v0.1.9` 的 tag 却发出 `0.1.8` 的包 |
| KB 仓 `kb-ci.yml` 的 `suite-ref` job | `check_suite_ref.py` | `LLMWIKI_REF` 指向不存在的 tag，或头注释里的 commit 与实际指向不符 |

发版流程：`version.py --set` → 补 CHANGELOG 与基准 → 提交 → `git tag -a vX.Y.Z` → 推 tag（`release.yml` 先校验 tag 与版本号一致，再构建上传 PyPI + 建 GitHub Release）。

---

## 发布避开坑（Checklist）

- [ ] `twine check dist/*` 全 PASSED；
- [ ] 令牌 scope 只勾 `llmwiki-suite`，不建全账号 token；
- [ ] token 只显一次，已妥善保存（密码管理器）；
- [ ] .pypirc / env 不要提交进 git；
- [ ] 正式 PyPI 已开 2FA；
- [ ] 可先用 TestPyPI 验证后再正式；
- [ ] 已 `git tag`（可选但推荐，便于回滚对应发布）。
