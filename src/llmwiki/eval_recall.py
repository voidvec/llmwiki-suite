# -*- coding: utf-8 -*-
"""
eval_recall.py — 召回评估（recall@K / MRR）

对评估集中每条 query 跑 `recall(query, top_k=K)`（K 与生产 build_context 的
max_chapters=6 统一），计算：

- contextual_recall@K   ：任一期望文档出现在 Top-K 即算该条命中，aggregate = 命中数/总数
- contextual_precision@K：期望文档的排名位置（1-based；未命中记 0）
- MRR@K                 ：命中条的平均倒数排名

输出：控制台汇总 + Markdown 报告 + JSON 快照。

套件化改造（相对个人库 scripts/_eval_recall.py）：
  - 评估集默认用包内置 data/eval_queries.json（通用示例集）；
    用户库可放自己的 eval_queries.json，--queries 指定。
  - 报告默认写到 <repo>/eval_reports/（套件默认排除该目录，快照不进召回索引）。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from datetime import date

from .config import resolve_repo, load_config
from .recall import KbRetriever

# 包内置数据目录（eval_queries.json 等）
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_BUILTIN_QUERIES = os.path.join(_DATA_DIR, "eval_queries.json")


def load_queries(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_eval(retriever: KbRetriever, queries: dict, top_k: int,
             min_score: float) -> list[dict]:
    """对每条 query 跑 recall，返回逐条结果（含 rank / top hits）。"""
    out = []
    for q in queries["queries"]:
        query = q["query"]
        expected = set(q["expected"])
        hits = retriever.recall(query, top_k=top_k, min_score=min_score)
        top_paths = [h.path for h in hits]
        # 期望文档在 Top-K 中的位置（1-based），未命中为 None
        rank = None
        for i, p in enumerate(top_paths, start=1):
            if p in expected:
                rank = i
                break
        out.append({
            "query": query,
            "expected": q["expected"],
            "note": q.get("note", ""),
            "hit": rank is not None,
            "rank": rank,
            "top": [
                {"path": h.path, "score": round(h.score, 3),
                 "via_link": h.via_link,
                 "headings": h.matched_headings[:2]}
                for h in hits
            ],
        })
    return out


def summarize(results: list[dict], prod_top_k: int = 4) -> dict:
    n = len(results)
    hits = [r for r in results if r["hit"]]
    hits_in_prod = [r for r in results if r["hit"] and r["rank"] <= prod_top_k]
    mrr = sum(1.0 / r["rank"] for r in hits) / n if n else 0.0
    avg_rank_hit = (sum(r["rank"] for r in hits) / len(hits)) if hits else 0.0
    return {
        "count": n,
        "hit_count": len(hits),
        "contextual_recall": round(len(hits) / n, 4) if n else 0.0,
        "prod_top_k": prod_top_k,
        "contextual_recall_prod": round(len(hits_in_prod) / n, 4) if n else 0.0,
        "mrr": round(mrr, 4),
        "avg_rank_of_hits": round(avg_rank_hit, 2),
        "missed_queries": [r["query"] for r in results if not r["hit"]],
    }


def render_markdown(meta: dict, summary: dict, results: list[dict],
                    top_k: int) -> str:
    lines: list[str] = []
    lines.append("# 召回评估报告")
    lines.append("")
    lines.append(f"- 生成时间：{meta['generated_at']}")
    lines.append(f"- 检索器：`{meta['retriever']}`"
                 f"（min_score={meta['min_score']}, "
                 f"min_score_per_term={meta.get('min_score_per_term', '-')}）")
    lines.append(f"- 评估集：`{meta['queries_path']}`（{summary['count']} 条）")
    fr = meta.get("index_freshness")
    if fr:
        if fr.get("unknown"):
            lines.append("- 索引状态：旧版索引（无过期指纹），建议重建")
        elif fr["stale"]:
            lines.append(f"- ⚠ 索引过期：{fr['changed']} 改 / {fr['added']} 增 / "
                         f"{fr['deleted']} 删（本次指标基于过期索引）")
        else:
            lines.append("- 索引状态：与磁盘一致（P3 指纹比对通过）")
    lines.append(f"- 召回 K = {top_k}（与生产 `build_context(max_chapters=4)` 同 K）")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| contextual_recall@{top_k} | {summary['hit_count']} / "
                 f"{summary['count']} = {summary['contextual_recall'] * 100:.1f}% |")
    prod = summary['prod_top_k']
    lines.append(f"| 当前生产等价 recall@{prod}（max_chapters={prod} 截断） | "
                 f"{summary['contextual_recall_prod'] * 100:.1f}% |")
    lines.append(f"| MRR@{top_k} | {summary['mrr']} |")
    lines.append(f"| 平均期望文档排名（仅命中条） | {summary['avg_rank_of_hits']} |")
    lines.append(f"| 未命中 query 数 | {len(summary['missed_queries'])} |")
    lines.append("")
    lines.append("## 逐条结果")
    lines.append("")
    lines.append("| # | query | 命中 | rank | Top-1 命中路径 |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(results, start=1):
        top1 = r["top"][0]["path"] if r["top"] else "（无命中）"
        mark = "✅" if r["hit"] else "❌"
        rank = str(r["rank"]) if r["rank"] else "-"
        lines.append(f"| {i} | {r['query']} | {mark} | {rank} | `{top1}` |")
    lines.append("")
    if summary["missed_queries"]:
        lines.append("## 未命中明细")
        lines.append("")
        for r in results:
            if r["hit"]:
                continue
            lines.append(f"### ❌ {r['query']}")
            lines.append("")
            lines.append(f"- 期望：`{'`、`'.join(r['expected'])}`")
            lines.append(f"- 备注：{r['note'] or '-'}")
            lines.append("- Top-6 实际召回：")
            for h in r["top"]:
                lines.append(f"  - `{h['path']}`  (score={h['score']})")
            lines.append("")
    lines.append("---")
    lines.append("> 由 `llmwiki eval` 自动生成。"
                 "不同检索器/参数用同命令对比：`--min-score <值> --tag <标签>`。")
    return "\n".join(lines)


def run_eval_cmd(cfg, queries_path=None, top_k=None, min_score=0.15,
                 out_dir=None, tag=None, retriever_desc=None, prod_top_k=4):
    repo = str(cfg.repo)
    queries_path = queries_path or os.path.join(repo, "eval_queries.json")
    if not os.path.isfile(queries_path):
        queries_path = _BUILTIN_QUERIES
    tag = tag or f"baseline-{date.today().isoformat()}"
    retriever_desc = retriever_desc or "llmwiki.recall.KbRetriever (BM25 + body_text + wikilink graph)"

    queries = load_queries(queries_path)
    top_k = top_k or int(queries.get("top_k", 4))
    retriever = KbRetriever(cfg.index_path, exclude_dirs=cfg.exclude_dirs,
                            alias_groups=cfg.alias_groups,
                            min_score_per_term=cfg.min_score_per_term,
                            link_gate=cfg.link_gate)
    # P3：对过期索引做评估会得出错误结论，先告警并把状态记入 meta
    fr = retriever.freshness
    if fr is not None and fr.unknown:
        print("[eval] ⚠ 索引由旧版生成（无过期指纹），建议先运行 llmwiki index 重建",
              file=sys.stderr)

    results = run_eval(retriever, queries, top_k, min_score)
    summary = summarize(results, prod_top_k)
    meta = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "index_path": os.path.relpath(cfg.index_path, repo),
        "queries_path": queries_path,
        "top_k": top_k,
        "min_score": min_score,
        "min_score_per_term": cfg.min_score_per_term,
        "link_gate": cfg.link_gate,
        "retriever": retriever_desc,
        "index_freshness": (
            None if fr is None else
            {"stale": fr.stale, "unknown": fr.unknown,
             "changed": len(fr.changed), "added": len(fr.added),
             "deleted": len(fr.deleted)}),
    }
    if fr is not None and fr.stale:
        print("[eval] ⚠ %s；本次指标基于过期索引，建议 llmwiki index 重建后复测"
              % fr.summary(), file=sys.stderr)

    # 控制台汇总
    print(f"[eval] {summary['count']} queries, "
          f"recall@{top_k} = {summary['contextual_recall'] * 100:.1f}% "
          f"({summary['hit_count']}/{summary['count']}), "
          f"prod-equiv recall@{summary['prod_top_k']} = "
          f"{summary['contextual_recall_prod'] * 100:.1f}%, "
          f"MRR@{top_k} = {summary['mrr']}")
    for i, r in enumerate(results, start=1):
        mark = "+" if r["hit"] else "-"
        rank = r["rank"] if r["rank"] else "-"
        top1 = r["top"][0]["path"] if r["top"] else "EMPTY"
        print(f"  [{mark}{rank}] {i}. {r['query']}  ->  {top1}")

    # 落盘报告 + JSON 快照
    out_dir = out_dir or os.path.join(repo, "eval_reports")
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, f"recall-eval-{tag}.md")
    json_path = os.path.join(out_dir, f"recall-eval-{tag}.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(meta, summary, results, top_k))
    snapshot = {"meta": meta, "summary": summary, "per_query": results}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"[eval] report   -> {md_path}")
    print(f"[eval] snapshot -> {json_path}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="llmwiki eval", description="召回质量评估")
    ap.add_argument("--repo", default=None, help="知识库根目录（默认: 当前目录解析）")
    ap.add_argument("--queries", default=None,
                    help="评估集路径（默认: <repo>/eval_queries.json，回退包内置示例集）")
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--min-score", type=float, default=0.15)
    ap.add_argument("--min-score-per-term", type=float, default=None,
                    help="R1 每词阈值（默认: 套件/llmwiki.toml 配置值）")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--retriever-desc", default=None)
    ap.add_argument("--prod-top-k", type=int, default=4)
    args = ap.parse_args(argv)

    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    if args.min_score_per_term is not None:
        cfg.min_score_per_term = args.min_score_per_term
    run_eval_cmd(cfg, queries_path=args.queries, top_k=args.top_k,
                 min_score=args.min_score, out_dir=args.out_dir, tag=args.tag,
                 retriever_desc=args.retriever_desc, prod_top_k=args.prod_top_k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
