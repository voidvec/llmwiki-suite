# -*- coding: utf-8 -*-
"""
gen_index.py — 知识库索引生成器（LlmWiki Ingest 阶段）

扫描全库 Markdown，解析 frontmatter + 正文结构，生成：
  1. kb-index.json     — 供 recall.KbRetriever 消费的检索索引（documents + 倒排表）
  2. category-index.md — 按 categories 受控词表聚合的人工导航页

套件化改造（相对个人库 scripts/_gen_query_index.py）：
  - repo / 排除集 / 索引文件名均由调用方注入（cli 层从 config 解析）。
  - 提供函数式接口 gen_index(repo, cfg)，cli 与 ingest 复用（不再 subprocess 自调）。

P3 索引过期检测（2026-08-24，schema 1.0 → 1.1）：
  - collect() 为每篇文档记录磁盘指纹 mtime_ns + size，供
    recall.KbRetriever.check_freshness() 比对文件系统（changed/deleted/added）。
  - 动机：索引与磁盘脱节时召回无任何感知——改内容查不到、新文档不可见、
    删除后返回幽灵文档（read_doc 直接 FileNotFoundError）。
依赖：仅 Python 标准库。
"""
import datetime
import hashlib
import json
import os
import re

from .kb_core import (
    FM_RE, parse_fm, strip_code_blocks, extract_headings, INLINE_CODE_RE,
)

# 索引 schema 版本：1.1 起新增每文档磁盘指纹（mtime_ns/size/content_hash），
# 供 recall.KbRetriever.check_freshness() 做索引过期检测（P3）。
# content_hash 用于 mtime 变而内容未变的场景决胜（git checkout/pull 恢复内容
# 会刷新 mtime，只看 mtime 会产生常态假阳性）。
SCHEMA_VERSION = "1.1"


def content_hash(text: str) -> str:
    """16 字节 blake2b（与 collect 读到的 utf-8 文本同口径，gen/check 一致即可）。"""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


def first_sentence_after(body, heading_key):
    """取 `## heading_key` 段内的首句（以句号或换行切分）。"""
    m = re.search(
        r"^##\s*" + re.escape(heading_key) + r"\s*$\n(.*?)(?=^\n##|\Z)",
        body, re.S | re.M,
    )
    if not m:
        return ""
    seg = m.group(1).strip()
    seg = re.split(r"[。\n]", seg)[0]
    return seg.strip()


def summarize(body, limit=200):
    s = first_sentence_after(body, "概述")
    if not s:
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            if para and not para.startswith("#") and not para.startswith("```"):
                s = re.split(r"[。\n]", para)[0].strip()
                break
    return s[:limit]


def make_description(fm, body, title, limit=120):
    d = (fm.get("description") or "").strip()
    if d and "<%" not in d:
        return d[:limit]
    s = summarize(body, limit)
    if s:
        return s
    return ("《%s》技术文档" % title)[:limit]


def body_variants(body):
    """正文双变体：

    - body_text      ：仅剥 ``` 代码块、保留内联 `code`（BM25 检索用，
                       `KbRetriever`/`CMake` 等标识符保持可检索）。
    - body_text_clean：再剥内联 `code`（wikilink 扫描用，避免 C++ `[[T]]`、
                       bash `[[ =~ ]]` 误报，与 kb_core.WIKILINK_RE 提取前提一致）。
    """
    no_blocks = strip_code_blocks(body)
    return no_blocks, INLINE_CODE_RE.sub("", no_blocks)


