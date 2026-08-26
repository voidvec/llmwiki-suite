# -*- coding: utf-8 -*-
"""
kb_core.py -- LlmWiki 共享核心（lint / ingest / index 共用，零三方依赖）

本模块是「链接判死铁律」「frontmatter 解析」的**唯一事实源**，
供 lint / ingest / index 生成器共用，避免两处各写一套归一逻辑再各自踩坑。

铁律（链接判死四步）：
  1. 用仓库相对路径建全局索引，不用绝对路径（绝对路径盘符会被 lower 破坏匹配）。
  2. 目录 + 文件名都归一再比对：`_`↔`-`、`：`(全角)→`-`、大小写、正斜杠。
  3. 路径分隔符一律转正斜杠（Windows 反斜杠会让键永不匹配）。
  4. wikilink 两种写法分别解析：`[[dir/file]]` 路径式按根相对路径查；
     `[[basename]]` 裸名按全局 basename 索引查（Obsidian 语义）。

套件化改造（相对个人库 scripts/kb_core.py）：
  - 移除模块级 REPO_DEFAULT（`.git` 锚定）：所有函数以显式 `repo` 参数运行，
    仓库根由 cli 层的 config.resolve_repo() 解析后注入。
  - EXCLUDE_DIR 硬编码移除：排除集由 config.load_config() 合并（默认 + toml 追加）。

依赖：仅 Python 标准库。
"""
import hashlib
import json
import os
import re

# frontmatter 块：必须含开头的 --- 与闭合的 ---（行级编辑铁律：绝不删除 ---）。
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")

# 链接提取（在剥掉代码块/内联代码之后进行，否则 C++ `[[T]]`、bash `[[ =~ ]]` 误报）。
WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
MD_LINK_RE = re.compile(r"\[(?P<text>[^\]]*?)\]\((?P<target>[^)]+?)\)")


# --------------------------------------------------------------------------
# frontmatter 解析（扁平 key/value + 内联/块列表；不处理嵌套映射）
# --------------------------------------------------------------------------
def parse_fm(fm_text):
    """轻量 YAML frontmatter 解析，覆盖扁平结构。

    支持：标量 `key: value`、内联列表 `key: [a, b]`、块列表 `key:\\n  - a\\n  - b`。
    """
    data = {}
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        mm = re.match(r"^([\w-]+)\s*:\s*(.*)$", line)
        if not mm:
            i += 1
            continue
        key, val = mm.group(1), mm.group(2).strip()
        if val == "" or val in ("|", ">"):
            if i + 1 < len(lines) and re.match(r"^\s*-\s+", lines[i + 1]):
                items = []
                j = i + 1
                while j < len(lines) and re.match(r"^\s*-\s+", lines[j]):
                    item = re.match(r"^\s*-\s+(.*)$", lines[j]).group(1).strip()
                    item = item.strip('"').strip("'")
                    items.append(item)
                    j += 1
                data[key] = items
                i = j
                continue
            data[key] = ""
            i += 1
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            items = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            data[key] = items
        else:
            data[key] = val.strip('"').strip("'")
        i += 1
    return data


def split_fm(text):
    """返回 (fm_dict_or_None, body, raw_fm_text_or_None)。无 FM 时 fm=None。"""
    m = FM_RE.match(text)
    if not m:
        return None, text, None
    return parse_fm(m.group(1)), text[m.end():], m.group(1)


def strip_code_blocks(text):
    """只剥 ``` 代码块、保留内联 `code`。

    供正文索引使用：BM25 检索需保留 `KbRetriever`/`CMake` 等内联标识符。
    """
    return CODE_FENCE_RE.sub("", text)


def strip_code(text):
    """剥掉 ``` 代码块后再剥内联 `code`，用于安全的链接提取。"""
    text = CODE_FENCE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def extract_headings(body):
    clean = strip_code(body)
    clean = re.sub(r"`[^`]*`", "", clean)
    return [h.strip() for h in HEADING_RE.findall(clean)]


# --------------------------------------------------------------------------
# 归一化（铁律 2/3 的核心）
# --------------------------------------------------------------------------
def normalize_token(s):
    """链接/文件名归一：小写；`_`↔`-`（统一转 `-`）；全角冒号 `：` 与半角 `:` → `-`；
    空白压成 `-`；分隔符转正斜杠；折叠多余连字符。

    中文原样保留（Chinese 无大小写，lower 对其无副作用）。
    """
    s = (s or "").strip().lower()
    s = s.replace("：", "-").replace(":", "-")
    s = s.replace("_", "-")
    s = re.sub(r"\s+", "-", s)
    s = s.replace("\\", "/")
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _rel_no_ext(rel):
    return rel[:-3] if rel.endswith(".md") else rel


