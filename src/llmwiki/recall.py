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

正确性修复（2026-08-24，扩充评估集 57 条回归把关）：
- tokenize 不再去重：去重曾使 tf 恒 ≤1、K1 饱和调节失效；query terms 与
  df 统计改为调用方自行去重。
- avgdl 按字段统计：原实现把 7 字段 token 总加总除以 N，却用它归一单字段
  的 dl，长短字段的归一化口径互相失真。

套件化改造（相对个人库 scripts/kb_recall.py）：
  - 移除 REPO_DEFAULT 依赖：wikilink 出链图的库根 = 索引文件所在目录
    （索引在库根生成，self.root 即库根），对 KbRetriever 调用方零新增参数。

P1 别名组（2026-08-24）：
- expand_aliases() 短语级双向扩展：文档字段 blob（init 时缓存）与查询串
  都过同一函数，组内变体互相追加 → 「系统架构」←→ `architecture` 可互命中。
- 别名组来源：defaults.DEFAULT_ALIAS_GROUPS + llmwiki.toml [aliases].groups（追加）。

R1 查询长度耦合（2026-08-24）：
- min_score 是**绝对**分数门槛，而 BM25 总分随查询词数近似线性增长 →
  固定阈值对短查询过松、对长查询放进大量弱命中。188 篇参考库实测：
  固定 0.15 下平均 120/188 篇过阈（阈值形同虚设）；库外主题查询
  （如「Excel 数据透视表怎么用」）也返回 60~125 篇假命中，
  「真无候选」判定（assistant 话术）永远不触发。
- 修复：新增**每词阈值** min_score_per_term（默认 1.0），生效门槛 =
  max(min_score, min_score_per_term × 查询词数)。实测真查询期望文档
  最弱 3.60 分/词、库外主题 top1 最高 2.08 分/词 → 默认 1.0 下 57 条
  评估集 0 损失，库外假命中降到 ≤8 篇；判别区间 [2.0, 3.0]，可用
  llmwiki.toml [recall].min_score_per_term 上调（设 0 关闭本门槛）。

R2 覆盖度阶跃平滑（2026-08-24）：
- 旧版 factor = 1.0 if coverage >= 0.34 else 0.7 是硬阶跃：cov 0.33→0.34
  分数跳变 ~43%。实测 55.5% 的 (query,doc) 打分对落在 0<cov<0.34 阶跃带内
  （高危区 [0.25,0.34) 1634 对）；评估集真实受害者：「系统架构」查询的
  期望文档 cov=0.33 被 ×0.7 压到门槛下，只能靠 via_link 补位救回（脆弱路径）。
- 修复：线性 ramp，锚点不变（cov=0 → 0.7 下限，cov≥0.34 → 1.0 满分），
  区间内平滑过渡。57 条评估集：期望文档转直接命中（link 补位不再必需），
  其余 56 条 0 退化；对库外查询的压制语义保留（低覆盖仍被压向 0.7）。
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from . import defaults
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

# 覆盖度平滑参数（R2）：cov=0 → COVERAGE_FLOOR，cov ≥ COVERAGE_FULL → 1.0，
# 区间内线性过渡（端点与旧硬阶跃一致，消除边界 ~43% 的分数跳变）
COVERAGE_FULL = 0.34
COVERAGE_FLOOR = 0.7

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
    注意：**保留重复 token**（词频是 BM25 的 tf 输入）；
    需要去重的调用方（如 query terms、df 统计）自行 set()/dict.fromkeys()。
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
    return tokens


# ---- 别名扩展（P1） --------------------------------------------------------
_ASCII_VARIANT = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _contains_variant(low_text: str, variant: str) -> bool:
    """变体命中检测：ASCII 变体用词边界（防 `e2e` 误命中 `abc2efoo`）；
    中文变体无词边界概念，用子串（`系统架构` 命中 `整体系统架构总览`）。"""
    if _ASCII_VARIANT.match(variant):
        return re.search(r"(?<![a-z0-9])" + re.escape(variant)
                         + r"(?![a-z0-9])", low_text) is not None
    return variant in low_text


