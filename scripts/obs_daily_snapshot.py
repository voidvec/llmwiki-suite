#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""obs_daily_snapshot.py — 曝光监控每日快照（实施合同 D4 主入口）。

合并 PyPI 下载量 + GitHub 仓库指标，写一份 JSON 快照 + 追加一行 CSV 序列，
供周报自动汇总与长期趋势追溯。仅标准库，零第三方依赖。

用法：
  python scripts/obs_daily_snapshot.py                     # 默认写 stats/ 下今日快照
  python scripts/obs_daily_snapshot.py --out-dir stats     # 指定输出目录
  python scripts/obs_daily_snapshot.py --token ghp_xxx      # 可选 GH token

产物：
  stats/llmwiki-obs-YYYY-MM-DD.json   单日完整快照（pypi + github 合并）
  stats/daily-series.csv              时序序列（首次运行自动写表头）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# 复用同目录的抓取脚本（不强制要求 llmwiki 包）
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from fetch_github_stats import fetch_repo_stats  # noqa: E402
from fetch_pypi_stats import fetch_stats as fetch_pypi  # noqa: E402

DEFAULT_PKG = "llmwiki-suite"
DEFAULT_OWNER = "voidvec"
DEFAULT_REPO = "llmwiki-suite"
DEFAULT_OUT_DIR = "stats"


def _today() -> str:
    # 用本地日期（作者侧观测，按本地时间切片）
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def build_snapshot(pkg: str, owner: str, repo: str, token: str | None) -> dict:
    pypi = fetch_pypi(pkg)
    gh = fetch_repo_stats(owner, repo, token)

    pypi_recent = pypi.get("recent") or {}
    return {
        "date": _today(),
        "fetched_at": gh.get("fetched_at") or pypi.get("fetched_at"),
        "pypi": {
            "package": pkg,
            "last_day": pypi_recent.get("last_day"),
            "last_week": pypi_recent.get("last_week"),
            "last_month": pypi_recent.get("last_month"),
            "error": pypi.get("error"),
        },
        "github": {
            "stars": gh.get("stars"),
            "forks": gh.get("forks"),
            "open_issues": gh.get("open_issues"),
            "open_prs": gh.get("open_prs"),
            "latest_release": gh.get("latest_release"),
            "latest_release_at": gh.get("latest_release_at"),
            "error": gh.get("error"),
        },
    }


def append_csv(snapshot: dict, csv_path: str) -> None:
    """追加一行到 daily-series.csv；首跑写表头；同日重跑覆盖旧行（幂等）。"""
    d = os.path.dirname(csv_path)
    if d:
        os.makedirs(d, exist_ok=True)
    header = ["date", "pypi_total_downloads", "pypi_recent_downloads",
              "stars", "forks", "open_issues", "open_prs", "version"]
    pypi = snapshot.get("pypi") or {}
    gh = snapshot.get("github") or {}
    date = snapshot.get("date", "")
    # 读既有行：取旧行（表头 + 历史行）。同日旧行的非空字段用作本轮兜底（防上游失败冲掉好数据）
    rows = []
    if os.path.isfile(csv_path):
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    old_row = {}
    if rows and rows[0] and rows[0][0] == "date":
        header_row = rows.pop(0)  # 取出表头
        for r in rows:
            if r and r[0] == date:
                old_row = dict(zip(header_row, r))
                break
    else:
        header_row = header
    rows = [r for r in rows if not (r and r[0] == date)]  # 去掉同日旧行

    def _pick(new_val, key):
        """新值非空用新值，否则保留旧值（防上游失败把好数据冲空）。"""
        if new_val is not None and str(new_val) != "":
            return new_val
        return old_row.get(key, "")

    row = [
        date,
        _pick(pypi.get("last_month"), "pypi_total_downloads"),
        _pick(pypi.get("last_day"), "pypi_recent_downloads"),
        _pick(gh.get("stars"), "stars"),
        _pick(gh.get("forks"), "forks"),
        _pick(gh.get("open_issues"), "open_issues"),
        _pick(gh.get("open_prs"), "open_prs"),
        _pick(gh.get("latest_release"), "version"),
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header_row)
        for r in rows:
            w.writerow(r)
        w.writerow(row)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="每日曝光快照：PyPI + GitHub 合并落盘")
    ap.add_argument("--pkg", default=DEFAULT_PKG)
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--token", default=None)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args(argv)

    snap = build_snapshot(args.pkg, args.owner, args.repo, args.token)

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, f"llmwiki-obs-{snap['date']}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print("[obs] 快照 JSON: %s" % json_path)

    csv_path = os.path.join(args.out_dir, "daily-series.csv")
    append_csv(snap, csv_path)
    print("[obs] CSV 序列: %s" % csv_path)

    print("\n=== 今日快照 %s ===" % snap["date"])
    print("PyPI: last_day=%s last_week=%s last_month=%s"
          % (snap["pypi"].get("last_day"), snap["pypi"].get("last_week"),
             snap["pypi"].get("last_month")))
    print("GitHub: stars=%s forks=%s open_issues=%s open_prs=%s rel=%s"
          % (snap["github"].get("stars"), snap["github"].get("forks"),
             snap["github"].get("open_issues"), snap["github"].get("open_prs"),
             snap["github"].get("latest_release")))
    if snap["pypi"].get("error"):
        print("PyPI 警告: %s" % snap["pypi"]["error"], file=sys.stderr)
    if snap["github"].get("error"):
        print("GitHub 警告: %s" % snap["github"]["error"], file=sys.stderr)

    # 全失败才算错
    pypi_ok = snap["pypi"].get("last_day") is not None or snap["pypi"].get("last_month") is not None
    gh_ok = snap["github"].get("stars") is not None
    return 0 if (pypi_ok or gh_ok) else 1


if __name__ == "__main__":
    sys.exit(main())