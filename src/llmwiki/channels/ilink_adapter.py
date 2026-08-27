# -*- coding: utf-8 -*-
"""
ilink_adapter.py -- 腾讯 iLink Bot API 适配器（个人微信，官方网关，免 Wechaty puppet）

为什么需要它
------------
接「个人微信」通常有三条路（详见 docs/llmwiki-architecture.md）：
  ① 本地 hook（wcferry/gewechat）：注入桌面微信，有封号风险，mac/Linux 难跑；
  ② Wechaty + 商业 puppet（PadLocal ≈ ¥299/年）：稳但收费；
  ③ 腾讯官方 iLink Bot API：个人号扫码注册成 bot，经官方网关收发，免费、官方、
     无头跨平台——cc-go 项目正是走这条路，本适配器复刻其接口契约。

接口契约（与 cc-go/internal/wechat/client.go 逐字段对齐）
---------------------------------------------------------
  鉴权头：AuthorizationType: ilink_bot_token
          Authorization: Bearer <bot_token>   （有 token 时）
          X-WECHAT-UIN: base64(rand uin)
  取码   GET  ilink/bot/get_bot_qrcode?bot_type=3   -> {qrcode, qrcode_img_content}
  查态   GET  ilink/bot/get_qrcode_status?qrcode=X  -> {status:"confirmed", bot_token, baseurl}
  收消息 POST ilink/bot/getupdates                  -> {get_updates_buf, msgs:[...]}
  发消息 POST ilink/bot/sendmessage                 -> 见 _send_raw
  心跳/激活：会话约 24h 过期，重激活链接 liteapp.weixin.qq.com/q/...?qrcode=X&bot_type=3

消息结构（getupdates.msgs[]）：
  {from_user_id, to_user_id, message_type, message_state, context_token,
   item_list:[{type:1, text_item:{text}}]}

驱动模型：轮询驱动（ChannelAdapter.start() 起后台线程长轮询，收文本 -> assistant.answer
-> sendmessage）。与 WeCom 的 Webhook 模型不同，故本适配器实现 start()/stop() 而非路由。

安全与限制
----------
  - bot_token 落本地会话文件（默认 .ilink_session.json），**绝不入库**（已加 .gitignore）。
  - 启动时若会话文件有效（<24h）直接复用 token，免重新扫码。
  - v1 仅支持文本问答；图片/文件走官方 CDN AES-ECB 上传，复杂度高，本期不做。
  - 仅依赖标准库；与知识库检索零耦合（通过构造函数注入 KbAssistant）。

环境变量：ILINK_BASE_URL / ILINK_CDN_BASE_URL / ILINK_BOT_TOKEN / ILINK_SESSION_FILE
"""
import os
import json
import time
import base64
import random
import logging
import threading
import urllib.request
import urllib.parse

from .. import _env
from .channel_base import ChannelAdapter

LOG = logging.getLogger("ilink")

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
CHANNEL_VERSION = "1.0.2"
SESSION_TTL = 24 * 3600  # 与 cc-go DefaultReconnectConfig.SessionDuration 一致
ACTIVATION_APP = "https://liteapp.weixin.qq.com/q/7GiQu1"


