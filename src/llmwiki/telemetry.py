# -*- coding: utf-8 -*-
"""telemetry.py — 最简本地埋点（D2，全匿名、零上传、零第三方依赖）。

设计约束（对齐实施契约 D2 / 防漂移）：
  - **不上传任何数据**：事件只追加写到 ~/.llmwiki/telemetry/events.jsonl，
    由作者侧脚本统计。用户零隐私负担（无 PII、无路径、无主机名）。
  - **零依赖**：只用标准库（pathlib / json / datetime）。
  - **优雅降级**：任何异常静默吞掉，绝不影响主命令执行。
  - **3 事件 → 契约最简**：
      1. cli-run     — 每次命令行执行（防噪：同日同命令只记 1 条）
      2. eval-run    — eval 命令执行
      3. health-run  — health 命令执行（健康分使用痕迹，Q1 触发依据之一）

落地结构（可查询）：
  ~/.llmwiki/telemetry/
    events.jsonl   — 追加式事件流（JSON Lines）
    state.json     — 去重状态（{date: {cmd: ts}}）

用法：
  from .telemetry import record
  record("eval-run")
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from . import __version__

_TELE_DIR = Path.home() / ".llmwiki" / "telemetry"
_STATE_FILE = _TELE_DIR / "state.json"
_EVENTS_FILE = _TELE_DIR / "events.jsonl"


def _load_state() -> dict:
    try:
        if _STATE_FILE.is_file():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        _TELE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False),
                               encoding="utf-8")
    except Exception:
        pass


def record(event: str) -> bool:
    """追加一条本地事件（同日同事件去重）。返回是否写入（True=首次记，False=已去重/失败）。"""
    try:
        today = date.today().isoformat()
        state = _state = _load_state()
        if state.get(today, {}).get(event):
            return False  # 同日去重，抑制噪声
        _TELE_DIR.mkdir(parents=True, exist_ok=True)
        line = {
            "event": event,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "ver": __version__,
        }
        with open(_EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        state.setdefault(today, {})[event] = line["ts"]
        _save_state(state)
        return True
    except Exception:
        return False


def summarize() -> dict:
    """汇总已落盘事件（供作者本地查看/周报）。失败返回空 dict。"""
    try:
        if not _EVENTS_FILE.is_file():
            return {}
        out = {}
        for ln in _EVENTS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
            except Exception:
                continue
            k = e.get("event", "?")
            out[k] = out.get(k, 0) + 1
        return out
    except Exception:
        return {}