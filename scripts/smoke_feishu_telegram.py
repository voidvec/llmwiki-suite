# -*- coding: utf-8 -*-
"""smoke_feishu_telegram.py — llmwiki 飞书 / Telegram 通道冒烟自检

不触网、不需要真实服务/token，用 FastAPI TestClient 在内存里验证两个适配器：
  1. 飞书 challenge 自动应答（返回原文）
  2. 飞书 hmac 签名校验：伪造签名被拒
  3. Telegram 无 secret 回调 → 200
  4. Telegram 错 secret token → 403；对 token → 200 且 assistant.answer 被调用

用法（在已 pip install -e . 的 venv 里）:
    python scripts/smoke_feishu_telegram.py
退出码：0 全过；1 任一失败。
"""
import hashlib
import hmac
import json
import os
import sys
from unittest.mock import Mock

# 关键：先清空环境，避免宿主真实 token 干扰
for k in (
    "LLM_WIKI_FEISHU_APP_ID",
    "LLM_WIKI_FEISHU_APP_SECRET",
    "LLM_WIKI_FEISHU_VERIFY_TOKEN",
    "LLM_WIKI_TELEGRAM_BOT_TOKEN",
    "LLM_WIKI_TELEGRAM_SECRET_TOKEN",
    "WECOM_TOKEN",
    "WECOM_AES_KEY",
):
    os.environ.pop(k, None)


def _app_client(assist):
    """构造一个装了飞书+Telegram 两类适配器的内存 TestClient。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from llmwiki.channels.feishu_adapter import FeishuAdapter
    from llmwiki.channels.telegram_adapter import TelegramAdapter

    app = FastAPI()
    feishu = FeishuAdapter(assist)
    tg = TelegramAdapter(assist)
    # 关键：stub 掉实际网络调用（sendMessage / 飞书发消息），避免 15s 超时
    feishu.send_text = lambda chat_id, text: True
    tg._api = lambda method, params: None
    feishu.register_routes(app)
    tg.register_routes(app)
    return TestClient(app)


def _mock_assistant():
    assist = Mock()
    assist.answer.return_value = ("（冒烟测试回答）", [])
    return assist


def _feishu_sig(ts, nonce, secret, body):
    """按 feishu_adapter._verify_signature 同款算法构造签名。
    v1 算法：sha256_hmac( token, key= joined_sorted(token, ts, nonce, body) )
    实际：string_to_sign = "".join(sorted([token, ts, nonce, body]))
         calc = hmac.new(token.encode(), string_to_sign.encode(), sha256)
    """
    joined = "".join(sorted([secret, ts, nonce, body]))
    return hmac.new(
        secret.encode("utf-8"), joined.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def main() -> int:
    from llmwiki.channels.feishu_adapter import _verify_signature

    # 统一假凭据：让通道走「已配置」路径（answer/校验），但不触网
    os.environ["LLM_WIKI_FEISHU_APP_ID"] = "cli_smoke"
    os.environ["LLM_WIKI_FEISHU_APP_SECRET"] = "sec_smoke"
    os.environ["LLM_WIKI_FEISHU_VERIFY_TOKEN"] = "123456"  # 数字，便于排序断言
    os.environ["LLM_WIKI_TELEGRAM_BOT_TOKEN"] = "123:SMOKE"

    results = []
    assist = _mock_assistant()

    # 1) 飞书 challenge：返回原文
    r = _app_client(assist).post(
        "/feishu/callback",
        json={"challenge": "ch_smoke", "type": "url_verification"},
    )
    ok = r.status_code == 200 and r.json().get("challenge") == "ch_smoke"
    results.append(("飞书 challenge 回声", ok, f"{r.status_code} {r.text[:60]}"))

    # 2) 飞书伪造签名 → 拒绝（verify False）
    ok = _verify_signature("t", "n", "body", "bogus") is False
    results.append(("飞书伪造签名拒绝", ok, f"verify(伪造)={not ok}"))

    # 3) 飞书正确签名 → 通过（算法自洽）
    body = json.dumps({"type": "event_callback", "event": {}})
    ts, nonce = "1720000000", "nonce1"
    sig = _feishu_sig(ts, nonce, os.environ["LLM_WIKI_FEISHU_VERIFY_TOKEN"], body)
    ok = _verify_signature(ts, nonce, body, sig) is True
    results.append(("飞书正确签名通过", ok, f"sig_len={len(sig)}"))

    # 3) 飞书事件处理链（无 verify_token 路径放行）→ 200 且调 answer
    #    签名算法本身已由 case2/3 验证；这里验证「事件 → assistant.answer → 回复」
    #    全链路（用故障注入避开 TestClient body 编码 vs 原始字节的差异）。
    assist.reset_mock()
    os.environ.pop("LLM_WIKI_FEISHU_VERIFY_TOKEN", None)  # 放行签名
    raw_body = json.dumps({
        "schema": "2.0", "type": "event_callback",
        "header": {"timestamp": "1720000000", "nonce": "nonce1"},
        "event": {"chat_id": "oc_demo",
                  "message": {"message_type": "text",
                              "content": '{"text":"你好"}'}},
    })
    r = _app_client(assist).post(
        "/feishu/callback", content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    ok = r.status_code == 200 and assist.answer.called
    results.append(("飞书事件处理链 → 200+answer", ok,
                    f"{r.status_code}, answer_called={assist.answer.called}"))

    # 4) Telegram 无 secret → 回调 200
    r = _app_client(assist).post(
        "/telegram/callback",
        json={"update_id": 1, "message": {"chat": {"id": 1}, "text": "hi"}},
    )
    ok = r.status_code == 200
    results.append(("Telegram 无secret 200", ok, str(r.status_code)))

    # 5) Telegram 错 secret → 403（需带 env 再装配）
    os.environ["LLM_WIKI_TELEGRAM_SECRET_TOKEN"] = "topsecret"
    r = _app_client(assist).post(
        "/telegram/callback",
        json={"update_id": 2, "message": {"chat": {"id": 2}, "text": "x"}},
        headers={"x-telegram-bot-api-secret-token": "wrong"},
    )
    ok = r.status_code == 403
    results.append(("Telegram 错 secret→403", ok, str(r.status_code)))

    # 6) Telegram 对 secret → 200 且 assistant.answer 被调用
    assist.reset_mock()
    r = _app_client(assist).post(
        "/telegram/callback",
        json={"update_id": 3, "message": {"chat": {"id": 3}, "text": "hello"}},
        headers={"x-telegram-bot-api-secret-token": "topsecret"},
    )
    ok = r.status_code == 200 and assist.answer.called
    results.append(
        ("Telegram 对 secret → 200+answer",
         ok, f"{r.status_code}, answer_called={assist.answer.called}")
    )

    print("\n=== llmwiki 飞书/Telegram 通道冒烟结果 ===")
    all_ok = True
    for name, passed, detail in results:
        flag = "PASS" if passed else "FAIL"
        all_ok &= passed
        print(f"[{flag}] {name}\n        {detail}")
    print(f"\n总体: {'ALL PASS' if all_ok else 'SOME FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())