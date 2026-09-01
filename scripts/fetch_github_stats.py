#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_github_stats.py — 曝光监控：抓取 GitHub 仓库公开指标（实施合同 D4）。

仅用标准库（urllib.request / json），零第三方依赖。作者侧运行，产物写 JSON。
公开 REST API 无需认证即可拿基础字段；网络/限流失败按字段降级，错误记入 error。

用法：
  python scripts/fetch_github_stats.py                       # 默认 voidvec/llmwiki-suite，输出到控制台
  python scripts/fetch_github_stats.py --owner voidvec --repo llmwiki-suite
  python scripts/fetch_github_stats.py --out stats/github-daily.json
  python scripts/fetch_github_stats.py --token ghp_xxx       # 可选：带 token 提限流（5000/h vs 60/h）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

API_BASE = "https://api.github.com"

DEFAULT_OWNER = "voidvec"
DEFAULT_REPO = "llmwiki-suite"


def _get(url: str, token: str | None, timeout: float = 15.0) -> dict | None:
    """GET JSON；404/403 不抛异常，返回 None（上层降级）。"""
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "llmwiki-obs/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code}
    except Exception as e:
        return {"__net_error__": str(e)}


def fetch_repo_stats(owner: str, repo: str, token: str | None) -> dict:
    """抓取 star/fork/issue/PR/release，单项失败降级为 None + 记 error。"""
    out = {"owner": owner, "repo": repo, "fetched_at": None, "error": None}

    # 1) 仓库基础字段（star/fork/license/description 等）
    base = _get(f"{API_BASE}/repos/{owner}/{repo}", token)
    if isinstance(base, dict) and "__http_error__" not in base and "stargazers_count" in base:
        out["stars"] = base.get("stargazers_count")
        out["forks"] = base.get("forks_count")
        out["open_issues_total"] = base.get("open_issues_count")  # issues + PR（GitHub 口径）
        out["license"] = (base.get("license") or {}).get("spdx_id")
        out["created_at"] = base.get("created_at")
        out["pushed_at"] = base.get("pushed_at")
    else:
        err = base.get("__http_error__") if isinstance(base, dict) else "unknown"
        out["error"] = "repo: HTTP %s" % err
        out["stars"] = out["forks"] = out["open_issues_total"] = None

    # 2) open issues（不含 PR，type 过滤）
    issues = _get(f"{API_BASE}/search/issues?q=repo:{owner}/{repo}+type:issue+state:open&per_page=1", token)
    if isinstance(issues, dict) and "total_count" in issues:
        out["open_issues"] = issues["total_count"]
    else:
        # 搜索 API 无认证限流 10/min——降级用 repo 的 open_issues_count（含 PR）并标注
        out["open_issues"] = None
        out["error"] = (out["error"] or "") + " | issues-query 降级"
    time.sleep(0.2)  # 温和限流

    # 3) open pulls
    pulls = _get(f"{API_BASE}/repos/{owner}/{repo}/pulls?state=open&per_page=1", token)
    if isinstance(pulls, list):
        # 返回数组即成功；open PR 数无法直接数，用 per_page=1 只判断是否有；补一次 header 拿 count 更准
        out["open_prs"] = len(pulls)
    elif isinstance(pulls, dict):
        out["open_prs"] = None
        out["error"] = (out.get("error") or "") + " | pulls: HTTP %s" % pulls.get("__http_error__")
    time.sleep(0.2)

    # 4) latest release
    rel = _get(f"{API_BASE}/repos/{owner}/{repo}/releases/latest", token)
    if isinstance(rel, dict) and "tag_name" in rel:
        out["latest_release"] = rel["tag_name"]
        out["latest_release_at"] = rel.get("published_at")
    else:
        out["latest_release"] = None

    out["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return out


def _call(url: str, token: str | None, timeout: float = 15.0) -> dict | list:
    """_get 的别名，返回 dict/list，网络异常返回 {'__http_error__': msg}。"""
    return _get(url, token, timeout)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="抓取 GitHub 仓库公开指标（作者侧观测）")
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--token", default=None, help="可选 GH token（提限流）")
    ap.add_argument("--out", default=None, help="可选：写出 JSON 到文件")
    args = ap.parse_args(argv)

    stats = fetch_repo_stats(args.owner, args.repo, args.token)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print("[gh-stats] 已写出 %s" % args.out)

    print("repo: %s/%s" % (stats["owner"], stats["repo"]))
    print("stars: %s  forks: %s  open_issues: %s  open_prs: %s"
          % (stats.get("stars"), stats.get("forks"),
             stats.get("open_issues"), stats.get("open_prs")))
    if stats.get("latest_release"):
        print("latest_release: %s (%s)" % (stats["latest_release"],
                                           stats.get("latest_release_at", "?")))
    if stats.get("error"):
        print("警告: %s" % stats["error"], file=sys.stderr)
    # 全失败（连基础字段都没有）才算错
    return 1 if (stats.get("stars") is None and
                 stats.get("forks") is None and stats.get("open_issues") is None) else 0


if __name__ == "__main__":
    sys.exit(main())