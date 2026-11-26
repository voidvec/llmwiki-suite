---
title: 通道体系、服务层与安全边界
description: 四类通道的驱动模型、端点与验签、SSE 事件、鉴权范围与安全边界
tags: ["通道", "Webhook", "iLink", "安全"]
difficulty: advanced
categories: ["软件架构"]
kb_id: KB-07
legacy_kb_id: KB-08
kind: knowledge-base
status: derived
scope: ChannelAdapter 抽象、四类通道端点/凭据/签名、iLink 协议、Web/API 与 SSE、鉴权范围、暴露形态与安全红线
audience: 部署者、通道开发者、安全评审者
last_verified: 2026-11-11
reconciled_against: 仓库口径基准 v1 · 2026-11-11
confidence: high
---

# 通道体系、服务层与安全边界

> **定位**：把「谁能问、从哪进、怎么验签、哪里不设防」讲清楚。产品文档偏接入教程，这篇偏契约与安全边界。

## 1. 背景

`llmwiki serve` 是一层 FastAPI 装配（默认 `127.0.0.1:8000`），把同一份索引与 `KbAssistant` 暴露给网页、企业微信、飞书、Telegram 与个人微信 iLink。0.1.5 增加 WebUI/Dashboard，0.1.6 把 `/api/*` 收敛为正式路由并加入 SSE 流式（`CHANGELOG.md`）。所有页面是自包含内联 HTML，无静态文件路由。

## 2. 结论速览

- 两类驱动：**Webhook**（WeCom / Feishu / Telegram，`register_routes(app)`）与**轮询**（iLink，`start()/stop()` 后台线程，无需公网）。
- 统一 `health()` 上报到 `/healthz`；构造函数注入 `KbAssistant`；基类四个方法都有默认实现，**无 `@abstractmethod`**。
- `BRIDGE_TOKEN` 只保护 **4 个问答端点**（`/api/chat`、`/api/recall`、`/chat`、`/recall`）；`/healthz`、`/dashboard*`、`/ilink/*`、`/webui/*` 与各 callback **不受保护**。
- 套件**永远只监听 `127.0.0.1`**，内部不做登录态 / 会话保护（P4 会话保护经评审取消）。
- 已知实现缺口：企业微信适配器绝对导入、`serve` 配置未注入、飞书签名算法疑似与官方不一致（PR-04）。

## 3. 关键关系

```
llmwiki serve (uvicorn, 127.0.0.1:8000)
   └─ wechat_bridge.app
        ├─ INDEX = KB_INDEX env > load_config(resolve_repo(None)).index_path > "kb-index.json"
        ├─ assistant = KbAssistant(INDEX)   ★ 只传索引，TOML 配置未注入
        ├─ adapters = [WeComAdapter, IlinkAdapter(ENABLE_ILINK!=0),
        │              FeishuAdapter, TelegramAdapter]
        │     └─ 逐个 register_routes(app)（轮询类无路由）
        ├─ startup / shutdown → 逐通道 start()/stop()（try/except 隔离）
        └─ 路由：
             问答 /api/chat /api/recall (+ /chat /recall 别名)
             状态 /healthz /dashboard /dashboard/status /ilink/status
             页面 /webui/chat /ilink/webui
             管理 /ilink/qrcode /ilink/activate
             回调 /wechat/callback /feishu/callback /telegram/callback
```

## 4. 主体内容

### 4.1 通道对照表

| 通道 | 驱动 | 端点 | 凭据（env） | 校验方式 | health() |
|---|---|---|---|---|---|
| 企业微信 | Webhook | `GET/POST /wechat/callback` | `LLM_WIKI_WECOM_{TOKEN,AES_KEY,CORPID,SECRET,AGENTID}` | `WXBizMsgCrypt`：sha1 签名 + AES-256-CBC + receiveid 比对 | `configured = _crypt() is not None` |
| 飞书 | Webhook | `POST /feishu/callback` | `FEISHU_APP_ID / APP_SECRET / VERIFY_TOKEN` | `url_verification` 原样回 `challenge`；HMAC-SHA256（有 VERIFY_TOKEN 才校验） | `configured = bool(app_id and app_secret)` |
| Telegram | Webhook | `POST /telegram/callback` | `TELEGRAM_BOT_TOKEN / SECRET_TOKEN` | Header `x-telegram-bot-api-secret-token` 不符 → 403 | `configured = bool(bot_token)` |
| 个人微信 iLink | 轮询 | 无回调；管理端点 `/ilink/*` | `ILINK_BOT_TOKEN / BASE_URL / CDN_BASE_URL / SESSION_FILE` | `AuthorizationType: ilink_bot_token` + Bearer + `X-WECHAT-UIN` | `connected / has_token / session_valid` |

