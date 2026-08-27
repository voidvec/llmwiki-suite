# Contributing to llmwiki-suite

感谢你愿意参与 llmwiki-suite 的建设。这个项目从一个人知识库工具长出来，
社区让它变得更好——无论是修一个 bug、补一篇文档，还是分享一个真实的使用场景。

## 我能贡献什么？

- **提 bug / 功能请求**：先搜 [Issues](https://github.com/voidvec/llmwiki-suite/issues)，
  避免重复；新建时用仓库自带的模板（Bug 报告 / 功能请求）。
- **修文档**：`docs/` 下任何一篇，包括 README。文档和代码一样重要。
- **修代码**：见下方「本地开发」。
- **分享使用场景 / 测试用例**：在 [Discussions](https://github.com/voidvec/llmwiki-suite/discussions)
  里晒你的知识库接入，或者往 `eval_queries.json` 里补真实查询——这对检索质量调优极有价值。

## 本地开发环境

要求 **Python ≥ 3.11**（内置 `tomllib`，套件最低版本）。

```bash
git clone https://github.com/voidvec/llmwiki-suite.git
cd llmwiki-suite
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"     # 测试 + pre-commit 依赖（不装通道 extras）
pre-commit install          # 注册仓库级钩子（推荐）
```

想本地验证通道行为，装 `[serve]` extras 并按 `docs/llmwiki-channel-verify.md` 跑冒烟。

## 测试原则

- 单测在 `tests/`，用 `pytest` 跑：`pytest`
- **召回基线回归**不经 pytest：`python scripts/check_recall_baseline.py --repo tests/fixtures/kb --build`
  ——CI 也会跑，改了检索逻辑必须同步维护基线
- 套件对「评估质量」是认真的：涉及 `eval` 的改动请一并跑 `llmwiki eval`（内置集或你自己的集）

## 提交规范

- 提交信息用 **Conventional Commits** 风格：
  `feat(core): ...` · `fix(cli): ...` · `docs(*): ...` · `test(*): ...` · `chore(release): ...`
- 提交前先跑一遍 `pytest` + pre-commit（会做 check-yaml / 行尾 / EOF / 召回基线回归）。
- 不要往提交里混入无关格式改动（行尾类修复单独一个提交）。
- **密钥 / 环境变量**：任何新密钥都只走 `LLM_WIKI_*` 环境变量，绝不写进 `llmwiki.toml` 或代码默认值内。
- 涉及 `pip` 依赖：只改 `pyproject.toml` 的 extras，别往 core dependencies 塞东西（核心保持零依赖）。

## PR 流程

1. Fork 本仓库，从 `main` 新建分支（`feat/xxx`、`fix/xxx`、`docs/xxx`）。
2. 提交改动（见上方规范），本地跑通 `pytest` + 基线回归。
3. 开 PR 到 `main`，描述里写清**动机**与**验证方式**（贴 terminal 输出最好）。
4. CI 全绿后合并。Release 由维护者打 tag 触发（见 `docs/pypi-release-guide.md`）。

## 文档与代码同步

文档 `docs/` 里的命令行为与 README 必须与当前 `main` 一致——文档过期也算 bug，
欢迎指出来（直接开 Issue 或顺手开 PR）。

---

有任何拿不准的，直接开 [Discussion](https://github.com/voidvec/llmwiki-suite/discussions)
问一声，别自己猜。欢迎来玩。