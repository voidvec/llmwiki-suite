#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_recall_baseline.py — 召回基线独立回归脚本（不依赖 pytest）。

用途：对指定知识库跑一次 eval，断言汇总指标不低于历史基线；
      供 CI、pre-commit 或手工回归调用，不引入 pytest 依赖。

基线（与 tests/test_recall_baseline.py 一致，来源 docs/RELEASE.md §4）：
    testkb：recall@4 = 100%，MRR@4 = 1.0（P6 实测仍为 1.0）
    通用回调：recall >= 0.95 / MRR >= 0.90（防 flaky 下限）

退出码：
    0  全部通过
    1  指标跌破基线（回归）
    2  运行出错（参数/配置/未建索引等）

用法：
    python scripts/check_recall_baseline.py                    # 默认对 cwd 知识库断言
    python scripts/check_recall_baseline.py --repo <kb> --build # 未建索引时自动 ingest+index
    python scripts/check_recall_baseline.py --recall 1.0 --mrr 1.0   # 覆盖阈值
    python scripts/check_recall_baseline.py --json <snapshot.json>   # 直接断言既有快照
    python scripts/check_recall_baseline.py --out-dir /tmp/eval-out  # 输出到临时目录
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 优先使用已安装的 llmwiki 包（pip install . 后）；本地未安装时回退仓库内 src
try:
    import llmwiki  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))


def die(msg: str, code: int = 2) -> int:
    print(f"[check-recall] {msg}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check-recall-baseline",
        description="召回基线回归：跑 eval 并断言 recall/MRR 不低于阈值")
    ap.add_argument("--repo", default=None,
                    help="知识库根目录（默认解析当前目录；套件默认 testkb）")
    ap.add_argument("--queries", default=None, help="eval_queries.json 路径（默认用 repo 内置）")
    ap.add_argument("--recall", type=float, default=0.95,
                    help="contextual_recall 阈值（默认 0.95）")
    ap.add_argument("--mrr", type=float, default=0.90, help="MRR 阈值（默认 0.90）")
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--min-score", type=float, default=0.15)
    ap.add_argument("--out-dir", default=None,
                    help="eval 报告输出目录（默认 <repo>/eval_reports）")
    ap.add_argument("--tag", default=None, help="eval 报告标签（默认 baseline-YYYY-MM-DD）")
    ap.add_argument("--json", default=None, dest="json_path",
                    help="直接读取既有 JSON 快照断言（跳过重跑 eval）")
    ap.add_argument("--build", action="store_true",
                    help="若库未建索引（缺 kb-index.json），先运行 ingest+index 再评估")
    args = ap.parse_args(argv)

    from llmwiki.config import load_config, resolve_repo  # noqa: E402

    if args.json_path:
        json_path = args.json_path
        if not os.path.isfile(json_path):
            return die(f"JSON 快照不存在: {json_path}")
    else:
        repo = args.repo or os.getcwd()
        try:
            cfg = load_config(resolve_repo(repo))
        except Exception as exc:  # repo 未初始化等
            return die(f"加载知识库失败（{exc}）")
        from llmwiki.eval_recall import run_eval_cmd  # noqa: E402

        # 未建索引时按 --build 先建：ingest --apply（含重建索引）
        if not os.path.isfile(cfg.index_path):
            if not args.build:
                return die(
                    f"知识库尚未建索引（缺 {cfg.index_path}）。"
                    f"请先 llmwiki ingest --repo {repo} --apply，或加 --build 自动构建")
            print("[check-recall] 缺索引，自动 ingest --apply 构建…", file=sys.stderr)
            from llmwiki.ingest import run_ingest  # noqa: E402
            run_ingest(cfg, apply=True)
            cfg = load_config(resolve_repo(repo))  # 重建后的配置（含新索引路径等）

        out_dir = args.out_dir
        tag = args.tag
        # 默认输出到临时目录，避免污染知识库 eval_reports
        if out_dir is None:
            import tempfile
            out_dir = tempfile.mkdtemp(prefix="recall-baseline-")
        run_eval_cmd(cfg, queries_path=args.queries, top_k=args.top_k,
                     min_score=args.min_score, out_dir=out_dir, tag=tag or "baseline-check")
        json_path = os.path.join(out_dir, f"recall-eval-{tag or 'baseline-check'}.json")

    with open(json_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    s = snapshot["summary"]
    got_recall = s["contextual_recall"]
    got_mrr = s["mrr"]
    missed = s.get("missed_queries", [])
    top_k = snapshot.get("meta", {}).get("top_k", s.get("top_k", "?"))
    print(f"[check-recall] count={s['count']} recall@{top_k}={got_recall} "
          f"MRR={got_mrr} 阈值 recall>={args.recall} MRR>={args.mrr}")
    ok = True
    if got_recall < args.recall:
        print(f"[check-recall] ✗ recall={got_recall} < {args.recall}", file=sys.stderr)
        ok = False
    if got_mrr < args.mrr:
        print(f"[check-recall] ✗ MRR={got_mrr} < {args.mrr}", file=sys.stderr)
        ok = False
    if missed:
        print(f"[check-recall] 未命中 query: {missed}", file=sys.stderr)
    if not ok:
        return die(f"基线未达标（snapshot: {json_path}）", code=1)
    print("[check-recall] ✔ 基线通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())