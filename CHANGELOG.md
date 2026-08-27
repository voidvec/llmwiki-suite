# Changelog

本项目的所有显著变更都会记录在此文件，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- 仓库门面化（公众号引流铺垫）：README 顶部横幅 `assets/banner.png`、30 秒快速体验区与终端演示图
  `assets/demo-term.png`、社交预览图 `assets/social-preview.png`、底部「作者与公众号」区（二维码占位）。
- 新增 `CONTRIBUTING.md`（贡献流程：开发环境/测试/提交规范/PR）与 `SECURITY.md`（漏洞报告与密钥-EV规范）。
- 新增 Issue 模板 `docs_usage.yml`（文档改进 / 使用咨询）。
- 仓库侧已配置 description / topics / Discussions（代用户操作，见 README 社区入口）。
- 新增 `docs/llmwiki-eval.md`：eval CLI 命令参考（全部选项、评估集 schema、报告字段、指标解读）。
- 新增英文 README（`README.en.md`）与国际化链接。
- 新增 GitHub Issue 模板（bug 报告 / 功能请求）。
- 新增仓库级 pre-commit 钩子（check-yaml / 行尾 / EOF / 召回基线回归）。
- CI 矩阵新增 Python 3.14。
- `llmwiki eval --chart`：自包含 SVG 评估图表（指标卡 + 逐条命中），零第三方依赖。
- 飞书 / Telegram 适配器（`FeishuAdapter` / `TelegramAdapter`，Webhook 驱动，
  与 iLink/企业微信共用 `ChannelAdapter` 契约，`serve` 配置环境变量即注册）。
- 新增 `docs/llmwiki-evolution-roadmap.md`：知识库自进化路线图
  （L0 被动 → L1 记忆 → L2 主动建议 → L3 自主迭代，含实施顺序）。

### 变更
- 测试套件改为在**已安装包**上运行（`pip install -e .`），去除指向 `src/` 的路径注入——「测试的就是发布的」。
- README 渠道段改「渠道接入」并列 4 通道；tutorial-02 增补飞书 / Telegram 章节与变量。
- eval 报告新增 `.svg` 图表输出。
- extras 更名：`[wechat]` → `[serve]`（该依赖组实际驱动所有通道的 `llmwiki serve`，不再单指微信）；`[wechat]` 保留为兼容别名。
- 版本 0.1.1 → 0.1.2（发布新 extras 元数据）。

## [0.1.3] - 2026-08-26

### 新增
- categories 增量语义：`llmwiki.toml` 的 `[categories].allowed` 改为在套件默认词表
  **之上追加**（合并去重），不再整体替换——写少类别不丢默认类别（如「导航索引」）；
  如需白名单模式（整体替换），设 `[categories].replace_default = true`。
- `llmwiki categories-sync`：从 `kb-index.json` 派生全部**实际使用中**的类别，
  `--apply` 写回 `llmwiki.toml`（文本级最小改写，保留注释/其它节）。
- `llmwiki lint --sync-vocab`：巡检时自动把索引派生词表并入生效词表（仅本次校验，
  不持久化），categories 漏收自愈。
- `llmwiki eval` 双兜底：库根无 `eval_queries.json` 时回退套件内置示例集并在报告
  `meta.queries_is_builtin` 标记；索引缺失时返回退出码 1 并给出 `llmwiki index` 指引
  （不再裸抛 `FileNotFoundError`）。
- 锚点双段比对：`heading_exists` 新增宽松 `anchor_slug`（剥离 emoji、`第 N 步` /
  `步骤 N` / `Step N` / 纯数字序号前缀、折叠 `.`/`-`/空格），修复
  `#1-概述 ↔ ## 1. 📖 概述`、`#2-生成-github-pat ↔ 步骤 1：生成 GitHub PAT`
  这类真实库高频错配（真实库误报 199 → 24）。
- `qrcode` 依赖补入 `[serve]`（iLink 绑定二维码 SVG 生成）。
- `pyproject.toml` 补 `classifiers`（3.11–3.14 / OS Independent / Topic）。
- CI 矩阵新增 Python 3.14。

### 变更
- 版本 0.1.2 → 0.1.3。

### 修复
- `gh_slug` 补删 `+＊*` 等半角/全角标点，避免 `C++` 类锚点误判。
- `anchor_slug` 序号正则覆盖「数字在序数词前」形态（`步骤 N` / `Step N`）与
  「第 N」空格变体（`第 1 步`）。

## [0.1.1] - 2026-08-25

### 新增
- P1 最小测试套件：15 个核心单测（tokenize/frontmatter/仓库定位/配置合并）+ 3 个召回基线端到端断言。
- 独立召回基线回归脚本 `scripts/check_recall_baseline.py`（不经 pytest，退出码 0/1/2，
  支持 `--build` 自动构建、`--json` 直读快照）与 CI 可复现的 `tests/fixtures/kb` 迷你库。
- GitHub Actions 工作流：`ci.yml`（三矩阵冒烟 + 测试 + 独立基线回归 + 构建校验）与
  `release.yml`（tag 触发自动发布 PyPI + 建 GitHub Release，含 `--skip-existing` 保护）。
- README 补 CI / Release 徽章、五步接入补 `eval`、`query` 描述对齐「生成回答」能力。

### 修复
- 修复 `tests/fixtures/kb/category-index.md` 被 `.gitignore` 规则误伤不入库，导致
  CI 独立基线回归 recall=0.75 挂掉的问题（规则限定为仓库根 `/category-index.md`）。

### 变更
- 安装推荐统一为 PyPI 已发布版 + `[wechat]` 渠道版（核心版降级为轻量选项）。
- upgrade actions 至 Node24 运行时（checkout v7 / setup-python v7 / action-gh-release v3），
  消除 Node.js 20 弃用警告。
- license 改用 SPDX 简写 MIT；新增 PyPI 发布指南 `docs/pypi-release-guide.md`。

## [0.1.0] - 2026-08-24

### 新增
- 套件化交付：`serve` 子命令、`channels` 通道包（个人微信 iLink / 企业微信）、6 篇文档。
- 检索质量演进：P1 别名组（中英/缩写语义失配）、R1 每词阈值（查询长度感知）、
  R2 覆盖度线性 ramp（消除边界跳变）、R3 打分性能缓存（~170×）、P3 索引过期检测、
  P4 via_link 补位门槛、top_k 默认收紧 4（节流 ~35% token）。
- S1 核心引擎可安装化（pip 化迁移）、S2 套件分发（PyPI 发布）。

[0.1.1]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/voidvec/llmwiki-suite/releases/tag/v0.1.0
