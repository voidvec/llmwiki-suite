# -*- coding: utf-8 -*-
"""
telegram_adapter.py -- Telegram Bot 通道适配器（Webhook 驱动）

Telegram Bot API 是所有通道里最简的：
  - 无需 app 审批，@BotFather 建 bot 即得 token；
  - 纯 JSON 无加密、无签名（用 secret token 做轻量鉴权）；
  - Webhook 模型：Telegram 把每条消息 POST 到 `/telegram/callback`，
    我们在路由里同步 assistant.answer 并调用 sendMessage 回复。

驱动模型：Webhook（无轮询线程）。与 WeComWebhook 相同，但无加解密负担。

凭证（环境变量）：TELEGRAM_BOT_TOKEN（必填）/ TELEGRAM_SECRET_TOKEN（可选，X-Telegram-Bot-Api-Secret-Token 鉴权）。

参考：https://core.telegram.org/bots/api#setwebhook
"""
import json
import logging
import urllib.parse
import urllib.request

from fastapi import Header, Request, Response

from .. import _env
from .channel_base import ChannelAdapter

LOG = logging.getLogger("telegram")

TELEGRAM_BOT_TOKEN = _env.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_SECRET_TOKEN = _env.getenv("TELEGRAM_SECRET_TOKEN", "")


class TelegramAdapter(ChannelAdapter):
    name = "telegram"
    description = "Telegram Bot（Webhook，@BotFather 建 bot 后设 webhook）"

    def _api(self, method: str, params: dict):
        if not TELEGRAM_BOT_TOKEN:
            return None
        url = ("https://api.telegram.org/bot%s/%s" % (TELEGRAM_BOT_TOKEN, method))
        body = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            LOG.warning("Telegram API 调用失败[%s]: %s", method, e)
            return None

    def register_routes(self, app):
        @app.post("/telegram/callback")
        async def telegram_callback(request: Request,
                                    x_telegram_bot_api_secret_token: str | None = Header(None)):
            if TELEGRAM_SECRET_TOKEN and \
                    x_telegram_bot_api_secret_token != TELEGRAM_SECRET_TOKEN:
                return Response("forbidden", status_code=403)
            body = await request.body()
            raw = body.decode("utf-8")
            try:
                update = json.loads(raw)
            except Exception as e:
                return {"error": "bad JSON: %s" % e}
            if not TELEGRAM_BOT_TOKEN:
                return {"hint": "配置 TELEGRAM_BOT_TOKEN 后实现应答",
                        "received_bytes": len(raw)}
            msg = update.get("message") or {}
            text = (msg.get("text") or "").strip()
            chat_id = (msg.get("chat") or {}).get("id")
            if not text or chat_id is None:
                # 非文本/无 chat 的更新直接 ack（Telegram 期望 200）
                return {"ok": True}
            try:
                answer, _ = self.assistant.answer(text)
            except Exception as e:
                LOG.error("Telegram 应答失败: %s", e)
                answer = "（知识库处理出错，请稍后重试）"
            self._api("sendMessage", {"chat_id": chat_id, "text": answer[:4000]})
            return {"ok": True}

    def health(self):
        return {"name": self.name, "enabled": True,
                "configured": bool(TELEGRAM_BOT_TOKEN)}