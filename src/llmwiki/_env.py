"""环境变量集中读取 + 统一 LLM_WIKI_ 前缀。

统一前缀规则（2026-08-25，版本 0.2.0）：
  新名一律以 LLM_WIKI_ 开头，作为唯一权威来源：

      LLM_API_KEY        -> LLM_WIKI_API_KEY
      LLM_BASE_URL       -> LLM_WIKI_BASE_URL
      LLM_MODEL          -> LLM_WIKI_MODEL
      BRIDGE_TOKEN       -> LLM_WIKI_BRIDGE_TOKEN
      WECOM_*            -> LLM_WIKI_WECOM_*            （5 个）
      ILINK_*            -> LLM_WIKI_ILINK_*            （4 个）
      KB_INDEX           -> LLM_WIKI_KB_INDEX
      ENABLE_ILINK       -> LLM_WIKI_ENABLE_ILINK

旧名（无前缀）仍兼容读取；读到旧名时打印一次弃用告警。
"""
from __future__ import annotations

import os
import sys

_WARNED: set[str] = set()

# 旧名 -> 新名 映射（用于兼容读取 + 告警文案）
_LEGACY: dict[str, str] = {
    "LLM_API_KEY": "LLM_WIKI_API_KEY",
    "LLM_BASE_URL": "LLM_WIKI_BASE_URL",
    "LLM_MODEL": "LLM_WIKI_MODEL",
    "BRIDGE_TOKEN": "LLM_WIKI_BRIDGE_TOKEN",
    "WECOM_TOKEN": "LLM_WIKI_WECOM_TOKEN",
    "WECOM_AES_KEY": "LLM_WIKI_WECOM_AES_KEY",
    "WECOM_CORPID": "LLM_WIKI_WECOM_CORPID",
    "WECOM_SECRET": "LLM_WIKI_WECOM_SECRET",
    "WECOM_AGENTID": "LLM_WIKI_WECOM_AGENTID",
    "ILINK_BASE_URL": "LLM_WIKI_ILINK_BASE_URL",
    "ILINK_CDN_BASE_URL": "LLM_WIKI_ILINK_CDN_BASE_URL",
    "ILINK_SESSION_FILE": "LLM_WIKI_ILINK_SESSION_FILE",
    "ILINK_BOT_TOKEN": "LLM_WIKI_ILINK_BOT_TOKEN",
    "KB_INDEX": "LLM_WIKI_KB_INDEX",
    "ENABLE_ILINK": "LLM_WIKI_ENABLE_ILINK",
}

# 反向：新名 -> 旧名（用于告警展示）
_NEW_TO_LEGACY = {v: k for k, v in _LEGACY.items()}


def _warn_once(old: str, new: str) -> None:
    if old in _WARNED:
        return
    _WARNED.add(old)
    print(
        f"[llmwiki] 环境变量 {old} 已改名为 {new}，请改用新前缀（旧名仍兼容，仅提示一次）",
        file=sys.stderr,
    )


def getenv(name: str, default: str = "") -> str:
    """读取环境变量，优先 llm_wiki 前缀（LLM_WIKI_<name>），回退旧名。

    name   新变量短名，如 "API_KEY" / "BRIDGE_TOKEN" / "WECOM_TOKEN"。
    返回   str；默认走 default。
    """
    new = f"LLM_WIKI_{name}"
    if new in os.environ:
        return os.environ[new]
    legacy = _NEW_TO_LEGACY.get(new, name)
    if legacy in os.environ:
        _warn_once(legacy, new)
        return os.environ[legacy]
    return default
