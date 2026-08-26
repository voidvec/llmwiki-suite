# -*- coding: utf-8 -*-
"""
feishu_adapter.py -- 飞书（Lark）通道适配器（Webhook 驱动）

飞书开放平台「事件订阅」模型：
  - URL 校验：GET/POST `challenge` 请求，需**原样返回 challenge**（明文 JSON，非签名）。
  - 消息事件：POST 带 `type: url_verification / event_callback`，消息在
    event.message 内；回复通过「机器人群聊 @ 应答」或「单聊」走 send message API。

为什么不需要加密：
  - 企业微信回调强制 AES 加解密；飞书机器人是 **服务端校验 + 主动调用 API**，
    用 app_id/app_secret 换 tenant_access_token。只有「浏览器网页/卡片」才需要加密。

凭证（环境变量，绝不硬编码）：FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_VERIFY_TOKEN（可选）。

依赖：fastapi（路由装饰器）。与 iLink 不同，飞书是 Webhook 驱动，无轮询线程。

参考：https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.request

from fastapi import Request, Response

from .. import _env
from .channel_base import ChannelAdapter

LOG = logging.getLogger("feishu")

FEISHU_APP_ID = _env.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = _env.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFY_TOKEN = _env.getenv("FEISHU_VERIFY_TOKEN", "")

# 飞书开放平台 API 根（国内版）
FEISHU_BASE = "https://open.feishu.cn/open-apis"
_TOK_CACHE = {"token": "", "exp": 0.0}


def _tenant_access_token() -> str:
    """换 tenant_access_token（2h 有效，缓存复用）。"""
    if _TOK_CACHE["token"] and time.time() < _TOK_CACHE["exp"]:
        return _TOK_CACHE["token"]
    body = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_BASE + "/auth/v3/tenant_access_token/internal",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("code", 0) != 0:
        raise RuntimeError("飞书获取 token 失败: %s" % d.get("msg"))
    _TOK_CACHE["token"] = d["tenant_access_token"]
    _TOK_CACHE["exp"] = time.time() + 7000  # 提前 200s 失效，避免临界
    return _TOK_CACHE["token"]


def _verify_signature(timestamp: str, nonce: str, body: str, sign: str) -> bool:
    """飞书事件签名校验（v1：sha256(sort(token,timestamp,nonce,body))）。"""
    if not body or not timestamp or not nonce or not sign:
        return False
    string_to_sign = "".join(sorted([FEISHU_VERIFY_TOKEN, timestamp, nonce, body]))
    calc = hmac.new(FEISHU_VERIFY_TOKEN.encode("utf-8"),
                    string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, sign)


class FeishuAdapter(ChannelAdapter):
    name = "feishu"
    description = "飞书自建应用（Webhook 事件订阅，需 APP_ID/APP_SECRET）"

    def register_routes(self, app):
        @app.post("/feishu/callback")
        async def feishu_callback(request: Request):
            """飞书事件订阅入口：
              - challenge：原样返回 challenge；
              - message 事件：提取文本 -> assistant.answer -> 用机器人发回消息。
            """
            body = await request.body()
            raw = body.decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception as e:
                return {"error": "bad JSON: %s" % e}
            if not FEISHU_APP_ID:
                return {"hint": "配置 FEISHU_APP_ID/FEISHU_APP_SECRET 后实现事件应答",
                        "received_bytes": len(raw)}

            # 1) challenge（URL 验证）
            if data.get("type") == "url_verification" or "challenge" in data:
                return {"challenge": data["challenge"]}

            if data.get("type") != "event_callback":
                return {"ok": False, "reason": "unsupported event type"}

            # 2) 事件签名校验（有 token 时；无 token 仅开发自测放行）
            header = data.get("header", {})
            if FEISHU_VERIFY_TOKEN:
                ts = header.get("timestamp", "")
                n = header.get("nonce", "")
                sign = header.get("signature", "")
                if not _verify_signature(ts, n, raw, sign):
                    return Response("invalid signature", status_code=403)

            # 3) 取消息文本
            message = (data.get("event") or {}).get("message") or {}
            msg_type = message.get("message_type", "")
            text = ""
            if msg_type == "text":
                try:
                    text = (message.get("content") or "")
                    # content 是 JSON 字符串：{"text":"..."}
                    text = json.loads(text).get("text", "") if text else ""
                except Exception:
                    text = ""
            if not text:
                # 非文本消息：回一个简短引导；不阻塞
                return {"ok": True, "unsupported": msg_type}

            # 4) 应答编排（诊断/答错由 assist 兜底，不抛给飞书）
            try:
                answer, _ = self.assistant.answer(text)
            except Exception as e:
                LOG.error("飞书应答失败: %s", e)
                answer = "（知识库处理出错，请稍后重试）"

            # 5) 通过机器人 API 主动回复（避免被动回复 3s 超时坑）
            chat_id = (data.get("event") or {}).get("chat_id") \
                      or (message.get("chat_id") or "")
            if chat_id:
                self.send_text(chat_id, answer)
            return {"ok": True}

    # ---- 主动发送（机器人消息 API）----
    def send_text(self, chat_id: str, text: str):
        """给指定 chat 发文本消息（飞书消息 API，不需会话 context）。"""
        try:
            token = _tenant_access_token()
            url = FEISHU_BASE + "/im/v1/messages?receive_id_type=chat_id"
            body = json.dumps({
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text[:1800]}, ensure_ascii=False),
            }).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Authorization": "Bearer " + token,
                         "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("code", 0) != 0:
                LOG.warning("飞书发送失败: %s", d.get("msg"))
                return False
            return True
        except Exception as e:
            LOG.warning("飞书发送异常: %s", e)
            return False

    def health(self):
        return {"name": self.name, "enabled": True,
                "configured": bool(FEISHU_APP_ID and FEISHU_APP_SECRET)}