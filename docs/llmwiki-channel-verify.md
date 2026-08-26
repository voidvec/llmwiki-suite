# 飞书 / Telegram 通道 · 本地验证手册

> 只讲**本机验证**：不依赖真实消息，用 `curl` 模拟平台回调，即可确认
> 飞书（Feishu）与 Telegram 通道在本机 serve 里正确接通。

---

## 0. 先决条件

```bash
# ① 装渠道版（或已有 editable 安装，新增 adapter 已热载）
pip install "llmwiki-suite[serve]"

# ② 配置 LLM（OpenAI 兼容；至少给 KEY）
export LLM_WIKI_API_KEY="sk-xxx"
export LLM_WIKI_BASE_URL="https://api.openai.com/v1"
export LLM_WIKI_MODEL="gpt-4o-mini"

# ③ 库路径（默认当前目录，或用 --repo）
cd /d/work/development/Repos/docs/llmwiki-suite   # 换成你自己的 llmwiki-suite 路径
```

---

## 1. 启动 serve（含飞书 / Telegram 装配）

```bash
# 先配置通道凭据（注意：路由始终注册，缺凭据只影响 configured 状态与应答）
export LLM_WIKI_FEISHU_APP_ID="cli_xxxxxxxx"
export LLM_WIKI_FEISHU_APP_SECRET="xxxxxxxx"
export LLM_WIKI_FEISHU_VERIFY_TOKEN="my_verify_token"   # 可选（事件签名校验用）

export LLM_WIKI_TELEGRAM_BOT_TOKEN="123456:ABC-xxxx"
export LLM_WIKI_TELEGRAM_SECRET_TOKEN="my_secret"         # 可选（回调鉴权用）

# 启动
llmwiki serve --host 127.0.0.1 --port 8000
```

> 用命令行的 `export` 只在当前 shell 生效；**PowerShell 用 `$env:LLM_WIKI_FEISHU_APP_ID="cli_xxx"`**。
> 每次改完 env 后**不需要重启 serve**——adapter 在请求时动态读 env（热启停）。

启动后访问 `http://127.0.0.1:8000/healthz`，应看到各通道状态：

| 通道 | configured | enabled |
|---|---|---|
| feishu | ✅（两个变量都在） | ✅ |
| telegram | ✅ | ✅ |

> **注意**：路由始终注册（`enabled: true`），未配的通道显示 `configured: false`，
> 调用其回调端点会返回可读 `hint`（而不是 404）——例如
> `{"hint":"配置 LLM_WIKI_TELEGRAM_BOT_TOKEN 后实现应答", ...}`。
> 这是有意设计：`serve` 进程内改 env 即可热启用通道，无需重启。原文「未配则不注册路由」已过时。

### BRIDGE_TOKEN（本地验证可忽略）

`LLM_WIKI_BRIDGE_TOKEN` 只保护 `/chat`、`/recall` 问答接口；**不涉及飞书 /
Telegram 回调**（回调端点不走这个守卫）。本地只验证通道时不用管它；若宿主环境
残留了该变量（`/healthz` 显示 `bridge_token: true`）并想测问答，才需要在**当前
命令行**临时清空：

```bash
unset LLM_WIKI_BRIDGE_TOKEN        # Linux / macOS
Remove-Item Env:LLM_WIKI_BRIDGE_TOKEN   # PowerShell（当前会话）
```

---

## 2. 本地模拟验证（不触网，最快）

### 2.1 飞书 —— challenge 校验（平台接入前的敲门砖）

```bash
curl -s -X POST http://127.0.0.1:8000/feishu/callback \
  -H "Content-Type: application/json" \
  -d '{"challenge":"ch_abc123","type":"url_verification"}'
# 期望: {"challenge":"ch_abc123"}  ← 返回原文即通过（飞书开放平台也能判定成功）
```

### 2.2 飞书 —— 带签名校验的文本事件（模拟真实事件）

