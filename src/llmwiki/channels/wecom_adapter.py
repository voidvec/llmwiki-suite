# -*- coding: utf-8 -*-
"""
wecom_adapter.py -- 企业微信通道适配器（Webhook 驱动）

把原 wechat_bridge.py 里内联的企业微信回调逻辑迁出来，成为 ChannelAdapter 的
一个实现。企业微信是「平台主动回调」模型：URL 校验（GET 回显 echostr）与消息收发
（POST 收 XML 密文 → 解密 → 召回问答 → 加密被动回复 XML）都在路由处理函数里同步完成。

凭证（环境变量，绝不硬编码）：WECOM_TOKEN / WECOM_AES_KEY(43字符 EncodingAESKey)
  / WECOM_CORPID / WECOM_SECRET / WECOM_AGENTID。

被动回复有 5s 超时限制；若 LLM 生成耗时较长，可改用 push_text() 主动推送
（get_access_token + message/send）绕过限制。

依赖：fastapi（路由装饰器）+ wecom_crypto（WXBizMsgCrypt 官方加解密）。
"""
import os
import json
import time
import logging
import threading
import urllib.request
import xml.etree.ElementTree as ET

from fastapi import Request, Response

from .. import _env
from .channel_base import ChannelAdapter

LOG = logging.getLogger("wecom")

WECOM_TOKEN = _env.getenv("WECOM_TOKEN", "")
WECOM_AES_KEY = _env.getenv("WECOM_AES_KEY", "")
WECOM_CORPID = _env.getenv("WECOM_CORPID", "")
WECOM_SECRET = _env.getenv("WECOM_SECRET", "")
WECOM_AGENTID = _env.getenv("WECOM_AGENTID", "")


class WeComAdapter(ChannelAdapter):
    name = "wecom"
    description = "企业微信自建应用（Webhook 回调，需 CorpID/AgentID/Secret）"

    # ---- 加解密实例（配置齐全才可用）----
    def _crypt(self):
        if not (WECOM_TOKEN and WECOM_AES_KEY and WECOM_CORPID):
            return None
        try:
            from wecom_crypto import WXBizMsgCrypt
            return WXBizMsgCrypt(WECOM_TOKEN, WECOM_AES_KEY, WECOM_CORPID)
        except Exception:
            return None

    # ---- Webhook 路由 ----
    def register_routes(self, app):
        @app.get("/wechat/callback")
        def wecom_verify(msg_signature: str = "", timestamp: str = "",
                         nonce: str = "", echostr: str = ""):
            """企业微信 URL 校验：验签并回显解密 echostr。"""
            crypt = self._crypt()
            if not crypt:
                return {"hint": "配置 WECOM_TOKEN/WECOM_AES_KEY/WECOM_CORPID 后实现企业微信签名校验，回显解密 echostr"}
            try:
                plain = crypt.verify_url(msg_signature, timestamp, nonce, echostr)
                return plain
            except Exception as e:
                return {"error": "verify_url 失败: %s" % e}

        @app.post("/wechat/callback")
        async def wecom_msg(request: Request):
            """企业微信消息入口：验签+解密 -> 召回问答 -> 加密被动回复。"""
            crypt = self._crypt()
            if not crypt:
                body = await request.body()
                return {"hint": "企业微信消息入口：配置 WECOM_* 后解析 XML Content 调 answer 并加密回复",
                        "received_bytes": len(body)}
            try:
                data = await request.body()
                post_xml = data.decode("utf-8")
                qs = dict(request.query_params)
                plain = crypt.decrypt_msg(
                    qs.get("msg_signature", ""), qs.get("timestamp", ""),
                    qs.get("nonce", ""), post_xml,
                )
                msg = self._xml_text(plain)
                answer, _ = self.assistant.answer(msg["content"])
                reply = self._passive_reply_xml(msg["from"], msg["to"], answer)
                enc = crypt.encrypt_msg(
                    reply, qs.get("nonce", "n"),
                    qs.get("timestamp", str(int(time.time()))),
                )
                return Response(enc, media_type="application/xml")
            except Exception as e:
                return {"error": "wechat_msg 处理失败: %s" % e}

    # ---- 被动回复 XML（文本上限约 2048 字节，超长截断）----
    def _passive_reply_xml(self, to_user, from_user, content):
        ts = int(time.time())
        content = content[:1800]
        return (
            "<xml><ToUserName><![CDATA[%s]]></ToUserName>"
            "<FromUserName><![CDATA[%s]]></FromUserName>"
            "<CreateTime>%d</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[%s]]></Content></xml>"
            % (to_user, from_user, ts, content)
        )

    @staticmethod
    def _xml_text(xml_bytes):
        root = ET.fromstring(xml_bytes)
        return {
            "content": root.findtext("Content") or "",
            "from": root.findtext("FromUserName") or "",
            "to": root.findtext("ToUserName") or "",
        }

    # ---- 主动推送（绕过 5s 被动回复超时）----
    def push_text(self, user_id, text):
        if not (WECOM_SECRET and WECOM_AGENTID):
            LOG.warning("企业微信主动推送未配置 WECOM_SECRET/WECOM_AGENTID")
            return False
        try:
            from wecom_crypto import get_access_token
            token = get_access_token(WECOM_CORPID, WECOM_SECRET)
            url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + token
            body = json.dumps({
                "touser": user_id, "msgtype": "text",
                "agentid": int(WECOM_AGENTID),
                "text": {"content": text[:1800]},
            }).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8")).get("errcode", 1) == 0
        except Exception as e:
            LOG.warning("企业微信主动推送失败: %s", e)
            return False

    def health(self):
        return {"name": self.name, "enabled": True,
                "configured": self._crypt() is not None}
