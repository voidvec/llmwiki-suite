# Changelog

本项目的所有显著变更都会记录在此文件，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 修复
- **`is_vendored` 认本地化变体**：除 `README.md` / `CHANGELOG.md` 等精确名，还认
  `README.en.md` / `README.zh-CN.md` / `CHANGELOG.zh.md`（语言标记 `xx` 或
  `xx-YY`）。此前双语仓库的英文 README 会被当成「缺 frontmatter 的笔记」永久报
  `fm.missing`，而补 frontmatter 又是错的方向（仓库元数据不该进召回），只能靠
  排除——所以判定必须覆盖变体。`readme-linux.md`、`readme.api.md` 这类真笔记不受影响。

## [0.1.7] - 2026-11-26

### 新增
- **`llmwiki lint --strict-links`**（严格链接口径）：只做大小写与分隔符方向归一，
  不做标点归一（`：` / `_` 不再折成 `-`）、不认目录链接；`lint-report.json` 增
  `strict_links` 字段。默认口径逐字节不变（`strict` 默认 `False`）。
- 严格口径下的断链详情附「宽松口径可解析为 `<真实路径>`」，直接给出应改成的目标，
  省一次人工定位。

### 修复
- **代码围栏与行内代码按 CommonMark 解析**：围栏须行首锚定（允许 ≤3 空格缩进与
  `>` 引用前缀），闭围栏长度不短于开围栏；行内码按反引号串长度反向引用配对。
  修掉正文里成对出现的 4 个反引号把整段（含 `[[wikilink]]` 示例表）当代码块吞掉、
  以及长围栏包短围栏时配对错位导致 `[[T]]` / `[[ =~ ]]` 被误报断链
  （实测 472 文件：errors 2→0、warnings 1→0）。
- **`health` 完整性分母剔除 vendored 仓库元数据**：`CHANGELOG`/`README`/`LICENSE`
  这类本就没有知识库 frontmatter 的文件不再被计入「缺 title/description/tags」，
  完整性不再永远卡在 99（实测 99 → 100）。
- **检索上下文按「词的标题稀有度加权」选章节**：全篇标题都含的词（如「契约」「测试」）
  权重低，只在小节标题出现的词权重高，H1 不再必然垄断章节选择；`build_context`
  与 `fetch_chapter` 兜底时剥离 frontmatter 与 `<cite>` 块。排序只影响章节选择，
  `score * factor` 未改动，recall@K / MRR 不受影响。
- **`gh_slug` 对齐 GitHub 语义**：en/em dash、减号、全角连字符、箭头一律剔除，
  空白逐字符转 `-`（破折号剔除后留下的空格形成 `--`，不再被折叠）。锚点比对
  误报 12 条归零。

### 变更
- **BM25 打分排除导航页**：frontmatter `kind: nav-index` 的页面不参与 df 与打分
  （仍保留在出链图中）。导航页按设计把一片域的标题词聚在一篇，会凭关键词密度
  抢正本 top-1（历史事故：Playwright 指引页把正本挤出 top-4）。

### 迁移
- 无破坏性变更：`--strict-links` 是可选开关，默认行为与 0.1.6 完全一致。

## [0.1.6] - 2026-08-31

### 新增
- **`/api/*` 正式路由（P2）**：`POST /api/chat`、`/api/recall` 收敛为正式接口，
  旧 `/chat`、`/recall` 保留为兼容别名（同一处理器，行为一致）。
- **SSE 流式应答（P3）**：`POST /api/chat`（及 `/chat` 别名）在请求头
  `Accept: text/event-stream` 或 `?stream=1` 时返回 `text/event-stream` 事件流，
  事件序列 `meta`（索引过期告警）→ `candidates`（引用卡）→ `delta*`（回答增量）
  → `done`（全文）；不带该头保持原 JSON 响应，老客户端零影响。
  网页问答 `/webui/chat` 已接入打字机效果 + 「停止」按钮（`AbortController` 中断），
  无 `ReadableStream` 时自动降级回普通 JSON。

### 修复
- **流式回答段落排版与占位前缀**：`/webui/chat` 新增轻量 Markdown 渲染（段落/加粗/
  列表/行内码），流式打字机逐帧对累计全文重渲染，非流式 JSON 路径共用同一渲染器，
  两端观感一致；收到首个增量前先清空「思考中…」占位，避免占位符拼入正文头部。
- **回答生成格式引导**：`assistant.py` 的 `PROMPT_TMPL` 增加「多自然段组织、
  段间空行分隔、并列要点用短列表」约束，使流式与非流式输出都倾向结构化分段。

### 变更
- 无。

## [0.1.5] - 2026-08-27

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
- **网页问答页 `GET /webui/chat`**（P0）：自包含 HTML（无外部 CDN、无构建），单栏对话 + 顶部
  `top_k` / categories / tags 筛选 + 回答下方引用卡（path/title/score）+ 索引过期提示；
  与 `POST /chat` 共用同一 `assistant.answer()` 后端。浏览器打开 `localhost:8000/webui/chat` 即用。
