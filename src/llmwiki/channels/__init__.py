# -*- coding: utf-8 -*-
"""channels — 可选通道插件（需安装 extras: llmwiki[wechat]）。

M3（S2 里程碑）迁移：channel_base / ilink_adapter / wecom_adapter /
wecom_crypto / wechat_bridge。serve 子命令届时在此提供。

通道清单（ChannelAdapter 子类，按需装配进 wechat_bridge.app）：
  - ilink_adapter.IlinkAdapter     个人微信（iLink Bot API，轮询驱动，免费官方，免公网）
  - wecom_adapter.WeComAdapter       企业微信（Webhook 回调，AES 加解密）
  - feishu_adapter.FeishuAdapter     飞书 / Lark（Webhook 事件订阅，challenge + token）
  - telegram_adapter.TelegramAdapter Telegram（Webhook setWebhook，最简，secret 鉴权）
"""