**路由无条件挂载**：缺凭据不会 404，而是返回可读 `hint`（`docs/llmwiki-channel-verify.md` §1）。`BRIDGE_TOKEN` **不涉及**飞书/Telegram 回调端点；iLink 后台轮询直接调 `assistant.answer()`，微信端发消息不受 BRIDGE_TOKEN 影响。

### 4.2 iLink 协议要点（`ilink_adapter.py`）

- 常量：`DEFAULT_BASE_URL = https://ilinkai.weixin.qq.com`、`CDN_BASE_URL = https://novac2c.cdn.weixin.qq.com/c2c`、`CHANNEL_VERSION = 1.0.2`、`SESSION_TTL = 24h`、`bot_type=3`。
- 绑定流程：`GET ilink/bot/get_bot_qrcode?bot_type=3` → 本地生成 SVG（`qrcode` 可选，缺库降级为链接）→ `GET get_qrcode_status` 轮询至 `confirmed` → 保存 `bot_token/baseurl/login_time` 到 `.ilink_session.json`。
- 消息循环：`POST getupdates` 长轮询（默认 35s，请求 timeout 45s）→ 仅 `message_type==1` 文本 → `assistant.answer()` → `POST sendmessage`（`text[:1800]`，`client_id = llmwiki-%08x`）。会话过期发重激活链接并 `sleep(30)`；异常断开 `sleep(3)` 重试。
- **无需公网**（客户端主动长轮询），这是选它作默认个人微信通道的核心原因；对比 Wechaty+PadLocal 约 ¥299/年、本地 hook 有封号风险（`llmwiki-architecture.md` §3）。

### 4.3 Web / API 契约

`QueryReq`：`query`、`top_k=4`、`categories=[]`、`tags=[]`。

| 端点 | 说明 |
|---|---|
| `POST /api/chat` | `?stream=1` 或 `Accept: text/event-stream` → SSE；否则 JSON `{answer, candidates, index_stale}` |
| `POST /api/recall` | 只召回： `{query, count, candidates[{path,title,score,matched_headings,summary}], index_stale}` |
| `POST /chat` / `POST /recall` | 0.1.6 保留兼容别名；**`/chat` 只认 Accept 头，不认 `?stream=1`**（与「等价」注释不符） |
| `GET /healthz` | `{ok, bridge_token, channels:[...]}` |
| `GET /dashboard/status` / `GET /dashboard` | 索引信息 + 通道视图 + bridge_token / 自包含 HTML |
| `GET /webui/chat` | 打字机 + 「停止」按钮（AbortController），无 ReadableStream 降级 JSON |
| `GET /ilink/{qrcode,activate,status,webui}` | 扫码绑定与管理 |

**SSE 事件序列**：`meta`（`{"index_stale": ...}`）→ `candidates`（无命中带 `not_found`）→ `delta*`（`{"text": ...}`）→ `done`（`{"answer": 全文}`）。格式 `event: <name>\ndata: <json>\n\n`。

**鉴权**：`BRIDGE_TOKEN` 在模块 import 时冻结（`wechat_bridge.py:79`）；未配置则**本地/开发模式放行**。校验支持 `?token=` 或 `X-Bridge-Token` 头，不符返回 401。前端把 token 存 `localStorage('llmwiki_token')`。

### 4.4 安全边界（硬约束）

1. 默认 `--host 127.0.0.1`；暴露形态**只支持两种**：A 仅自己（Tailscale/ZeroTier 设备级认证）、B 团队内网（反代 + 网关 Basic Auth），「暂不做第三种」。
2. `/webui/*`、`/dashboard` 继承「能访问到 127.0.0.1:8000 即已过身份」的网关信任，**套件内部不做登录态 / 会话保护**（P4 取消）；网关若暴露公网应挡 `/api/*`、放行 `/webui/*`。
3. 公网暴露必须设 `LLM_WIKI_BRIDGE_TOKEN`；各 webhook 用各自 secret / verify token 验签。
4. 密钥只走环境变量，不读 `.env`；`.ilink_session.json` 绝不入库；推理预算熔断 600s（`SECURITY.md`）。
5. 本项目**无自有服务器端组件**，TLS / 反代 / 防火墙由部署方负责；只操作 `--repo` 指向的库，不扫系统目录。
6. 前端 `mdText()` 先 HTML 转义再渲染 Markdown（防 XSS）；所有页面 CSS/JS 内嵌、无外部依赖。