def collect(repo, exclude_dirs):
    documents = []
    for dp, dns, fns in os.walk(repo):
        dns[:] = [d for d in dns
                  if d not in exclude_dirs and not d.startswith(".")]
        for fn in fns:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, repo).replace("\\", "/")
            try:
                text = open(full, encoding="utf-8").read()
            except Exception:
                continue
            m = FM_RE.match(text)
            if not m:
                # 跳过无 frontmatter 的 vendored 文件（如 CHANGELOG/CONTRIBUTING）
                continue
            fm_text = m.group(1)
            body = text[m.end():]
            try:
                fm = parse_fm(fm_text)
            except Exception:
                continue
            basename = os.path.splitext(fn)[0]
            title = (fm.get("title") or "").strip()
            if not title or "<%" in title:
                title = basename
            categories = fm.get("categories") or []
            if isinstance(categories, str):
                categories = [categories]
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            kind = fm.get("kind") or "doc"
            if basename == "category-index":
                # 该文件由本模块生成，无论其 frontmatter 是否带 kind 都强制标记，
                # 保证 collect() 在覆盖写之前读到旧文件时也能正确分类。
                kind = "generated-index"
            headings = extract_headings(body)
            word_count = len(re.sub(r"\s", "", body))
            body_text, body_text_clean = body_variants(body)
            # P3：磁盘指纹（过期检测用；collect 本就读文件，stat/哈希成本可忽略）
            st = os.stat(full)
            documents.append({
                "path": rel,
                "mtime_ns": st.st_mtime_ns,
                "size": st.st_size,
                "content_hash": content_hash(text),
                "basename": basename,
                "title": title,
                "description": make_description(fm, body, title),
                "categories": categories,
                "tags": tags,
                "difficulty": fm.get("difficulty", "") or "",
                "estimated_time": fm.get("estimated_time", "") or "",
                "updated": fm.get("updated", "") or "",
                "version": fm.get("version", "") or "",
                "word_count": word_count,
                "headings": headings,
                "summary": summarize(body),
                "body_text": body_text,
                "body_text_clean": body_text_clean,
                "kind": kind,
            })
    return documents


def build_index(documents):
    category_index = {}
    tag_index = {}
    for d in documents:
        for c in d["categories"]:
            category_index.setdefault(c, []).append(d["path"])
        for t in d["tags"]:
            tag_index.setdefault(t, []).append(d["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": os.path.basename(os.path.abspath(os.curdir)) or "knowledge-base",
        "doc_count": len(documents),
        "documents": documents,
        "category_index": category_index,
        "tag_index": tag_index,
    }


def slug(s):
    s = s.strip().lower()
    s = re.sub(r"[^\w一-鿿\- ]+", "", s)
    s = s.replace(" ", "-")
    return s


def gen_category_md(documents):
    cats = {}
    for d in documents:
        for c in d["categories"]:
            cats.setdefault(c, []).append(d)
    ordered = sorted(cats.items(), key=lambda kv: len(kv[1]), reverse=True)
    today = datetime.date.today().isoformat()
    L = []
    L.append("---")
    L.append('title: "知识库分类导航索引"')
    L.append('description: "按 categories 受控词表聚合全部文档的自动生成导航页，便于按主题发现内容。"')
    L.append('created: "%s"' % today)
    L.append('updated: "%s"' % today)
    L.append('version: "1.0"')
    L.append("categories: ['导航索引']")
    L.append("tags:")
    L.append("  - 导航")
    L.append("  - 索引")
    L.append("  - 分类")
    L.append('difficulty: "beginner"')
    L.append('estimated_time: "5分钟"')
    L.append("kind: generated-index")
    L.append("---")
    L.append("")
    L.append("# 🗂️ 知识库分类导航索引")
    L.append("")
    L.append("> 自动生成（%d 篇文档 / %d 个分类）。本页按 `categories` 受控词表聚合，每个分类下列出所属文档，点击 `[[wikilink]]` 直达。" % (len(documents), len(ordered)))
    L.append("")
    L.append("## 分类目录")
    L.append("")
    for cat, ds in ordered:
        L.append("- [%s](#%s) (%d 篇)" % (cat, slug(cat), len(ds)))
    L.append("")
    for cat, ds in ordered:
        L.append("## %s" % cat)
        L.append("")
        for d in sorted(ds, key=lambda x: x["basename"]):
            L.append("- [[%s]]" % d["basename"])
        L.append("")
    return "\n".join(L)


def gen_index(repo, cfg):
    """生成索引与分类导航页。返回 index dict（doc_count 等供调用方报告）。"""
    documents = collect(repo, cfg.exclude_dirs)
    index = build_index(documents)
    index["source"] = os.path.basename(str(repo).rstrip("/\\")) or "knowledge-base"
    with open(cfg.index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    cat_md = os.path.join(repo, "category-index.md")
    with open(cat_md, "w", encoding="utf-8") as f:
        f.write(gen_category_md(documents))
    return index
