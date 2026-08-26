# Changelog

本项目的所有显著变更都会记录在此文件，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
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