class IlinkAdapter(ChannelAdapter):
    name = "ilink"
    description = "腾讯 iLink Bot API（个人微信，官方网关，免 puppet）"

    def __init__(self, assistant, base_url=None, cdn_base_url=None,
                 session_file=None, bot_token=None):
        super().__init__(assistant)
        self.base_url = (base_url or _env.getenv("ILINK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.cdn_base_url = (cdn_base_url or _env.getenv("ILINK_CDN_BASE_URL") or DEFAULT_CDN_BASE_URL).rstrip("/")
        self.session_file = session_file or _env.getenv("ILINK_SESSION_FILE") or ".ilink_session.json"
        self.bot_token = bot_token or _env.getenv("ILINK_BOT_TOKEN") or ""
        self.baseurl_override = ""
        self.login_time = 0.0
        # 运行时状态
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._updates_buf = ""
        self.last_contact = {"from_user_id": "", "context_token": ""}
        self.connected = False
        # 激活期状态（供 WebUI 复用同一二维码，避免刷新重复生成）
        self._pending_qrcode = ""
        self._pending_svg = ""
        self._wait_thread = None
        # 启动即尝试恢复会话（有 token 才能直接进入轮询）
        self._load_session()

    # ---- 持久化 ----
    def _save_session(self):
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump({
                    "bot_token": self.bot_token,
                    "baseurl": self.baseurl_override,
                    "login_time": self.login_time,
                }, f)
        except Exception as e:
            LOG.warning("保存 iLink 会话失败: %s", e)

    def _load_session(self):
        if self.bot_token:
            return
        if not os.path.exists(self.session_file):
            return
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                s = json.load(f)
            self.bot_token = s.get("bot_token", "")
            self.baseurl_override = s.get("baseurl", "")
            self.login_time = s.get("login_time", 0.0)
            if self.baseurl_override:
                self.base_url = self.baseurl_override
            if self.bot_token:
                LOG.info("恢复 iLink 会话（login_time=%s）",
                         time.strftime("%Y-%m-%d %H:%M", time.localtime(self.login_time)) if self.login_time else "?")
        except Exception as e:
            LOG.warning("读取 iLink 会话失败: %s", e)

    def _session_valid(self):
        if not self.bot_token:
            return False
        if not self.login_time:
            return True  # 无 login_time 也先尝试用（兼容仅给 token 的场景）
        return (time.time() - self.login_time) < SESSION_TTL

    # ---- HTTP（统一收口，便于单测 mock）----
    def _headers(self):
        h = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": base64.b64encode(str(random.randint(0, 2 ** 31)).encode()).decode(),
        }
        if self.bot_token:
            h["Authorization"] = "Bearer " + self.bot_token
        return h

    def _request(self, method, path, body=None, timeout=60):
        url = self.base_url + "/" + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in self._headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            # 在异常里带上实际请求的 URL，便于排查是哪台 host 触网失败：
            # 例如激活返回的 baseurl 与默认 host 可达性不同、或长轮询(~35s)被
            # 代理/防火墙掐断、或本机/服务端网络抖动。
            raise RuntimeError("iLink 请求失败 [%s] %s: %s" % (method, url, e)) from e
        return json.loads(raw)

    # ---- 激活：拉码 / 等待扫码 ----
    def get_qrcode(self):
        """拉取绑定二维码（bot_type=3 个人号）。返回 (qrcode, activation_link, qr_svg)。

        iLink 的 get_bot_qrcode 只返回二维码 token 与「激活链接」(activation_link)，
        并不返回图片二进制；图片由本适配器把激活链接编码成二维码 SVG 在本地生成
        （与 cc-go 桌面端用 webview 把激活链接渲染成二维码图形的做法一致）。
        """
        r = self._request("GET", "ilink/bot/get_bot_qrcode?bot_type=3")
        qr = r.get("qrcode", "")
        if not qr:
            return "", "", ""
        link = (r.get("activation_link")
                or r.get("qrcode_img_base64")
                or r.get("qrcode_img_content")
                or self.activation_link(qr))
        svg = ""
        try:
            svg = self._make_qr_svg(link)
        except Exception as e:
            # 缺 qrcode 库时降级：仍返回 activation_link，WebUI 会提示用链接在微信内打开
            LOG.warning("[ilink] 二维码图生成失败（可能缺少 qrcode 库，pip install qrcode 即可）: %s", e)
        return qr, link, svg

    @staticmethod
    def _make_qr_svg(text, box_size=8, border=4):
        """把任意文本（这里是激活链接）编码成二维码 SVG 字符串，零外部图片依赖。
        使用 qrcode 库（纯 Python，get_matrix 无需 Pillow）。"""
        import qrcode
        qr = qrcode.QRCode(box_size=box_size, border=border,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(text)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        n = len(matrix)
        dim = n * box_size
        rects = []
        for r in range(n):
            for c in range(n):
                if matrix[r][c]:
                    x = c * box_size
                    y = r * box_size
                    rects.append("M%d %dh%dv%dh-%dz" % (x, y, box_size, box_size, box_size))
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" '
                'viewBox="0 0 %d %d" shape-rendering="crispEdges">'
                '<rect width="100%%" height="100%%" fill="#ffffff"/>'
                '<path fill="#000000" d="%s"/></svg>'
                % (dim, dim, "".join(rects)))

    def check_qrcode_status(self, qrcode):
        """轮询扫码状态；confirmed 时返回 (True, bot_token, baseurl)。"""
        r = self._request("GET", "ilink/bot/get_qrcode_status?qrcode=" + urllib.parse.quote(qrcode))
        if r.get("status") == "confirmed":
            return True, r.get("bot_token", ""), r.get("baseurl", "")
        return False, "", ""

    def activate(self, qrcode=None, timeout=180, interval=2, on_done=None):
        """等待用户扫码激活（内部轮询 get_qrcode_status）。返回 (ok, detail)。
        qrcode 可外部提供（先调 get_qrcode）；不提供则内部先拉码。
        on_done：无论成功/超时均回调一次（用于清理 pending 二维码）。"""
        try:
            if not qrcode:
                qrcode, _, _ = self.get_qrcode()
            if not qrcode:
                return False, "无法获取二维码"
            deadline = time.time() + timeout
            while time.time() < deadline:
                ok, token, baseurl = self.check_qrcode_status(qrcode)
                if ok:
                    with self._lock:
                        self.bot_token = token
                        if baseurl:
                            self.baseurl_override = baseurl
                            self.base_url = baseurl
                        self.login_time = time.time()
                        self.connected = True  # 扫码激活成功立即标记为已连接
                    self._save_session()
                    LOG.info("iLink 激活成功")
                    return True, "activated"
                time.sleep(interval)
            return False, "等待扫码超时"
        finally:
            if on_done:
                on_done()

    def start_activation(self, timeout=180, interval=2):
        """确保已生成二维码且后台等待线程在运行；WebUI 刷新时复用同一二维码，
        避免重复生成多个码。返回 (qrcode, activation_link, qr_svg)。"""
        with self._lock:
            if self._wait_thread and self._wait_thread.is_alive() and self._pending_qrcode:
                return self._pending_qrcode, self.activation_link(self._pending_qrcode), self._pending_svg
        qr, link, svg = self.get_qrcode()
        if not qr:
            return "", "", ""
        self._pending_qrcode = qr
        self._pending_svg = svg

        def _wait():
            self.activate(qr, timeout=timeout, interval=interval, on_done=self._clear_pending)

        self._wait_thread = threading.Thread(target=_wait, name="ilink-activate", daemon=True)
        self._wait_thread.start()
        return qr, link, svg

    def _clear_pending(self):
        with self._lock:
            self._pending_qrcode = ""
            self._pending_svg = ""

    def activation_link(self, qrcode):
        return ACTIVATION_APP + "?qrcode=%s&bot_type=3" % urllib.parse.quote(qrcode)

    # ---- 收发 ----
    @staticmethod
    def _parse_msgs(raw_list):
        """把 getupdates.msgs 解析为本适配器使用的字典列表（对齐 cc-go parseMessage）。"""
        out = []
        for raw in (raw_list or []):
            rm = raw if isinstance(raw, dict) else {}
            msg = {
                "from_user_id": rm.get("from_user_id", ""),
                "to_user_id": rm.get("to_user_id", ""),
                "message_type": int(rm.get("message_type", 0) or 0),
                "message_state": int(rm.get("message_state", 0) or 0),
                "context_token": rm.get("context_token", ""),
                "text": "",
            }
            for item in (rm.get("item_list") or []):
                if isinstance(item, dict) and int(item.get("type", 0) or 0) == 1:
                    ti = item.get("text_item") or {}
                    msg["text"] = ti.get("text", "")
                    break
            out.append(msg)
        return out

    def poll_once(self, timeout_ms=35000):
        """一次长轮询。返回解析后的消息列表（调用方按 message_type 过滤）。"""
        body = {"get_updates_buf": self._updates_buf,
                "base_info": {"channel_version": CHANNEL_VERSION}}
        r = self._request("POST", "ilink/bot/getupdates", body,
                          timeout=max(timeout_ms // 1000 + 10, 10))
        buf = r.get("get_updates_buf")
        if buf:
            with self._lock:
                self._updates_buf = buf
        return self._parse_msgs(r.get("msgs"))

    def send(self, to_user_id, context_token, text):
        """发送文本消息（item_list type=1 text_item）。返回是否成功。"""
        client_id = "llmwiki-%08x" % random.randint(0, 2 ** 31)
        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token,
                "item_list": [{"type": 1, "text_item": {"text": text[:1800]}}],
            },
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        try:
            self._request("POST", "ilink/bot/sendmessage", body, timeout=30)
            return True
        except Exception as e:
            LOG.error("iLink 发送失败: %s", e)
            return False

    # ---- 后台轮询循环（轮询驱动核心）----
    def _loop(self):
        LOG.info("iLink 轮询线程启动")
        while not self._stop.is_set():
            if not self.bot_token:
                time.sleep(3)
                continue
            if not self._session_valid():
                # 会话过期：尝试给最近联系人发重激活提醒（镜像 cc-go 行为），
                # 随后等待外部重新激活（用户点链接 或 调 /ilink/activate）。
                with self._lock:
                    self.connected = False
                self._notify_relogin()
                time.sleep(30)
                continue
            try:
                msgs = self.poll_once()
                for m in msgs:
                    if m["message_type"] != 1:  # 仅处理文本消息
                        continue
                    text = (m.get("text") or "").strip()
                    if not text:
                        continue
                    with self._lock:
                        self.last_contact = {"from_user_id": m["from_user_id"],
                                             "context_token": m["context_token"]}
                        self.connected = True
                    try:
                        answer, _ = self.assistant.answer(text)
                    except Exception as e:
                        LOG.error("应答失败: %s", e)
                        answer = "（知识库处理出错，请稍后重试）"
                    self.send(m["from_user_id"], m["context_token"], answer)
            except Exception as e:
                LOG.warning("iLink 轮询异常: %s", e)
                with self._lock:
                    self.connected = False
                time.sleep(3)
        LOG.info("iLink 轮询线程退出")

    def _notify_relogin(self):
        ct = self.last_contact
        if not ct.get("from_user_id"):
            return
        try:
            qr, _, _ = self.get_qrcode()
            link = self.activation_link(qr)
            self.send(ct["from_user_id"], ct["context_token"],
                      "### 登录提醒\n\n机器人会话已过期，请点击重新激活：%s" % link)
        except Exception as e:
            LOG.warning("发送重激活提醒失败: %s", e)

    # ---- ChannelAdapter 接口 ----
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ilink-poll", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def health(self):
        return {
            "name": self.name,
            "enabled": True,
            "connected": self.connected,
            "has_token": bool(self.bot_token),
            "session_valid": self._session_valid(),
        }