def gh_slug(s):
    """GitHub/Obsidian 风格的锚点 slug：小写；删除全角/半角标点（含 `：` 直接剔除，
    而非转标点；`/`、`+`、`.` 等同理删除）；空白压成 `-`。用于 `#anchor`
    与章节标题的一致性比对。"""
    s = (s or "").strip().lower()
    s = re.sub(r"[：:，。、！？（）()\[\]{}'\"/\\.,;+＊*]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


# emoji / 装饰字符（标题常用 📖🔧📑⚠️ 等前缀；不参与锚点比对）
_DECOR_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # Emoji 扩展
    "\U00002600-\U000027BF"   # 杂项符号（☑✦✖…）
    "\U00002300-\U000023FF"   # 杂项技术符号（⏰⏱⏳…）
    "\U0001F1E6-\U0001F1FF"   # 区域指示符
    "\uFE0F\u200D\u200B"      # 变体选择/零宽连接
    "]"
)


def anchor_slug(s):
    """锚点宽松 slug：gh_slug 基础上再剥离 emoji 装饰与「数字序号前缀」
    （`1.`/`1、`/`1-`/`3.1 配置` → `配置`；`步骤 3：`/`Step 4` → 剩余正文），
    并折叠中间 `.`/`-`/空格为 `-`，用于「链接内 `#1-概述` ↔ 标题 `## 1. 📖 概述`」
    「链接 `#2-生成-github-pat` ↔ 标题 `步骤 1：生成 GitHub PAT`」这类常见书写差异的容错比对。"""
    s = (s or "").strip().lower()
    s = _DECOR_RE.sub("", s)
    s = re.sub(r"^#{1,6}\s*", "", s)          # 剥 Markdown 标题语法（## 1. 概述 → 1. 概述）
    # 中文/英文序号前缀（三种形态，数字可在「序数词后」或「序数词前」）：
    # ① 第 N 步/章/节：数字在后  ② 步骤/章节 N：数字在前  ③ Step/Part N：英文序数
    s = re.sub(r"^第\s*[一二三四五六七八九十百\d]+\s*[步章节][：:]?\s*", "", s)
    s = re.sub(r"^(?:步骤|章节|小节|章|节|阶段)\s*第?\s*[一二三四五六七八九十百\d]+\s*[：:.、]?\s*", "", s)
    s = re.sub(r"^(?:step|part|section|sec|chapter|ch)\s*[-–—]?\s*[ivxlcdm\d]+\s*[：:.、]?\s*", "", s)
    # 数字序号前缀：1. / 1、 / 1- / 3.1- / -1. / 3.1  等（纯数字型，无文字序数）
    s = re.sub(r"^\s*[-–—]?\s*\d+(?:[.、\-–—]\d+)*\s*[.、\-–—]?\s*", "", s)
    s = s.replace("/", "").replace("&", "").replace("+", "")  # I/O、C&C++/斜杠并入词内
    s = re.sub(r"[\s.、·\-–—、；（）()]+", "-", s)   # 折叠分隔符与成对括号
    return s.strip("-")


# --------------------------------------------------------------------------
# 全局链接索引（铁律 1/2/3：仓库相对路径 + 归一键）
# --------------------------------------------------------------------------
def iter_md_files(repo, exclude_dirs):
    for dp, dns, fns in os.walk(repo):
        dns[:] = [d for d in dns
                  if d not in exclude_dirs and not d.startswith(".")]
        for fn in fns:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, repo).replace("\\", "/")
            yield rel, full


def build_link_index(repo, exclude_dirs):
    """建全局索引：
      by_rel : normalize(相对路径去 .md) -> 真实 rel        （路径式 wikilink / md 链接）
      by_base: normalize(basename 去 .md) -> [rel, ...]     （裸名 wikilink，Obsidian 语义）
      by_dir : normalize(目录相对路径) -> 真实 dir          （目录式导航链接，存在的文件夹即有效）
      files  : rel -> {"fm", "body", "text"}
    vendored 文件（无 KB frontmatter）也登记文件存在以便链接解析，但 FM 校验会跳过它们。
    """
    by_rel, by_base, by_dir, files = {}, {}, set(), {}
    for dp, dns, fns in os.walk(repo):
        # 目录索引：所有真实存在的目录（排除隐藏/排除目录）皆为合法 `[[folder]]` 目标
        dp_rel = os.path.relpath(dp, repo).replace("\\", "/")
        if dp_rel != "." and not dp_rel.startswith(".") \
                and os.path.basename(dp) not in exclude_dirs:
            by_dir.add(normalize_token(dp_rel))
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
            fm, body, _ = split_fm(text)
            files[rel] = {"fm": fm, "body": body, "text": text}
            by_rel[normalize_token(_rel_no_ext(rel))] = rel
            base = os.path.splitext(os.path.basename(rel))[0]
            by_base.setdefault(normalize_token(base), []).append(rel)
    return {"by_rel": by_rel, "by_base": by_base, "by_dir": by_dir, "files": files}


