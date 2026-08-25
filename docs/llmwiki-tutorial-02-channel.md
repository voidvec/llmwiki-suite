---
title: "LLMWiki 渠道接入：把知识库接到微信等聊天渠道"
description: "把本地 LLMWiki 知识库接入微信做问答：装 wechat extras → 起桥接服务 → 个人微信(iLink 官方 Bot API)扫码授权 → 企业微信(可选) → 微信端直接查知识库。覆盖 PowerShell/bash/Git Bash 三版本与排错。"
categories: ['知识库规范', '软件架构']
tags:
  - llmwiki
  - wechat
  - ilink
  - wecom
  - bot
  - deployment
  - tutorial
difficulty: "advanced"
estimated_time: "30分钟"
created: "2026-08-20"
updated: "2026-08-24"
version: "2.0"
---

# LLMWiki 渠道接入：把知识库接到微信等聊天渠道

> 适用对象：已按《[[llmwiki-tutorial-01-system]]·体系搭建》建好知识库（有 `kb-index.json`），想把它接到微信随时问答的人。
> 所有命令提供 **PowerShell（Windows）**、**bash（Linux/macOS）**、**Git Bash（Windows）** 三版本。

---

## 0. 架构一句话

```
微信(个人号) ──iLink Bot API(轮询)──► IlinkAdapter ──┐
                                                      ├─► KbAssistant ──► KbRetriever(本地 kb-index.json) ──► 答案回微信
企业微信 ────────Webhook 回调────────► WeComAdapter ──┘
```

- **个人微信走 iLink**：服务端主动长轮询 `ilinkai.weixin.qq.com`，**不需要公网 / 内网穿透**（相对企业微信的最大优势）。
- **企业微信走 Webhook**：需要公网可达的回调地址（或内网穿透）。
- 两条通道共用同一个 `KbAssistant`（召回 → 拼 prompt → 调 LLM → 附来源），与传输方式解耦。

分层（自下而上）：**通道层 `ChannelAdapter`** → **应答编排层 `KbAssistant`** → **召回层 `KbRetriever`**（依赖 `kb_core` 的链接铁律）。`channels/wechat_bridge.py` 只做「装配 + 生命周期 + 对外 HTTP 端点」。

---

## 1. 环境准备

### 1.1 前置条件

| 项 | 说明 | 验证 |
|----|------|------|
| 已装 llmwiki-suite | 见姊妹篇 §1.2 | `llmwiki --help` |
| wechat extras | 桥接服务依赖 fastapi + uvicorn | `llmwiki serve --help` |
| 知识库索引 | 已生成 `kb-index.json` | `ls kb-index.json` |
| LLM Key（推荐） | 不设也能跑，答案降级为片段预览 | `echo $LLM_WIKI_API_KEY` |
| iLink 平台权限 | **个人微信前提**：需有腾讯 iLink Bot API 访问权限 | 取码能返回二维码即代表有权 |

> 若 `kb-index.json` 缺失，先跑 `llmwiki index` 重建。

### 1.2 安装依赖（wechat extras）

> 说明：`[wechat]` extra 自动带上 fastapi + uvicorn；若之前只装了核心版（`llmwiki-suite`），
> 直接执行下面命令补装即可（会升级为完整包，无需重装核心）。

```bash
# bash（Linux / macOS）
pip install "llmwiki-suite[wechat]"
```

```powershell
# Windows（PowerShell / Git Bash 同理）
pip install "llmwiki-suite[wechat]"
```

- `fastapi` / `uvicorn`：对外 HTTP 服务（必需）。
- `qrcode`：把激活链接本地编码成二维码 SVG（缺了会自动降级，WebUI 改用链接）。
- `pycryptodome`：企业微信消息加解密必需（只用企业微信才需要）。

---

## 2. 环境变量清单

代码只读 `os.getenv`，**无 `.env` 自动加载**，请手动 `export` / `$env:` 注入（**切勿硬编码任何凭证**）。

