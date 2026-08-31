# -*- coding: utf-8 -*-
"""health.py — 知识库健康分（0-100，零依赖、离线可跑）。

设计（对应实施契约 D1 / 9 周路线图）：
  - 3 规则 MVP（经验版 Beta，对外定性「健康度参考值」）：
      1. 文档完整性    meta  — frontmatter 必填字段完整率 + 正文非空
      2. 链接健壮性    link  — wikilink + 相对 md 链接解析成功率
      3. 元数据新鲜度  fresh — FRESH_WINDOW_DAYS 内有 updated/date 的文档占比
  - 0-100 加权：meta 0.40 / link 0.40 / fresh 0.20（和 = 1.0）。
  - 输出：JSON（机器可读）+ HTML（自包含可视化基础版，零依赖、无图表库）。
  - 只依赖标准库 + kb_core / config。

区别于 lint：
  - lint = 阻断式巡检（errors>0 → 退出码 1，供 pre-commit/CI 用）；
  - health = 趋势式健康度量（0-100 与分项，供人/CI 观察，不阻断）。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from .kb_core import (
    split_fm, strip_code,
    WIKILINK_RE, MD_LINK_RE,
    iter_md_files, build_link_index,
    resolve_wikilink, resolve_md_link, heading_exists,
    is_vendored,
)
from .config import Config, load_config

REQUIRED_FM = ["title", "description", "tags", "difficulty"]
FRESH_WINDOW_DAYS = 90
WEIGHTS = {"meta": 0.40, "link": 0.40, "fresh": 0.20}
_GRADES = [(90, "A", "优秀"), (75, "B", "良好"), (60, "C", "及格"), (0, "D", "待优化")]
MAX_ISSUES_PER_KIND = 50
MAX_ISSUES_SHOWN_HTML = 8
_RULE_LABELS = {"meta": "文档完整性", "link": "链接健壮性", "fresh": "元数据新鲜度"}
_GRADE_ZH = {"A": "优秀  90-100", "B": "良好  75-89", "C": "及格  60-74", "D": "待优化  <60", "F": "空库"}


def grade(score: float) -> str:
    for thr, letter, _ in _GRADES:
        if score >= thr:
            return letter
    return "F"


def _read_text(path) -> str:
    """读文件 utf-8；兼容 str 与 Path（iter_md_files 返回 str 路径）。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_date_from_fm(fm_text: str):
    """从 frontmatter 原文找 updated/date/modified 的 YYYY-MM-DD。找不到 None。"""
    if not fm_text:
        return None
    for key in ("updated", "date", "modified"):
        m = re.search(
            r"^\s*%s\s*:\s*[\"']?([0-9]{4}-[0-9]{2}-[0-9]{2})[\"']?\s*$" % key,
            fm_text, re.M)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                return None
    return None


def _ratio(ok: int, tot: int) -> float:
    return (ok / tot) if tot else 1.0


