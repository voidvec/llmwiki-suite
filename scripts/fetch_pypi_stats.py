#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_pypi_stats.py — 曝光监控：抓取 PyPI 下载统计（数析 D4 前置，D2 作者侧）。
仅用标准库（urllib.request / json），零第三方依赖。作者侧运行，产物写 JSON。

用法：
  python scripts/fetch_pypi_stats.py            # 默认包名 llmwiki-suite，输出到控制台
  python scripts/fetch_pypi_stats.py --out stats/pypi-daily.json
  python scripts/fetch_pypi_stats.py --since 2026-08-20 --days 14

数据源：https://pypistats.org/api/packages/<name>/recent（聚合） 
         https://pypistats.org/api/packages/<name>/overall（历史，按天）
说明：PyPI 无细粒度 per-day 公开 API；pypistats 的 overview 可给出近似日分布。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

DEFAULT_PKG = "llmwiki-suite"
API_RECENT = "https://pypistats.org/api/packages/{name}/recent"
API_OVERVIEW = "https://pypistats.org/api/packages/{name}/overall"


def _fetch(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "llmwiki-obs/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_stats(name: str) -> dict:
    """拉取 recent + overall（overall 失败不影响 recent，429 降级友好）。"""
    import time as _time
    out = {"package": name, "fetched_at": None, "recent": None,
           "overview": None, "error": None}
    try:
        recent = _fetch(API_RECENT.format(name=name))
        out["recent"] = recent.get("data", {})
        out["fetched_at"] = recent.get("last_update")
    except Exception as e:
        out["error"] = "recent: %s" % e
        return out
    try:
        _time.sleep(1.0)  # pypistats 限流：两次请求间隔 ≥1s
        overview = _fetch(API_OVERVIEW.format(name=name))
        out["overview"] = overview.get("data", {})
    except Exception as e:
        out["error"] = (out["error"] or "") + " | overall: %s" % e
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取 PyPI 下载统计（作者侧观测，非用户行为）")
    ap.add_argument("--name", default=DEFAULT_PKG)
    ap.add_argument("--out", default=None, help="可选：写出 JSON 到文件")
    args = ap.parse_args()

    stats = fetch_stats(args.name)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print("[stats] 已写出 %s" % args.out)

    r = stats.get("recent") or {}
    print("包: %s" % stats["package"])
    print("日期: %s" % (stats.get("fetched_at") or "?"))
    print("下载: last_day=%s last_week=%s last_month=%s"
          % (r.get("last_day", "?"), r.get("last_week", "?"),
             r.get("last_month", "?")))
    if stats.get("error"):
        print("警告: %s" % stats["error"], file=sys.stderr)
    return 1 if stats.get("error") and not r else 0


if __name__ == "__main__":
    sys.exit(main())