| 变量 | 必填 | 默认值 | 作用 |
|------|------|--------|------|
| `LLM_WIKI_KB_INDEX` | 否 | `<repo>/kb-index.json` | 检索索引路径（缺省时按 D3 解析：`--repo` / CWD 向上找 `.git` / CWD 有 .md） |
| `LLM_WIKI_API_KEY` | 推荐 | 空 → 降级预览 | OpenAI 兼容端点密钥 |
| `LLM_WIKI_BASE_URL` | 否 | `https://api.openai.com/v1` | 自建 / 兼容 LLM 网关 |
| `LLM_WIKI_MODEL` | 否 | `gpt-4o-mini` | 模型名 |
| `LLM_WIKI_BRIDGE_TOKEN` | 建议 | 空（开发放行） | 保护 `/chat`、`/recall` |
| `LLM_WIKI_ENABLE_ILINK` | 否 | `1`（启用） | 设 `0` 关闭个人微信通道 |
| `LLM_WIKI_WECOM_TOKEN` / `LLM_WIKI_WECOM_AES_KEY` | 企业微信需 | 空 → 不启用 | 企业微信回调验签 / 加解密 |
| `LLM_WIKI_WECOM_CORPID` / `LLM_WIKI_WECOM_SECRET` / `LLM_WIKI_WECOM_AGENTID` | 企业微信需 | 空 | 主动推送用 |
| `LLM_WIKI_ILINK_BASE_URL` | 否 | `https://ilinkai.weixin.qq.com` | iLink 网关 |
| `LLM_WIKI_ILINK_CDN_BASE_URL` | 否 | `https://novac2c.cdn.weixin.qq.com/c2c` | 媒体 CDN |
| `LLM_WIKI_ILINK_BOT_TOKEN` | 否 | 空（走扫码） | 直接注入已有 token，跳过扫码 |
| `LLM_WIKI_ILINK_SESSION_FILE` | 否 | `.ilink_session.json` | 会话持久化（已在 .gitignore） |

> 🔒 `.ilink_session.json` 已在 `.gitignore` 中，**token 不出仓库**，可放心持久化。

### 2.1 换 LLM 厂商 / 模型（协议兼容即可，不看厂商名）

`LLM_WIKI_API_KEY` 关键字是「推荐」；`LLM_WIKI_BASE_URL` / `LLM_WIKI_MODEL` 已有默认值。只用 OpenAI 时只设 key；换厂商就把三个一起设。

**兼容判定**：`call_llm` 只依赖 OpenAI 兼容的 `/chat/completions`——

```bash
# DeepSeek
export LLM_WIKI_BASE_URL="https://api.deepseek.com/v1"; export LLM_WIKI_MODEL="deepseek-chat"
# 通义千问
export LLM_WIKI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"; export LLM_WIKI_MODEL="qwen-plus"
# Kimi / Moonshot
export LLM_WIKI_BASE_URL="https://api.moonshot.cn/v1"; export LLM_WIKI_MODEL="moonshot-v1-8k"
# 本地 Ollama（key 随便填）
export LLM_WIKI_BASE_URL="http://127.0.0.1:11434/v1"; export LLM_WIKI_MODEL="qwen2.5:7b"; export LLM_WIKI_API_KEY="ollama"
```

### 2.2 LLM_WIKI_BRIDGE_TOKEN 是什么、从哪来

它是**你自己定义的一个网关口令**，不是平台提供。作用：保护 `/chat`、`/recall` 两个对外端点——部署用内网穿透暴露公网后，陌生人无法随便查你的知识库；设了之后必须带令牌（`?token=xxx` 或头 `X-Bridge-Token: xxx`）否则 `401`。

