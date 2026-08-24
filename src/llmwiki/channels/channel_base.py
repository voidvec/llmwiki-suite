# -*- coding: utf-8 -*-
"""
channel_base.py -- LlmWiki 通道适配器抽象（Channel Adapter 契约）

为什么需要这一层
----------------
知识库对外通道有两类驱动模型，必须统一抽象：

  1. Webhook 驱动（如企业微信）：外部平台把消息 POST 到我们的 HTTP 端点，
     我们在路由处理函数里同步回复。→ 通过 register_routes(app) 挂路由。
  2. 轮询驱动（如腾讯 iLink Bot API）：我们主动长轮询拉消息，收到后自己把
     回答推送回去。→ 通过 start()/stop() 管理后台线程。

ChannelAdapter 把这两种模型收口成统一接口，桥接服务（wechat_bridge.py）只负责
装配与生命周期，不关心具体通道细节。每个适配器持有一个 KbAssistant 引用，
调用 assistant.answer(text) 即可生成回答。

纯标准库，无 fastapi 依赖（ilink_adapter 因此可在无 fastapi 环境下单测）。
"""
from abc import ABC, abstractmethod


class ChannelAdapter(ABC):
    """所有微信/IM 通道的基类。子类按需覆盖下列方法。"""

    #: 通道标识，用于 /healthz 与日志
    name = "base"
    #: 通道人类可读描述
    description = ""

    def __init__(self, assistant):
        #: 应答编排层引用（召回 + LLM 生成都在这里）
        self.assistant = assistant

    # ---- Webhook 驱动：注册 HTTP 路由（轮询驱动默认 no-op）----
    def register_routes(self, app):
        """在 FastAPI app 上注册本通道所需的路由（如 /wechat/callback）。
        轮询驱动的适配器无需路由，默认空实现。"""
        return

    # ---- 轮询驱动：生命周期（Webhook 驱动默认 no-op）----
    def start(self):
        """启动后台轮询/监听；Webhook 驱动默认空实现。"""
        return

    def stop(self):
        """停止后台轮询/监听。"""
        return

    # ---- 状态上报 ----
    def health(self):
        """返回通道健康信息 dict，供 /healthz 聚合。"""
        return {"name": self.name, "enabled": True, "connected": False}