def compute(repo, cfg: Config | None = None, exclude_dirs=None) -> dict:
    """计算知识库健康分（全匿名本地计算）。

    repo         - 库根（Path/str）
    cfg          - Config（提供 exclude_dirs）；None 时自动 load_config
    exclude_dirs - 追加排除（仅 cfg=None 时生效）
    """
    root = Path(repo)
    if cfg is None:
        cfg = load_config(root)
        if exclude_dirs:
            extra = {str(d).strip("/") for d in exclude_dirs if str(d).strip("/")}
            cfg.exclude_dirs |= extra

    files = sorted(iter_md_files(root, cfg.exclude_dirs))  # [(rel, full), ...]
    total = len(files)
    if total == 0:
        return {
            "schema": "llmwiki.health.v1",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "repo": str(root),
            "score": 0,
            "grade": "F",
            "rules": {},
            "counts": {"files": 0, "links": 0},
            "issues": {"fm": [], "link": [], "fresh": []},
            "notes": {"overall": "空库（0 篇 markdown），请先 ingest 再评估健康度。", "rule_issues": []},
        }

    link_index = build_link_index(root, cfg.exclude_dirs)
    fm_issues, link_issues, fresh_issues = [], [], []
    n_fm = n_link = n_fresh = n_fresh_ok = 0
    vendored_skipped = 0

    for rel, full in files:
        if is_vendored(rel):
            vendored_skipped += 1  # repo 元数据文件不参与 FM/新鲜度统计
        text = _read_text(full)
        fm, body, raw_fm = split_fm(text)

        # --- 1. 文档完整性（frontmatter 必填 + 正文非空）---
        n_fm += 1
        missing = [f for f in REQUIRED_FM
                   if not (fm and fm.get(f) is not None and str(fm.get(f)).strip())]
        if missing:
            fm_issues.append((rel, "missing-fm:" + ",".join(missing)))
        if not strip_code(body or "").strip():
            fm_issues.append((rel, "empty-body"))

        # --- 2. 链接健壮性 ---
        safe_body = strip_code(body or "")
        for m in WIKILINK_RE.finditer(safe_body):
            n_link += 1
            target = m.group(1).split("|")[0].strip()
            ok, _ = resolve_wikilink(target, rel, link_index)
            if ok != "ok":
                link_issues.append((rel, target, "wikilink"))
        for m in MD_LINK_RE.finditer(safe_body):
            tgt = m.group(2).strip()
            if tgt.startswith(("#", "mailto:", "ftp://")):
                continue
            status, _res, anchor = resolve_md_link(tgt, rel, link_index, root)
            ok = status in ("ok", "external", "anchor_same")
            if ok and anchor:
                ok = heading_exists(rel, anchor, link_index)
            n_link += 1
            if not ok:
                link_issues.append((rel, tgt, "mdlink"))

        # --- 3. 元数据新鲜度 ---
        if not is_vendored(rel):
            n_fresh += 1
            updated = _parse_date_from_fm(raw_fm or "")
            today = datetime.now()
            if updated is None:
                fresh_issues.append((rel, "no-date"))
            elif (today - updated).days > FRESH_WINDOW_DAYS:
                fresh_issues.append((rel, "stale:%d" % (today - updated).days))
            else:
                n_fresh_ok += 1

    meta_ratio = _ratio(n_fm - len(set(i[0] for i in fm_issues)), n_fm)
    link_ratio = _ratio(n_link - len(link_issues), n_link)
    fresh_ratio = _ratio(n_fresh_ok, n_fresh)

    score = round(
        WEIGHTS["meta"] * meta_ratio * 100 +
        WEIGHTS["link"] * link_ratio * 100 +
        WEIGHTS["fresh"] * fresh_ratio * 100
    )
    if n_link < 5:
        score = max(0, score - 2)

    return {
        "schema": "llmwiki.health.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "score": score,
        "grade": grade(score),
        "rules": {
            "meta":  {"score": round(meta_ratio * 100, 1),  "weight": WEIGHTS["meta"]},
            "link":  {"score": round(link_ratio * 100, 1),  "weight": WEIGHTS["link"]},
            "fresh": {"score": round(fresh_ratio * 100, 1), "weight": WEIGHTS["fresh"]},
        },
        "counts": {"files": total, "links": n_link},
        "issues": {
            "fm":    [{"file": r, "detail": d} for r, d in fm_issues][:MAX_ISSUES_PER_KIND],
            "link":  [{"file": r, "detail": t, "type": k} for r, t, k in link_issues][:MAX_ISSUES_PER_KIND],
            "fresh": [{"file": r, "detail": d} for r, d in fresh_issues][:MAX_ISSUES_PER_KIND],
        },
        "notes": _notes(score, meta_ratio, link_ratio, fresh_ratio, total, n_link),
    }


def _notes(score: float, m: float, l: float, f: float, total: int, nlinks: int) -> dict:
    ls = []
    if m < 0.5:
        ls.append("meta: 超过半数文档缺 frontmatter 必填字段")
    elif m < 0.8:
        ls.append("meta: 部分文档缺 frontmatter 必填字段（title/description/tags/difficulty）")
    if l < 0.8 and nlinks > 0:
        ls.append("link: 断链比例偏高，建议运行 llmwiki lint 定位修复")
    if f < 0.5:
        ls.append("fresh: 大量文档无更新日期或已过期（建议补充 updated 字段）")
    if nlinks == 0:
        ls.append("link: 检测到 0 条内部链接（健康分已小幅下调）")
    overall = "知识库整体健康" if score >= 75 else ("需要关注" if score >= 60 else "亟待体检")
    return {"overall": overall, "rule_issues": ls}


# --------------------------------------------------------------------------
# HTML 渲染（零依赖、自包含）
# --------------------------------------------------------------------------
def _bar_color(sc: float) -> str:
    return "#34d399" if sc >= 80 else ("#fbbf24" if sc >= 60 else "#f87171")