```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

> ⚠️ **重要**：个人微信 iLink 通道**不经过**这两个受保护端点——它在后台轮询里直接调 `assistant.answer()`，**微信端发消息不受 LLM_WIKI_BRIDGE_TOKEN 影响**。

---

## 3. 启动桥接服务

```bash
# bash（Linux / macOS / Git Bash）
export LLM_WIKI_API_KEY="sk-xxxx"     # 不设则答案降级为片段预览
export LLM_WIKI_BRIDGE_TOKEN="my-secret"  # 建议设置，保护 /chat /recall
export LLM_WIKI_ENABLE_ILINK="1"          # 个人微信通道（默认即开）
cd ~/my-notes                    # 库目录（D3 解析锚点）
llmwiki serve --host 127.0.0.1 --port 8000
```

```powershell
# PowerShell
$env:LLM_WIKI_API_KEY="sk-xxxx"
$env:LLM_WIKI_BRIDGE_TOKEN="my-secret"
$env:LLM_WIKI_ENABLE_ILINK="1"
cd ~/my-notes
llmwiki serve --host 127.0.0.1 --port 8000
```

等价底层命令（想精确控制 uvicorn 参数时）：

```bash
uvicorn llmwiki.channels.wechat_bridge:app --host 127.0.0.1 --port 8000
```

> 服务从**任意目录**都能启动（`llmwiki serve` 自动定位库根）；不再要求 cd 到 `scripts/`。

启动后另开终端验证：

```bash
curl http://127.0.0.1:8000/healthz
# 期望：{"ok":true,"bridge_token":true,
#        "channels":[{"name":"ilink","enabled":true,"connected":false,
#                     "has_token":false,"session_valid":false}]}
```

看到 `channels` 里有 `ilink` 即代表个人微信通道已挂载、后台轮询线程已就绪（无 token 时空闲不触网）。

---

## 4. 个人微信接入（iLink，推荐，免费官方）

个人微信通过**腾讯官方 iLink Bot API** 接入：拉绑定二维码 → 微信扫码 / 点链接授权 → 服务端拿到 `bot_token` → 进入长轮询收发。**无需公网、无头跨平台、免 Wechaty 商业 puppet（≈¥299/年）**。

### 4.1 为什么选 iLink（接个人微信三条路对比）

| 路线 | 成本 | 稳定性 | 跨平台 | 机制 |
|------|------|--------|--------|------|
| 本地 hook（wcferry / gewechat） | 免费 | 有封号风险，mac/Linux 难跑 | 仅 Windows 桌面微信 | 注入客户端内存 |
| Wechaty + 商业 puppet（PadLocal） | ≈¥299/年 | 较稳 | 跨平台 | 模拟 iPad 协议 |
| **腾讯 iLink Bot API（本套件默认）** | **免费·官方** | 受平台开放度摆布 | **无头跨平台** | 个人号扫码成 bot，经官方网关 |

### 4.2 一步激活（推荐）

```bash
curl -X POST "http://127.0.0.1:8000/ilink/activate?timeout=180"
```

返回：

```json
{
  "qrcode": "<qr_token>",
  "activation_link": "https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=<qr_token>&bot_type=3",
  "qrcode_img_svg": "<二维码 SVG>"
}
```

> iLink 的 `get_bot_qrcode` **只返回二维码 token 与激活链接**，不带图片；二维码图由服务用 `qrcode` 库把 `activation_link` **本地编码成 SVG** 生成。

**怎么扫：**

- **方式 A（点链接，最省事）**：把 `activation_link` 在**微信内**打开（发给文件传输助手 / 复制到微信对话框点击），确认授权。
- **方式 B（扫服务端二维码）**：

```bash
curl -s http://127.0.0.1:8000/ilink/qrcode | python -c "import sys,json; open('qr.svg','w').write(json.load(sys.stdin)['qrcode_img_svg'])" && open qr.svg   # mac/linux
```

### 4.3 WebUI 可视化扫码（最推荐）

浏览器打开 `http://127.0.0.1:8000/ilink/webui`：页面自动拉取二维码并渲染成 SVG（服务端本地编码），**手机微信扫一扫**即可；扫码确认后页面**自动轮询**显示「✅ 已激活」。

底层链路：`GET /ilink/webui` → `POST /ilink/activate`（后台等扫码）→ `GET /ilink/status`（前端每 2s 轮询）。

### 4.4 会话持久化 / 24h 过期

- **重启免重扫**：`<24h` 内重启读 `.ilink_session.json` 自动复用 token。
- **24h 过期**：服务端自动给最近联系人推送重激活链接，或随时再调 `/ilink/activate`。

### 4.5 确认已连上

```bash
curl http://127.0.0.1:8000/healthz
# 等到 ilink 的 "connected":true、"has_token":true 即成功
```

---

## 5. 在微信端查询知识库

授权完成后 → 给 bot 发任意文本即可。

1. 找到已绑定的 bot（你的个人号自身，或按绑定方式而定）。
2. 发送问题，如：
   > `如何配置 lint 自动化？`
   > `微信渠道有哪三条接入路线？`
   > `iLink 和 Wechaty 的区别`
3. 服务端收到文本 → `KbAssistant.answer()` → `sendmessage` 把答案回发微信。
4. 答案默认引用来源标题（如「来源：[[llmwiki-architecture]]」）。