# --------------------------------------------------------------------------
# 链接解析（铁律 4：路径式 / 裸名分别解析）
# --------------------------------------------------------------------------
def resolve_wikilink(target, source_rel, index):
    """Obsidian 语义解析 `[[target]]`。target 可能含 `|alias` 或 `#heading`。
    返回 (status, resolved_rel_or_None)。status: 'ok' | 'missing'。
    'ok' 表示归一后命中（Obsidian 大小写/分隔符不敏感，命中即存活）。
    """
    link = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not link:
        return ("missing", None)
    nt = normalize_token(link)
    # 路径式：含 / 或显式相对/上级
    if "/" in nt or link in (".", ".."):
        if nt in index["by_rel"]:
            return ("ok", index["by_rel"][nt])
        if source_rel:
            base_dir = os.path.dirname(source_rel)
            joined = normalize_token(
                os.path.normpath(os.path.join(base_dir, link)).replace("\\", "/")
            )
            if joined in index["by_rel"]:
                return ("ok", index["by_rel"][joined])
            if joined in index["by_dir"]:  # 目录式导航链接
                return ("ok", joined)
        if nt in index["by_dir"]:
            return ("ok", nt)
        return ("missing", None)
    # 裸名：全局 basename 索引
    if nt in index["by_base"]:
        cands = index["by_base"][nt]
        if len(cands) == 1:
            return ("ok", cands[0])
        if source_rel:  # 同名多个：优先与 source 同目录
            sd = os.path.dirname(source_rel)
            same = [c for c in cands if os.path.dirname(c) == sd]
            if same:
                return ("ok", same[0])
        return ("ok", cands[0])  # 命中但存在同名歧义（lint 可额外 warning）
    # 裸名也可能指向目录（如 `[[21-Guide-Tutorial]]`）
    if nt in index["by_dir"]:
        return ("ok", nt)
    return ("missing", None)


def resolve_md_link(target, source_rel, index, repo):
    """解析标准 markdown 链接 `[text](target)`。
    返回 (status, resolved_rel_or_None, anchor_or_None)。
    status: 'external'（http/mailto，交给 lychee）| 'anchor_same'（仅 #锚点，同文件）
            | 'ok' | 'missing'。
    """
    t = (target or "").strip()
    if t.startswith(("http://", "https://", "mailto:", "ftp://", "file://", "//")):
        return ("external", None, None)
    path_part, _, anchor = t.partition("#")
    if not path_part:
        return ("anchor_same", None, anchor or None)
    if source_rel:
        base_dir = os.path.dirname(source_rel)
        joined = os.path.normpath(os.path.join(base_dir, path_part))
    else:
        joined = os.path.normpath(path_part)
    joined = joined.replace("\\", "/")
    if joined.endswith(".md"):
        key = normalize_token(_rel_no_ext(joined))
        if key in index["by_rel"]:
            return ("ok", index["by_rel"][key], anchor or None)
        return ("missing", None, anchor or None)
    # 非 .md 目标（图片 / LICENSE / 二进制）：按磁盘存在性判定，而非 .md 索引
    if os.path.exists(os.path.join(repo, joined)):
        return ("ok", joined, anchor or None)
    if joined in index["by_dir"]:
        return ("ok", joined, anchor or None)
    return ("missing", None, anchor or None)


def heading_exists(rel, anchor, index):
    """校验 `#anchor` 是否命中某文件的章节标题（GitHub slug 严格比对 +
    宽松锚点 slug 容错比对：剥离 emoji/序号/步骤前缀，见 anchor_slug）。"""
    if not anchor:
        return True
    doc = index["files"].get(rel)
    if not doc:
        return False
    na = gh_slug(anchor)
    na_loose = anchor_slug(anchor)
    for h in extract_headings(doc["body"]):
        if gh_slug(h) == na:
            return True
        # 宽松比对（如 #1-概述 ↔ ## 1. 📖 概述；#2-生成-github-pat ↔ 步骤 1：生成 GitHub PAT）
        if na_loose:
            h_loose = anchor_slug(h)
            if h_loose == na_loose or h_loose.startswith(na_loose + "-"):
                return True
    return False


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_vendored(rel):
    """vendored 仓库元数据（无 KB frontmatter）：巡检时排除 FM 缺失误报，也不注入相关文档。"""
    base = os.path.basename(rel).lower()
    return base in {
        "changelog.md", "claude.md", "contributing.md", "license.md", "readme.md",
        "code_of_conduct.md", "security.md",
    }
