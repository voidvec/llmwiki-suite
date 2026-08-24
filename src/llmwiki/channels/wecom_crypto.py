# -*- coding: utf-8 -*-
"""
wecom_crypto.py -- 企业微信消息加解密（WXBizMsgCrypt 标准算法）

企业微信回调要求：URL 校验（GET，回显解密 echostr）与消息收发（POST，XML 密文）
都必须做「签名校验 + AES-256-CBC 加解密」。本模块实现官方规范算法，可直接复用。

算法要点（官方 sample 一致）：
  - EncodingAESKey：43 字节 Base64（无填充），解码得 32 字节 AES Key；IV = Key 前 16 字节。
  - 明文结构：random(16) + msg_len(4 字节大端) + msg + receiveid(corpid)。
  - 签名：sha1(sorted(token, timestamp, nonce, encrypt) 拼接)。
  - 块大小 32，PKCS7 填充。

依赖：pycryptodome（`pip install pycryptodome`）。仅 bridge 使用，lint/ingest 不涉及。
离线可测：用同一 token/aeskey/corpid 加密后再解密应得到原文（见文件末尾自检）。
"""
import os
import base64
import socket
import struct
import hashlib

try:
    from Crypto.Cipher import AES
except ImportError:  # 友好提示，避免 fastapi 启动即崩
    AES = None

BLOCK_SIZE = 32


class WXBizMsgCrypt:
    def __init__(self, token, encoding_aes_key, receive_id):
        self.token = token
        self.key = base64.b64decode(encoding_aes_key + "=")
        if len(self.key) != 32:
            raise ValueError("EncodingAESKey 解码后必须为 32 字节")
        self.iv = self.key[:16]
        self.receive_id = receive_id

    # ---- 基础 ----
    def _sha1(self, *parts):
        s = "".join(sorted(parts))
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    @staticmethod
    def _pkcs7_pad(text):
        pad = BLOCK_SIZE - (len(text) % BLOCK_SIZE)
        if pad == 0:
            pad = BLOCK_SIZE
        return text + bytes([pad]) * pad

    @staticmethod
    def _pkcs7_unpad(text):
        pad = text[-1]
        if pad < 1 or pad > BLOCK_SIZE:
            return text
        return text[:-pad]

    def _encrypt(self, text_bytes):
        if AES is None:
            raise RuntimeError("pycryptodome 未安装：pip install pycryptodome")
        rand = os.urandom(16)
        msg_len = struct.pack(">I", len(text_bytes))
        raw = rand + msg_len + text_bytes + self.receive_id.encode("utf-8")
        padded = self._pkcs7_pad(raw)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        enc = cipher.encrypt(padded)
        return base64.b64encode(enc).decode("utf-8")

    def _decrypt(self, b64_text):
        if AES is None:
            raise RuntimeError("pycryptodome 未安装：pip install pycryptodome")
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        raw = cipher.decrypt(base64.b64decode(b64_text))
        raw = self._pkcs7_unpad(raw)
        content = raw[16:]  # 去随机前缀
        msg_len = struct.unpack(">I", content[:4])[0]
        msg = content[4:4 + msg_len]
        from_id = content[4 + msg_len:]
        return msg.decode("utf-8"), from_id.decode("utf-8")

    # ---- 对外：URL 校验 ----
    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        sig = self._sha1(self.token, timestamp, nonce, echostr)
        if sig != msg_signature:
            raise ValueError("签名校验失败")
        plain, _ = self._decrypt(echostr)
        return plain

    # ---- 对外：解密消息 ----
    def decrypt_msg(self, msg_signature, timestamp, nonce, post_data):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(post_data)
        enc = root.findtext("Encrypt")
        sig = self._sha1(self.token, timestamp, nonce, enc)
        if sig != msg_signature:
            raise ValueError("签名校验失败")
        plain, from_id = self._decrypt(enc)
        if from_id != self.receive_id:
            raise ValueError("receiveid 不匹配")
        return plain  # 明文 XML（含 MsgType/Content/FromUserName...）

    # ---- 对外：加密被动回复 ----
    def encrypt_msg(self, reply_text, nonce, timestamp=None):
        import time
        import xml.etree.ElementTree as ET
        if timestamp is None:
            timestamp = str(int(time.time()))
        enc = self._encrypt(reply_text.encode("utf-8"))
        sig = self._sha1(self.token, timestamp, nonce, enc)
        xml = (
            "<xml><Encrypt><![CDATA[%s]]></Encrypt>"
            "<MsgSignature><![CDATA[%s]]></MsgSignature>"
            "<TimeStamp>%s</TimeStamp><Nonce><![CDATA[%s]]></Nonce></xml>"
            % (enc, sig, timestamp, nonce)
        )
        return xml


def get_access_token(corpid, secret, cache=None):
    """获取企业微信 access_token（用于主动推送/客服消息，绕过 5s 被动回复限制）。
    cache 为可选 dict，做内存缓存（微信 token 有效期 7200s）。"""
    if cache is not None and cache.get("token"):
        return cache["token"]
    import urllib.request, json
    url = ("https://qyapi.weixin.qq.com/cgi-bin/gettoken"
           "?corpid=%s&corpsecret=%s" % (corpid, secret))
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("errcode", 0) != 0:
        raise RuntimeError("获取 access_token 失败: %s" % d)
    token = d["access_token"]
    if cache is not None:
        cache["token"] = token
    return token


if __name__ == "__main__":
    # 离线自检：加密→解密应还原原文（validate the tool itself）。
    import binascii
    token = "tok"
    aes = base64.b64encode(os.urandom(32)).decode("utf-8")[:43]  # 43 字符模拟 EncodingAESKey
    corpid = "wwdummy"
    c = WXBizMsgCrypt(token, aes, corpid)
    sample = "<xml><Content><![CDATA[你好知识库]]></Content></xml>"
    nonce, ts = "n123", "1700000000"
    enc = c._encrypt(sample.encode("utf-8"))
    # 模拟解密路径：构造签名 + 伪装 Encrypt 包
    sig = c._sha1(token, ts, nonce, enc)
    xml_in = "<xml><Encrypt><![CDATA[%s]]></Encrypt></xml>" % enc
    out = c.decrypt_msg(sig, ts, nonce, xml_in)
    print("round-trip ok:" if out == sample else "FAIL", out)