_HTML_CSS = (
    "body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;"
    "max-width:820px;margin:32px auto;padding:0 20px;color:#e5e7eb;background:#18181b}"
    "h1{font-size:20px;margin-bottom:6px}.dim{color:#9ca3af;font-size:13px}"
    ".scorebox{display:flex;align-items:center;gap:24px;margin:20px 0;padding:20px;"
    "border:1px solid #333;border-radius:12px}"
    ".big{font-size:56px;font-weight:700;min-width:120px}"
    ".tag{display:inline-block;padding:2px 12px;border-radius:20px;font-size:13px;color:#111}"
    ".tag-a{background:#4ade80}.tag-b{background:#34d399}.tag-c{background:#fbbf24}"
    ".tag-d{background:#f87171}.tag-f{background:#9ca3af}"
    ".row{display:flex;align-items:center;gap:8px;margin:10px 0;font-size:13px}"
    ".lbl{width:64px;color:#9aa3af}.bar{flex:1;height:8px;background:#27272a;border-radius:4px}"
    ".fill{height:8px;border-radius:4px}.val{width:58px;text-align:right;color:#e5e7eb}"
    ".w{width:62px;color:#6b7280}"
    ".sec{margin-top:28px;font-size:15px;color:#c6c9ce;border-bottom:1px solid #2a2a2e;"
    "padding-bottom:6px}"
    ".summary{font-size:13px;color:#d4d4d8;line-height:1.9}"
    ".small{color:#6b7280;font-size:11.5px;margin-top:22px;line-height:1.6}"
    ".kpi{display:flex;gap:28px;margin:10px 0;color:#c6c9ce;font-size:13px}"
)

_HTML_TPL = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>llmwiki Health Report</title><style>{css}</style></head><body>
<h1>llmwiki 知识库健康报告</h1>
<div class="kpi"><span>生成时刻：{ts}</span><span>文档：{doc}</span><span>内部链接：{link}</span><span>待处理：{ni}</span></div>
<div class="scorebox">
  <div class="big">{score}</div>
  <div>
    <div><b>健康度得分（0-100）</b></div>
    <div style="margin-top:4px"><span class="tag tag-{gl}">{grade}</span></div>
    <div class="dim" style="margin-top:8px">{overall}</div>
  </div>
</div>
<div class="sec">规则明细（权重：meta 40% · link 40% · fresh 20%）</div>
<div style="margin-top:10px">{rows}</div>
<div class="sec">问题摘要（前 {maxn} 条/类，完整见 JSON）</div>
<div class="summary" style="margin-top:8px">{issues_html}</div>
<div class="small">llmwiki health v0.1（经验版 Beta）· 健康度参考值，非质量标准。零第三方依赖，离线生成。</div>
</body></html>"""


def render_html(report: dict) -> str:
    s = report["score"]
    g = report["grade"]
    rules = report.get("rules", {})
    counts = report.get("counts", {})
    notes = report.get("notes", {})
    issues = report.get("issues", {})
    n_issues = sum(len(v) for v in issues.values())

    rows = ""
    for key, label in _RULE_LABELS.items():
        r = rules.get(key)
        if not r:
            continue
        sc = r.get("score", 0)
        rows += (
            '<div class="row"><div class="lbl">{label}</div>'
            '<div class="bar"><div class="fill" style="width:{w}%;background:{c}"></div></div>'
            '<div class="val">{v} / 100</div><div class="w">权重 {wt}%</div></div>'
        ).format(label=label, w=round(sc), c=_bar_color(sc), v=round(sc),
                 wt=round(r.get("weight", 0) * 100))

    if n_issues == 0:
        issues_html = '<div class="small">无待处理问题 🎉</div>'
    else:
        lines = []
        for kind, label in (("fm", "元数据缺失"), ("link", "断链"), ("fresh", "新鲜度")):
            items = issues.get(kind, [])
            if not items:
                continue
            lines.append("<b>{label}（{n}）</b>".format(label=label, n=len(items)))
            for it in items[:MAX_ISSUES_SHOWN_HTML]:
                f = it.get("file", "")
                d = it.get("detail", it.get("type", ""))
                lines.append("&nbsp;&nbsp;- {f} → {d}".format(f=f, d=d))
        issues_html = "<br/>".join(lines)

    overall = notes.get("overall", "")
    zh = _GRADE_ZH.get(g, "空库")
    return _HTML_TPL.format(
        css=_HTML_CSS,
        ts=report.get("generated_at", ""),
        doc=counts.get("files", 0), link=counts.get("links", 0),
        ni=n_issues, score=s, gl=g.lower(),
        grade=g + " " + zh, overall=overall,
        rows=rows, maxn=MAX_ISSUES_SHOWN_HTML, issues_html=issues_html,
    )


# --------------------------------------------------------------------------
# CLI 入口
# --------------------------------------------------------------------------
def run_health(repo: str, out_dir: str | None = None, json_out: bool = True,
               html_out: bool = True) -> dict:
    """计算 + 落盘（默认 JSON+HTML 双写）。返回 report dict。"""
    report = compute(repo)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    if json_out and out_dir:
        (Path(out_dir) / "health-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if html_out and out_dir:
        (Path(out_dir) / "health-report.html").write_text(
            render_html(report), encoding="utf-8")
    return report