def expand_aliases(text: str, groups: list) -> str:
    """短语级**双向**别名扩展：text（原文即可，内部自 lower）含组内任一
    变体 → 把其余变体**追加**到文末（不改写原文，原有 token 全保留）。

    文档侧与查询侧都过本函数 → 双向可命中：
      查「系统架构」←→ 标题只写 `architecture` 的文档。
    """
    if not groups or not text:
        return text
    low = text.lower()
    extra: list[str] = []
    for group in groups:
        if len(group) < 2:
            continue
        hit = next((v for v in group if _contains_variant(low, v)), None)
        if hit:
            extra.extend(v for v in group if v != hit
                         and not _contains_variant(low, v))
    return text + " " + " ".join(extra) if extra else text


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
                 exclude_dirs: Optional[set] = None,
                 alias_groups: Optional[list] = None,
                 min_score_per_term: Optional[float] = None):
        with open(index_path, "r", encoding="utf-8") as f:
            self.index = json.load(f)
        self.root = os.path.dirname(os.path.abspath(index_path))
        self.docs = self.index["documents"]
        self.cat_index = self.index.get("category_index", {})
        self.tag_index = self.index.get("tag_index", {})
        # path -> doc 快速查表
        self._by_path = {d["path"]: d for d in self.docs}
        # P1：别名组（短语级双向扩展，文档侧与查询侧共用）
        self.alias_groups = [list(g) for g in (alias_groups or [])]
        # R1：每词阈值（查询长度感知的相关性门槛）。None → 套件默认。
        # 设 0 可关闭（退回纯绝对 min_score 门槛）。
        self.min_score_per_term = (
            defaults.DEFAULT_MIN_SCORE_PER_TERM
            if min_score_per_term is None else float(min_score_per_term))
        # 每文档每字段的（别名扩展后）文本 blob，统计与打分共用，
        # 同时避免 _score_doc 对同一 blob 反复拼串/扩展。
        self._blobs = {
            d["path"]: {
                f: expand_aliases(" ".join(_as_list(d.get(f, ""))),
                                  self.alias_groups)
                for f in FIELD_BOOST
            }
            for d in self.docs
        }
        # P0-1：BM25 统计（df / N / avgdl）预计算一次
        self._build_bm25_stats()
        # P0-2：wikilink 出链图（索引过期/解析异常时退化为空图，不影响主流程）
        self._link_graph = self._build_link_graph(exclude_dirs)

    # ---- BM25 统计 --------------------------------------------------------
    def _build_bm25_stats(self) -> None:
        """df 按文档级统计（term 出现在任一字段即计入该文档）；
        avgdl **按字段**统计（_bm25 归一的是单字段 dl，口径必须一致）。
        统计口径与打分一致：都基于别名扩展后的字段 blob。
        """
        df: dict[str, int] = defaultdict(int)
        field_len: dict[str, int] = defaultdict(int)
        for d in self.docs:
            seen: set[str] = set()
            for f in FIELD_BOOST:
                toks = tokenize(self._blobs[d["path"]][f])
                field_len[f] += len(toks)
                for t in set(toks):
                    if t not in seen:
                        df[t] += 1
                        seen.add(t)
        n = len(self.docs)
        self._df = df
        self._N = n
        # 每字段平均长度；空字段兜底 1.0 避免 dl/avgdl 除零
        self._avgdl = {f: (field_len[f] / n if n else 0.0) or 1.0
                       for f in FIELD_BOOST}

    def _bm25(self, text: str, term: str, field: str = "body_text") -> float:
        toks = tokenize(text)
        tf = toks.count(term)
        if tf == 0:
            return 0.0
        dl = len(toks)
        avgdl = self._avgdl.get(field) or 1.0
        idf = math.log((self._N - self._df.get(term, 0) + 0.5)
                       / (self._df.get(term, 0) + 0.5) + 1)
        return idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * dl / avgdl))

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
        blobs = self._blobs[doc["path"]]  # 已做别名扩展的字段 blob（缓存）
        for f, boost in FIELD_BOOST.items():
            blob = blobs[f]
            for term in terms:
                s = self._bm25(blob, term, f) * boost
                score += s
                # 记录命中的章节（仅 headings 字段用于章节级检索）
                if f == "headings" and s > 0:
                    for h in doc.get("headings", []):
                        if term in h.lower():
                            matched_headings.add(h)
        # R2 覆盖度平滑 ramp（替代旧硬阶跃 1.0 if cov>=0.34 else 0.7）：
        # cov=0 → 0.7（保留低覆盖压制，不砍到 0.5），cov≥0.34 → 1.0（满分），
        # 区间内线性过渡——边界处不再出现 ~43% 的分数跳变与排名翻转。
        matched = sum(1 for t in terms
                      if any(t in blobs[f].lower() for f in FIELD_BOOST))
        coverage = matched / len(terms) if terms else 0.0
        factor = COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * min(
            coverage / COVERAGE_FULL, 1.0)
        return score * factor, list(matched_headings)

    # ---- 对外召回接口 -----------------------------------------------------
    def recall(self, query: str, top_k: int = 5,
               categories: Optional[Iterable[str]] = None,
               tags: Optional[Iterable[str]] = None,
               min_score: float = 0.15,
               min_score_per_term: Optional[float] = None) -> list[RecallHit]:
        """BM25 召回 + Wikilink 图扩展。

        min_score 默认 0.15（绝对门槛，按 BM25 量纲重定；过高会静默滤掉真实命中）。
        min_score_per_term：R1 每词门槛（None → 用构造时的默认值），生效门槛 =
        max(min_score, min_score_per_term × 查询词数)。BM25 总分随词数线性增长，
        绝对门槛对长查询失效；每词门槛保证「平均每个查询词至少贡献这么多分」，
        弱命中（只擦到 1~2 个常见词的文档）被挡在门外。设 0 可关闭。
        """
        # 查询侧同样做别名扩展（与文档侧对称）；query terms 去重（保序）
        terms = list(dict.fromkeys(tokenize(expand_aliases(query, self.alias_groups))))
        if not terms:
            return []
        # R1：查询长度感知门槛（两道门叠加，任一可独立关闭）
        per_term = (self.min_score_per_term
                    if min_score_per_term is None else min_score_per_term)
        effective_min = max(min_score, per_term * len(terms))
        cand_docs = self._candidates(categories, tags)
        cand_paths = {d["path"] for d in cand_docs}
        direct: list[RecallHit] = []
        for doc in cand_docs:
            score, mh = self._score_doc(doc, terms)
            if score >= effective_min:
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