- **工作台 `GET /dashboard`**（P1）：导航总台 + 状态聚合——索引健康（文档数/来源/生成时间/新鲜度）、
  通道状态（`connected > configured > 未配置` 归一化视图）、各功能入口按钮。
- **`GET /dashboard/status`**：JSON 状态聚合端点（`ok / bridge_token / index / channels`），
  通道字段统一归一化为 `state / state_cls` 视图（对齐 iLink 的 `connected/has_token` 与
  wecom/feishu/telegram 的 `configured`）。
- 同步文档：README / README.en / getting-started / architecture / channel-verify / evolution-roadmap
  补网页问答与工作台说明。

### 变更
- 测试套件改为在**已安装包**上运行（`pip install -e .`），去除指向 `src/` 的路径注入——「测试的就是发布的」。
- README 渠道段改「渠道接入」并列 4 通道；tutorial-02 增补飞书 / Telegram 章节与变量。
- extras 更名：`[wechat]` → `[serve]`（该依赖组实际驱动所有通道的 `llmwiki serve`，不再单指微信）；`[wechat]` 保留为兼容别名。

### 修复
- **iLink 扫码激活后页面不跳转**：`activate()` 在 `get_qrcode_status` 返回 `confirmed` 时，
  除保存 `bot_token / baseurl / login_time` 外补设 `self.connected = True`——此前该标志
  仅在收消息循环收到首条消息后才置位，导致 WebUI 轮询 `/ilink/status` 永远停在「等待扫码
  确认…」（实际扫码已成功、token 已落盘）。
- **`/dashboard` 空白页**：页面脚本末尾误调 `fetch()`（原生 API，无参数）导致自定义
  `load()` 从不执行，改为 `load()`。
- dashboard 按钮（打开问答 / 扫码绑定 / API 文档）加 `target="_blank"`，新标签页打开。

### 测试
- 新增 `TestIlinkActivate` 回归测试（扫码 confirmed 后 `connected=True` 且保存 token；
  未确认不置位）。`test_core.py` 40 → 42 passed。

### 文档
- `docs/llmwiki-verify.md` 更名并修订为 `docs/llmwiki-local-verify.md`（用户资产边界 + 全角→连字符重建流程）。
- `docs/llmwiki-webui-dashboard-design.md` 本地设计稿（评审依据，不提交远程；实施后回填联动文档）。

## [0.1.4] - 2026-08-27

### 新增
- `llmwiki eval --seed [--seed-limit N]`：从索引文档标题**采样生成首版 `eval_queries.json`**
  （自动过滤 `templates/`、`category-index.md` 等派生产物，保证 expected 指向真实进索引的文档），
  写盘后立即用本集评估——新用户一条命令拿到**针对自己库**的首版评估集：
  `llmwiki init && llmwiki ingest && llmwiki index && llmwiki eval --seed`。
- `llmwiki eval --demo`：显式演示模式——内置示例评测集仅供套件**自测/演示**使用
  （`scripts/check_recall_baseline.py --demo`），stderr 明确标注「expected 指向套件 demo 库，
  与你的知识库无关，分数不具参考意义」。
- 报告 `meta.queries_source` 字段：区分 `repo` / `explicit` / `seed` / `demo-builtin`
  （取代原 `queries_is_builtin` 布尔）。

### 变更
- **取消内置集自动回退**（不提供假成功结果）：`llmwiki eval` 无 `eval_queries.json` 时不再
  自动改用包内置示例集（0.1.3 会跑出「假 100%」），改为**退出码 2** + 引导
  `--seed` 或放置评估集文件。
- 退出码语义收紧：**2** = 无评估集（可恢复缺失），**3** = 索引缺失，且索引缺失判断
  **优先于**评估集判断（先 `llmwiki index` 再评估）。
- `scripts/check_recall_baseline.py` 同步 `--demo` 透传（套件自身基线回归改为显式用内置集）。
- 设计取舍：**否决 init 生成 T0 种子**（`templates/` 默认排除、README 非保证存在，
  种子必指向永不进索引的文件），统一定为 `--seed` 一条命令闭环。
- 文档同步：`llmwiki-eval.md`（选项/退出码）、`llmwiki-tutorial-03`（§3.1/3.2）、
  `getting-started.md`（0→1 流程补 `eval --seed`）、设计文档改版 2.0 记录拍板结果。
- 版本 0.1.3 → 0.1.4（行为收紧 + 新功能）。

### 测试
- 套件测试 40 passed：新增无评估集→2、`--demo` 标记、`--seed` 采样过滤、`--seed` 无索引→3。
- 真实 CLI 五场景验证：无集+有索引→exit 2、`--seed`→写盘并评估、`--demo`→显式内置集、
  `--seed` 无索引→exit 3、无集无索引→exit 3。

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

[0.1.6]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/voidvec/llmwiki-suite/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/voidvec/llmwiki-suite/releases/tag/v0.1.0
