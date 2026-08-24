# -*- coding: utf-8 -*-
"""
recall.py — 知识库候选召回（BM25 + Wikilink 图扩展）

读取 `kb-index.json`（由 gen_index 生成），在 RAG 检索流程中先用轻量元数据筛选
候选文档，再按需读取全文 / 章节送进大模型生成。无需一次性载入全库。

P0 方案落地（docs/llmwiki-tutorial-03-quality-tuning.md）：
- P0-1：BM25 替换旧 2-gram 子串求和（K1=1.5, B=0.75, FIELD_BOOST，idf 自动压低
  高频词、抬高判别词 → 修复排序反转）；停用字用「单字集 + 含任一即弃」。
- P0-2：Wikilink 图扩展——命中文档的出链文档以封顶 LINK_BOOST 补位，
  只补位不顶替，`RecallHit.via_link` 标记便于调试与评估。
- P0-3：正文索引 `body_text`（仅剥代码块、保留 inline code）参与 BM25。
- min_score 默认 0.15（按 BM25 量纲重定）。

套件化改造（相对个人库 scripts/kb_recall.py）：
  - 移除 REPO_DEFAULT 依赖：wikilink 出链图的库根 = 索引文件所在目录
    （索引在库根生成，self.root 即库根），对 KbRetriever 调用方零新增参数。
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .kb_core import WIKILINK_RE, build_link_index, resolve_wikilink

# BM25 字段 boost（P0-1）：标题最高，标签/章节次之，正文与描述/摘要同权
FIELD_BOOST = {
    "title": 3.0,
    "tags": 2.0,
    "headings": 1.5,
    "body_text": 1.0,
    "description": 1.0,
    "summary": 1.0,
    "categories": 0.8,
}

# BM25 参数（P0-1：K1=1.5, B=0.75，经典默认）
K1, B = 1.5, 0.75

_CJK = re.compile(r"[一-鿿]")

# 单字停用词表。2-gram 含任一停用字即丢弃（删得掉噪声 gram；「路由」不含停用字 → 保留）。
_CJK_STOP = set("与的了这那是在和对如何怎么一个可以我们你们做哪些")


def _as_list(v):
    """字段值归一为 list[str]。list 原样返回；str 包成 [str]；空值/None 返回 []。"""
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v:
        return [v]
    return []


def tokenize(text: str, cjk_stop: bool = True) -> list[str]:
    """中英文混合分词：英文按词；中文滑 2-gram；丢弃含停用字的 gram。

    BM25 检索与 df/avgdl 统计共用本函数，保证打分口径一致。
    """
    text = (text or "").lower()
    tokens: list[str] = []
    for chunk in re.findall(r"[一-鿿]+|[a-zA-Z0-9_]+", text):
        if _CJK.match(chunk):
            if len(chunk) == 1:
                grams = [chunk]
            else:
                grams = [chunk[i:i + 2] for i in range(len(chunk) - 1)]
            if cjk_stop:
                grams = [g for g in grams
                         if not any(c in _CJK_STOP for c in g)]
            tokens.extend(grams)
        else:
            tokens.append(chunk)
    # 去重但保留顺序
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


@dataclass
class RecallHit:
    path: str
    title: str
    score: float
    matched_headings: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    via_link: bool = False  # True = 由 wikilink 图扩展补位（P0-2）


class KbRetriever:
    def __init__(self, index_path: str | os.PathLike,
                 exclude_dirs: Optional[set] = None):
        with open(index_path, "r", encoding="utf-8") as f:
            self.index = json.load(f)
        self.root = os.path.dirname(os.path.abspath(index_path))
        self.docs = self.index["documents"]
        self.cat_index = self.index.get("category_index", {})
        self.tag_index = self.index.get("tag_index", {})
        # path -> doc 快速查表
        self._by_path = {d["path"]: d for d in self.docs}
        # P0-1：BM25 统计（df / N / avgdl）预计算一次
        self._build_bm25_stats()
        # P0-2：wikilink 出链图（索引过期/解析异常时退化为空图，不影响主流程）
        self._link_graph = self._build_link_graph(exclude_dirs)

    # ---- BM25 统计 --------------------------------------------------------
    def _build_bm25_stats(self) -> None:
        df: dict[str, int] = defaultdict(int)
        total = 0
        for d in self.docs:
            seen: set[str] = set()
            for f in FIELD_BOOST:
                toks = tokenize(" ".join(_as_list(d.get(f, ""))))
                total += len(toks)
                for t in set(toks):
                    if t not in seen:
                        df[t] += 1
                        seen.add(t)
        self._df = df
        self._N = len(self.docs)
        self._avgdl = (total / len(self.docs)) if self.docs else 0.0

    def _bm25(self, text: str, term: str) -> float:
        toks = tokenize(text)
        tf = toks.count(term)
        if tf == 0:
            return 0.0
        dl = len(toks)
        idf = math.log((self._N - self._df.get(term, 0) + 0.5)
                       / (self._df.get(term, 0) + 0.5) + 1)
        return idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * dl / self._avgdl))

    # ---- Wikilink 出链图（P0-2） -------------------------------------------
    def _build_link_graph(self, exclude_dirs: Optional[set]) -> dict[str, set[str]]:
        """自建出链图 {rel: set(out_rel)}。

        用 `body_text_clean`（再剥 inline code，避免 C++ `[[T]]` / bash `[[ =~ ]]`
        误报）扫 `[[wikilink]]`，经 `build_link_index(self.root)` +
        `resolve_wikilink(target, rel, ix)` 解析到真实文档 rel；
        仅收录解析成功且在本索引内的文档（目录目标/解析失败忽略）。
        """
        try:
            ix = build_link_index(self.root, exclude_dirs or set())
        except Exception:
            return {}
        graph: dict[str, set[str]] = {}
        for d in self.docs:
            rel = d["path"]
            body = d.get("body_text_clean") or ""
            outs: set[str] = set()
            for m in WIKILINK_RE.finditer(body):
                status, resolved = resolve_wikilink(m.group(1), rel, ix)
                if status == "ok" and resolved in self._by_path:
                    outs.add(resolved)
            graph[rel] = outs
        return graph

    # ---- 候选集过滤 -------------------------------------------------------
    def _candidates(self, categories: Optional[Iterable[str]],
                    tags: Optional[Iterable[str]]) -> list[dict]:
        """先用分类 / 标签倒排表缩小候选集（O(1) 查表），再逐篇打分。"""
        if categories:
            cands: set[str] = set()
            for c in categories:
                cands |= set(self.cat_index.get(c, []))
            paths = cands
        else:
            paths = set(self._by_path)

        if tags:
            tag_paths: set[str] = set()
            for t in tags:
                tag_paths |= set(self.tag_index.get(t, []))
            paths &= tag_paths
        return [self._by_path[p] for p in paths if p in self._by_path]

    # ---- 单篇打分（BM25 × 字段 boost × 覆盖度系数） --------------------------
    def _score_doc(self, doc: dict, terms: list[str]) -> tuple[float, list[str]]:
        matched_headings: set[str] = set()
        score = 0.0
        for f, boost in FIELD_BOOST.items():
            blob = " ".join(_as_list(doc.get(f, "")))
            for term in terms:
                s = self._bm25(blob, term) * boost
                score += s
                # 记录命中的章节（仅 headings 字段用于章节级检索）
                if f == "headings" and s > 0:
                    for h in doc.get("headings", []):
                        if term in h.lower():
                            matched_headings.add(h)
        # 门槛式覆盖度。coverage≥0.34 满分 1.0；否则下限 0.7
        matched = sum(1 for t in terms
                      if any(t in (" ".join(_as_list(doc.get(f, "")))).lower()
                             for f in FIELD_BOOST))
        coverage = matched / len(terms) if terms else 0.0
        factor = 1.0 if coverage >= 0.34 else 0.7
        return score * factor, list(matched_headings)

    # ---- 对外召回接口 -----------------------------------------------------
    def recall(self, query: str, top_k: int = 5,
               categories: Optional[Iterable[str]] = None,
               tags: Optional[Iterable[str]] = None,
               min_score: float = 0.15) -> list[RecallHit]:
        """BM25 召回 + Wikilink 图扩展。

        min_score 默认 0.15（按 BM25 量纲重定；过高会静默滤掉真实命中）。
        """
        terms = tokenize(query)
        if not terms:
            return []
        cand_docs = self._candidates(categories, tags)
        cand_paths = {d["path"] for d in cand_docs}
        direct: list[RecallHit] = []
        for doc in cand_docs:
            score, mh = self._score_doc(doc, terms)
            if score >= min_score:
                direct.append(RecallHit(
                    path=doc["path"],
                    title=doc.get("title", doc.get("basename", "")),
                    score=score,
                    matched_headings=mh,
                    categories=doc.get("categories", []),
                    tags=doc.get("tags", []),
                    summary=doc.get("summary", ""),
                ))
        direct.sort(key=lambda h: h.score, reverse=True)

        # P0-2：link 图扩展，只补位不顶替，且遵守候选过滤（categories/tags）。
        # LINK_BOOST 封顶 = min(直接命中分) × 0.5，任何 link 文档都不可能
        # 压过最弱的直接命中；扩展文档取 max(自身 BM25 分, link_boost)。
        if direct and self._link_graph:
            direct_paths = {h.path for h in direct}
            link_boost = min(h.score for h in direct) * 0.5
            extended: dict[str, float] = {}
            for h in direct:
                for out_rel in self._link_graph.get(h.path, ()):
                    if (out_rel not in direct_paths and out_rel in cand_paths
                            and out_rel not in extended):
                        extended[out_rel] = link_boost
            for rel, lb in extended.items():
                doc = self._by_path[rel]
                own_score, _ = self._score_doc(doc, terms)
                direct.append(RecallHit(
                    path=rel,
                    title=doc.get("title", doc.get("basename", "")),
                    score=max(own_score, lb),
                    matched_headings=[],
                    categories=doc.get("categories", []),
                    tags=doc.get("tags", []),
                    summary=doc.get("summary", ""),
                    via_link=True,
                ))
            direct.sort(key=lambda h: h.score, reverse=True)

        return direct[:top_k]

    # ---- 取数：读全文 / 章节 ----------------------------------------------
    def read_doc(self, path: str) -> str:
        """按 path 读取源 .md 全文。"""
        full = os.path.join(self.root, path)
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    def fetch_chapter(self, path: str, heading: str) -> str:
        """章节级检索：只抽取 heading 标题下的那一段（到下一个同级/更高级标题为止）。"""
        text = self.read_doc(path)
        lines = text.splitlines()
        start = None
        for i, line in enumerate(lines):
            if re.match(r"^#{1,6}\s+" + re.escape(heading) + r"\s*$", line):
                start = i
                break
        if start is None:
            return ""
        level = len(lines[start]) - len(lines[start].lstrip("#"))
        out: list[str] = [lines[start]]
        for line in lines[start + 1:]:
            if re.match(r"^#{1,6}\s", line):
                cur = len(line) - len(line.lstrip("#"))
                if cur <= level:
                    break
            out.append(line)
        return "\n".join(out)