### 4.5 加密实现

`wecom_crypto.WXBizMsgCrypt`：43 字符 EncodingAESKey + `=` Base64 解码得 32 字节 AES Key，`IV = key[:16]`，PKCS7 填充，明文结构 `random(16) + 4 字节网络序长度 + msg + receiveid`，AES-256-CBC；签名 `sha1("".join(sorted(parts)))`；`decrypt_msg` 校验 receiveid 与 corpid 一致。依赖可选 `Crypto.Cipher.AES`（pycryptodome）。

## 5. 注意事项与常见误读

1. **「adapter 动态读 env、改配置不用重启」只对飞书/Telegram 成立**：企微凭证在模块级冻结；文档内部对此有矛盾表述（`channel-verify.md` §1 vs §4、`tutorial-02` §6）。
2. **`BRIDGE_TOKEN` 不是全局鉴权**：只挡 4 个问答端点，别误以为 Dashboard 与 iLink 管理端点受保护。
3. 个人微信 iLink 消息**绕过** BRIDGE_TOKEN；若需要管控，应在网关层或轮询层处理。
4. `README.en.md` 原写回调路径含 `/wecom/*`，实际是 **`/wechat/callback`**；该处已于 2026-11-11 修正（PR-04 §1 修订记录）。
5. `.ilink_session.json` 与 `.obsidian/` 在文档里被称「已加 .gitignore」，但根 `.gitignore` 与 `GITIGNORE_LINES` 都**没有**这两项（PR-04）。
6. `@app.on_event("startup"/"shutdown")` 是 FastAPI 已废弃 API，未来应迁 `lifespan`。

## 6. 不确定 / 待补充项

- 企业微信通道可用性存疑：`wecom_adapter.py:48,123` 用绝对导入 `from wecom_crypto import ...`，异常被静默吞掉，且 `pycryptodome` 未列入 extras；**未做运行时验证**。
- 飞书 `_verify_signature` 从 body 的 `header.signature` 取签名、HMAC 拼接方式与飞书官方文档不一致，疑似自造；`scripts/smoke_feishu_telegram.py` 只验证自洽，不代表与官方互通。
- `README.en.md` 的企微路由已于 2026-11-11 修正；`channel-verify.md` 的重启说法、`tutorial-02` 的旧 env 名仍待与代码统一（需按通道重写，PR-04 P1-9）。
- `llmwiki-webui-dashboard-design.md` §2.1 数据流仍写 `POST /chat`（正式接口已是 `/api/chat`），§6 三条开放问题（BRIDGE_TOKEN 轮换、dashboard 是否展示 index 调用路径、P2 是否一次性做）未标结论。
- 网关 Basic Auth 与 `BRIDGE_TOKEN` 是否应共存、token 是否轮换，仓库内无决策记录（已知问题 / 待办，PR-04）。

## 7. 主要依据

| 依据 | 具体线索 |
|---|---|
| `src/llmwiki/channels/channel_base.py` | `ChannelAdapter(ABC)` 四方法与默认实现 |
| `src/llmwiki/channels/wechat_bridge.py` | 路由表 :192-249 / :340-759、`require_bridge_token` :99、`_chat_stream` :137-159、装配 :61-91 |
| `src/llmwiki/channels/ilink_adapter.py` | 常量 :55-59、getupdates/sendmessage、`_loop` :324、`activate` :210 |
| `src/llmwiki/channels/wecom_adapter.py` / `wecom_crypto.py` | 端点、AES、签名、绝对导入 |
| `src/llmwiki/channels/feishu_adapter.py` / `telegram_adapter.py` | 运行时读 env、challenge、403 |
| `src/llmwiki/assistant.py` | `answer_stream` / `call_llm_stream` |
| `SECURITY.md` / `docs/llmwiki-webui-dashboard-design.md` / `docs/llmwiki-architecture.md` §3-§4 | 安全底线、A/B 暴露形态、iLink 选型 |
| `docs/llmwiki-channel-verify.md` / `scripts/smoke_feishu_telegram.py` | 验证手册与 6 个冒烟断言 |

## 8. 相关主题

- KB-01 系统架构、模块与依赖关系
- KB-04 配置三层模型与运行入口
- KB-08 业务规则与约束清单
- PR-04 已知偏差与待补充台账