**行为说明：**

- 配了 `LLM_WIKI_API_KEY` → LLM 基于检索片段生成回答；没配 → 返回「检索片段预览」。
- v1 仅支持**文本**；单条回复上限 **1800 字**。
- 知识库无相关内容 → 回答「知识库中未找到相关信息。」（这是**预期行为**，不是故障）。

---

## 6. 企业微信接入（可选）

配置以下变量后重启即启用（**Webhook 驱动**，需公网回调）：

```bash
export LLM_WIKI_WECOM_TOKEN="xxxx"
export LLM_WIKI_WECOM_AES_KEY="xxxx"        # 43 字符 EncodingAESKey
export LLM_WIKI_WECOM_CORPID="wwxxxx"
export LLM_WIKI_WECOM_SECRET="xxxx"
export LLM_WIKI_WECOM_AGENTID="1000002"
```

- 回调地址：`GET/POST /wechat/callback`（已实现签名校验 + XML 加解密被动回复）。
- 企业微信需**公网可达**回调（或内网穿透），与个人微信（iLink 轮询、无需公网）相反。
- 5s 被动回复超时不在套件范围，长任务走主动推送（`WeComAdapter.push_text`）。

---

## 7. 排错 FAQ

| 现象 | 排查 |
|------|------|
| `/healthz` 无 `ilink` | `LLM_WIKI_ENABLE_ILINK` 误设 `0` |
| `/ilink/qrcode` 返回「无法获取二维码」 | 多半是**没有 iLink Bot API 平台权限** |
| `connected` 一直 `false` | 未扫码 / 扫码后未确认 |
| 微信发消息无回复 | ① 查服务日志 `[ilink]`；② 确认 `connected:true`；③ `LLM_WIKI_API_KEY` 缺失会降级但仍有回复 |
| 答案被截断 1800 字 | iLink 单条限制已截断；更长需分段发送 |
| 24h 后不再回复 | 会话过期，按 §4.4 重激活 |
| `/chat` 返回 401 | 设了 `LLM_WIKI_BRIDGE_TOKEN`，请求带 `?token=xxx` 或 `X-Bridge-Token: xxx` |
| 端口被占 | `llmwiki serve --port 8001` 或释放原端口 |
| 换非 OpenAI 厂商 | 一并设 `LLM_WIKI_BASE_URL` + `LLM_WIKI_MODEL`；要求兼容 OpenAI `/chat/completions` |
| 弱图 / 不显示 | 缺 `qrcode` 库降级为链接；`pip install qrcode` 恢复 |

---

## 8. 安全注意事项

- **默认绑定 `127.0.0.1`**：`/chat`、`/recall` 仅本机；内网穿透暴露务必设 `LLM_WIKI_BRIDGE_TOKEN`。
- **token 不出本机**：`.ilink_session.json` 已 ignore，勿手动 `git add`。
- **iLink 走腾讯云**：非 P2P，受平台开放度与 ToS 约束，请合规使用。
- **凭证全环境变量**，不硬编码（`LLM_WIKI_*` 前缀下：`API_KEY` / `BRIDGE_TOKEN` / `WECOM_*` / `ILINK_*`）。

---

## 9. 最小可用命令清单（复制即用）

```bash
# 终端 1：装依赖 + 起服务
pip install "llmwiki-suite[wechat]"
export LLM_WIKI_API_KEY="sk-xxxx"; export LLM_WIKI_BRIDGE_TOKEN="my-secret"; export LLM_WIKI_ENABLE_ILINK="1"
cd ~/my-notes && llmwiki serve --host 127.0.0.1 --port 8000

# 终端 2：授权（浏览器打开 WebUI 扫码最省事）
curl -X POST "http://127.0.0.1:8000/ilink/activate?timeout=180"

# 终端 2：确认连上
curl http://127.0.0.1:8000/healthz    # -> ilink.connected == true

# 微信端：给 bot 发文本问题，等待回答
```

---

## 相关文档

- [[llmwiki-tutorial-01-system]]（体系搭建，本文前置）
- [[llmwiki-tutorial-03-quality-tuning]]（检索质量不满意时再看）
- [[llmwiki-architecture]]（系统架构总览）
- [[getting-started]]（五步快速上手）