```bash
# 用一个 Python 脚本拼正确签名（因为要对 body 做 HMAC）
python - <<'PY'
import hmac, hashlib, json, time
import urllib.request

def sign(ts, nonce, body, secret):   # 与 feishu_adapter._verify_signature 一致（先排序拼接再 HMAC）
    s = "".join(sorted([secret, ts, nonce, body]))
    return hmac.new(secret.encode(), s.encode(), hashlib.sha256).hexdigest()

ts = str(int(time.time())); nonce = "n123"
body_obj = {
  "schema":"2.0","type":"event_callback","header":{
    "timestamp": ts, "nonce": nonce},   # 验签用 header 里的 ts/nonce
  "event":{"chat_id":"oc_demo","message":{"message_type":"text",
           "content":json.dumps({"text":"LLM_WIKI 自检：你是谁？"})}}
}
body = json.dumps(body_obj).encode()      # 先组装 JSON 字符串，再编码为 UTF-8 字节

secret = "your_verify_token"            # 与 LLM_WIKI_FEISHU_VERIFY_TOKEN 一致
sig = sign(ts, nonce, body, secret)
req = urllib.request.Request(
  "http://127.0.0.1:8000/feishu/callback",
  data=body, method="POST",
  headers={"Content-Type":"application/json",
           "X-Lark-Signature":sig,"X-Lark-Request-Timestamp":ts,"X-Lark-Request-Nonce":nonce})
print(urllib.request.urlopen(req).status)  # 期望 200
PY
```

> **签名一致性**：adapter 用「原始 request body 的 UTF-8 字节」+ 对
> `[verify_token, timestamp, nonce, body]` 先排序拼接、再 HMAC-SHA256（hex 小写）。
> 脚本里务必**先 `json.dumps` 得到字符串、再 `.encode()`**——请求体、签名用的
> `body` 必须同字节，否则验签必失败。若未设 `FEISHU_VERIFY_TOKEN`，飞书事件可
> 不用签名直接 POST（server 仅走可选校验）。

### 2.3 Telegram —— 文本消息事件注入（验证回环）

```bash
# 无 secret token 时（未设 TELEGRAM_SECRET_TOKEN）：
curl -s -X POST http://127.0.0.1:8000/telegram/callback \
  -H "Content-Type: application/json" \
  -d '{"update_id":101,"message":{"chat":{"id":12345},"text":"hello"}}'
# 期望 200 + {"ok": "accepted"}（assistant.answer 被调用并尝试 sendMessage）

# 设了 secret token 时，必须带对 header：
curl -s -X POST http://127.0.0.1:8000/telegram/callback \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my_secret" \
  -d '{"update_id":102,"message":{"chat":{"id":12345},"text":"hi there"}}'
# 错 token → 403；对 token → 200
```

---

## 附录：公网接线（本地验证通过后的可选扩展）

> 以下**不是本机验证必需**；接公网涉及域名、反代、平台后台，需要时再看。
> 本地验证只需第 1-2 节即可完成。

### A.1 Telegram（最简单）

```bash
# ① 设好 webhook（把回调指到你的公网 HTTPS 地址）
#    Telegram 要求公网 HTTPS，自签证书不可；可用 frp / ngrok / 腾讯云轻量负载均衡
curl -F "url=https://<你的域名>/telegram/callback" \
     -F "secret_token=my_secret" \
     "https://api.telegram.org/bot<TOKEN>/setWebhook"

# ② 验证 webhook 已设
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
# 期望 pending_update_count:0、url 指向你的回调

# ③ 直接在 Telegram 应用里给 bot 发消息 → 应收到知识库回答（带来源）
```

### A.2 飞书

```bash
# ① 飞书开放平台 → 应用 → 事件订阅 → 请求地址
#    填 https://<你的域名>/feishu/callback
# ② 订阅并启用 im.message.receive_v1 事件
# ③ 保存时飞书会先发 challenge 校验 → 应自动通过（我们的 adapter 应答 challenge）
# ④ 在飞书里给 bot 发消息 → 应收到回答
```

---

## 3. 常见问题

| 现象 | 原因 | 解法 |
|------|------|------|
| `/healthz` 里 feishu 显示 not configured | `FEISHU_APP_ID` 或 `FEISHU_APP_SECRET` 缺配 | 补全 env 后重启 serve |
| 飞书 challenge 返回非原文 | 回调地址填错 / 端口不通 | 先用第 2 节本地 curl 验证 |
| Telegram 返回 200 但 bot 不回复 | webhook 未设 / secret token 不对 | `getWebhookInfo` 看并发；核对 header |
| 报 `cannot unpack non-iterable` | 测试替身 mock 结构不对 | 用真实 `assistant`（本文档场景不会出现） |

---

## 4. 验收清单（本地）

- [ ] `serve` 启动无异常，`/healthz` 显示 feishu+telegram configured ✅
- [ ] 飞书 challenge 本地 curl 返回原文
- [ ] 飞书带签名字段事件 POST 200
- [ ] 无 secret token 的 Telegram 回调 POST 200；错误 secret → 403
