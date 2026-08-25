# -*- coding: utf-8 -*-
"""
ingest.py — Ingest 前半自动化（原始笔记 → 可被索引消费的规范文档）

闭合 Ingest 闭环在「摄入前置」的断点：gen_index 只消费已规范文档，
缺 FM 的文件会被直接跳过、永不进入召回。本模块把零散笔记补齐为规范文档。

四件事（均行级编辑，绝不整体重写 / 绝不删除 `---` 分隔符）：
  1. 补 frontmatter（缺则建、残则补必填字段 title/description/tags/difficulty）。
  2. 文件名归一（lower + 空格/下划线→`-` + 全角`：`→`-`，同目录内重命名）。
  3. SHA256 去重（命中已有文档 → 仅报告，不删除，防误删真不同文档）。
  4. 建议归类目录（仅**报告**，默认不跨目录移动——见 R2 守卫）。

安全守卫：
  R1 幂等：仅处理「FM 缺失/残缺 或 文件名未归一」的文档；已规范的文档跳过 → 重跑 0 diff。
  R2 不动目录：跨目录移动会触发全库 wikilink 同步、爆炸半径大，故只报告建议目录，
      不自动移动。需要移动时请人工 review 后用 `git mv` 并跑 lint 校验。
  LLM 离线降级：未配置 LLM_API_KEY 时，categories 留空（lint 不报错），保证脚本可离线跑通。

套件化改造（相对个人库 scripts/_ingest_normalize.py）：
  - repo / 词表参数化；重建索引改调包内 gen_index.gen_index()（不再 subprocess）。
依赖：仅标准库；LLM 调用走环境变量（可选）。
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request

from . import _env
from .kb_core import (
    build_link_index, split_fm, is_vendored,
    sha256_text, normalize_token,
)
from .config import Config, load_vocab

REQUIRED_FM = ["title", "description", "tags", "difficulty"]

# tags 占位值：lint 要求必填字段非空（`tags: []` 是 falsy 会被判缺失），
# 故 ingest 生成的空 tags 用占位标签，用户后续可改。
_PLACEHOLDER_TAG = "未分类"


# --------------------------------------------------------------------------
# FM 补全（行级：保留已有行，仅追加缺失字段，绝不删 `---`）
# --------------------------------------------------------------------------
def first_sentence(body, limit=120):
    for para in body.split("\n\n"):
        para = para.strip()
        if para and not para.startswith("#") and not para.startswith("```"):
            return para.split("。")[0].split("\n")[0].strip()[:limit]
    return ""


def build_fm_block(rel, body):
    base = os.path.splitext(os.path.basename(rel))[0]
    title = base
    desc = first_sentence(body) or ("《%s》技术文档" % title)
    today = datetime.date.today().isoformat()
    lines = [
        "---",
        'title: "%s"' % title,
        'description: "%s"' % desc.replace('"', "'"),
        "categories: []",
        "tags: ['%s']" % _PLACEHOLDER_TAG,
        'difficulty: "beginner"',
        'estimated_time: "10分钟"',
        'created: "%s"' % today,
        'updated: "%s"' % today,
        'version: "1.0"',
        "---",
        "",
    ]
    return "\n".join(lines)


def ensure_fm(text, rel):
    """无 FM → 前置生成块；有 FM 但缺必填字段 → 在闭合 `---` 前追加。返回 (new_text, added)。"""
    fm, body, raw = split_fm(text)
    if fm is None:
        new_text = build_fm_block(rel, body) + body
        return new_text, ["<created>"]
    added = []
    # raw 是 FM 内部内容（不含两端 ---）；逐行保留，缺失字段追加在末尾（闭合 --- 之前）
    inner_lines = raw.split("\n")
    existing_keys = set()
    for ln in inner_lines:
        m = __import__("re").match(r"^([\w-]+)\s*:", ln)
        if m:
            existing_keys.add(m.group(1))
    base = os.path.splitext(os.path.basename(rel))[0]
    for key in REQUIRED_FM:
        if key in existing_keys:
            continue
        if key == "title":
            inner_lines.append('title: "%s"' % base)
        elif key == "description":
            desc = first_sentence(body) or ("《%s》技术文档" % base)
            inner_lines.append('description: "%s"' % desc.replace('"', "'"))
        elif key == "tags":
            inner_lines.append("tags: ['%s']" % _PLACEHOLDER_TAG)
        elif key == "difficulty":
            inner_lines.append('difficulty: "beginner"')
        added.append(key)
    if added:
        new_text = "---\n" + "\n".join(inner_lines) + "\n---\n" + body
        return new_text, added
    return text, []


# --------------------------------------------------------------------------
# LLM 元数据推断（可选；categories 必须 ∈ 受控词表，否则丢弃）
# 凭证只走环境变量（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL）。
# --------------------------------------------------------------------------
def infer_metadata(title, body, vocab, llm_base_url, llm_api_key, llm_model):
    if not llm_api_key:
        return None
    snippet = first_sentence(body, 400) or title
    vocab_hint = "、".join(sorted(vocab)) if vocab else "（未知）"
    prompt = (
        "你是知识库分类助手。根据标题与摘要，输出 JSON："
        '{"categories": [属于受控词表的1-3个分类], "tags": [3-5个标签], '
        '"description": "一句话描述"}。\n'
        "受控词表（categories 必须从中选取，勿自造）：%s\n"
        "标题：%s\n摘要：%s" % (vocab_hint, title, snippet)
    )
    try:
        req = urllib.request.Request(
            llm_base_url + "/chat/completions",
            data=json.dumps({"model": llm_model,
                             "messages": [{"role": "user", "content": prompt}],
                             "temperature": 0.2}).encode("utf-8"),
            headers={"Authorization": "Bearer " + llm_api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        # 抽取首个 JSON 对象
        s = content.find("{")
        e = content.rfind("}")
        if s >= 0 and e > s:
            return json.loads(content[s:e + 1])
    except Exception:
        return None
    return None


def apply_inferred(text, rel, vocab, llm_base_url, llm_api_key, llm_model):
    fm, body, raw = split_fm(text)
    if fm is None:
        return text, []
    title = fm.get("title") or os.path.splitext(os.path.basename(rel))[0]
    meta = infer_metadata(title, body, vocab, llm_base_url, llm_api_key, llm_model)
    if not meta:
        return text, []
    changed = []
    inner_lines = raw.split("\n")
    existing_keys = {__import__("re").match(r"^([\w-]+)\s*:", ln).group(1)
                     for ln in inner_lines if __import__("re").match(r"^([\w-]+)\s*:", ln)}
    # categories：仅当当前为空且推断值全部 ∈ vocab 时才写入
    cur_cats = fm.get("categories") or []
    if (not cur_cats) and vocab is not None:
        good = [c for c in meta.get("categories", []) if c in vocab]
        if good:
            inner_lines.append("categories: %s" % json.dumps(good, ensure_ascii=False))
            changed.append("categories")
    # tags：仅当当前为空
    cur_tags = fm.get("tags") or []
    if not cur_tags and meta.get("tags"):
        inner_lines.append("tags: %s" % json.dumps(meta["tags"][:5], ensure_ascii=False))
        changed.append("tags")
    if changed:
        return "---\n" + "\n".join(inner_lines) + "\n---\n" + body, changed
    return text, []


# --------------------------------------------------------------------------
# 文件名归一 + 去重
# --------------------------------------------------------------------------
def normalize_basename(rel):
    base, ext = os.path.splitext(os.path.basename(rel))
    new_base = normalize_token(base)
    if new_base != base:
        return os.path.dirname(rel) + "/" + new_base + ext if os.path.dirname(rel) else new_base + ext
    return None  # 已规范


def suggest_dir(category, index):
    """根据分类猜测顶层目录：归一后与某顶层目录名一致则采用。"""
    nc = normalize_token(category)
    top_dirs = sorted({d.split("/")[0] for d in index["by_dir"] if "/" not in d})
    for d in top_dirs:
        if normalize_token(d) == nc:
            return d
    return None


def _git_mv(repo, src, dst):
    """优先 git mv（保留历史）；对 untracked 新文件 git mv 会失败，fallback os.rename。"""
    import subprocess
    try:
        os.makedirs(os.path.join(repo, os.path.dirname(dst) or "."), exist_ok=True)
        r = subprocess.run(["git", "-C", repo, "mv", src, dst],
                           capture_output=True, check=False)
        if r.returncode != 0:
            src_full = os.path.join(repo, src)
            dst_full = os.path.join(repo, dst)
            if os.path.isfile(src_full) and not os.path.exists(dst_full):
                os.rename(src_full, dst_full)
    except Exception:
        pass


def run_ingest(cfg: Config, apply=False, move=False, report=None):
    """Ingest 主入口。返回计划文件数。"""
    repo = str(cfg.repo)
    llm_base_url = cfg.llm_base_url
    llm_api_key = _env.getenv("API_KEY", "")
    llm_model = cfg.llm_model

    index = build_link_index(repo, cfg.exclude_dirs)
    vocab = load_vocab(cfg)
    # 现有内容哈希表（去重用）
    hashes = {}
    for rel, doc in index["files"].items():
        h = sha256_text(doc["text"])
        hashes.setdefault(h, []).append(rel)

    plan = []  # 每个文件的处理计划
    for rel, doc in sorted(index["files"].items()):
        if is_vendored(rel):
            continue
        text = doc["text"]
        fm = doc["fm"]
        actions = []

        # 1+2 FM 补全
        new_text, added = ensure_fm(text, rel)
        if added:
            actions.append({"type": "fm", "detail": "补齐字段 %s" % added})
            text = new_text
        # LLM 推断（仅当 FM 已存在且 categories/tags 为空；dry-run 也会调用，注意配额）
        if apply and llm_api_key:
            new_text, changed = apply_inferred(
                text, rel, vocab, llm_base_url, llm_api_key, llm_model)
            if changed:
                actions.append({"type": "llm", "detail": "推断 %s" % changed})
                text = new_text

        # 3 文件名归一
        new_rel = normalize_basename(rel)
        if new_rel and new_rel != rel:
            actions.append({"type": "rename", "detail": "%s -> %s" % (rel, new_rel)})

        # 4 去重
        h = sha256_text(text)
        dups = [r for r in hashes.get(h, []) if r != rel]
        if dups:
            actions.append({"type": "dup", "detail": "与 %s 内容重复（不删除）" % dups})

        # 建议目录（仅报告）
        if fm and fm.get("categories"):
            cat = (fm["categories"][0] if isinstance(fm["categories"], list) else fm["categories"])
            sugg = suggest_dir(cat, index)
            if sugg and os.path.dirname(rel) != sugg:
                actions.append({"type": "suggest-move", "detail": "建议目录 %s" % sugg})

        if actions:
            plan.append({"rel": rel, "actions": actions})

    # 输出
    print("[ingest] 需处理文件：%d（dry-run=%s）" % (len(plan), not apply))
    for p in plan:
        print("  %s" % p["rel"])
        for a in p["actions"]:
            print("    - %-12s %s" % (a["type"], a["detail"]))

    report_path = report or os.path.join(repo, "ingest-report.json")
    report_data = {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": not apply,
        "planned_files": len(plan),
        "plan": plan,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print("[ingest] 报告已写 %s" % report_path)

    # 执行
    if not apply:
        print("[ingest] 仅 dry-run。加 --apply 执行写入（会重建索引）。")
        return len(plan)

    for p in plan:
        rel = p["rel"]
        doc = index["files"][rel]
        text = doc["text"]
        # 重新计算（与上面一致，避免状态漂移）
        new_text, added = ensure_fm(text, rel)
        wrote = False
        if added:
            with open(os.path.join(repo, rel), "w", encoding="utf-8") as f:
                f.write(new_text)
            wrote = True
        if llm_api_key:
            new_text2, changed = apply_inferred(
                new_text if wrote else text, rel, vocab,
                llm_base_url, llm_api_key, llm_model)
            if changed:
                with open(os.path.join(repo, rel), "w", encoding="utf-8") as f:
                    f.write(new_text2)
                wrote = True
        rename_action = next((a for a in p["actions"] if a["type"] == "rename"), None)
        if rename_action:
            dst = rename_action["detail"].split(" -> ")[1]
            _git_mv(repo, rel, dst)
        # suggest-move 默认不执行；--move 时谨慎处理
        if move:
            mv = next((a for a in p["actions"] if a["type"] == "suggest-move"), None)
            if mv:
                dst_dir = mv["detail"].split("建议目录 ")[1]
                if os.path.isdir(os.path.join(repo, dst_dir)):
                    dst = dst_dir + "/" + os.path.basename(rel)
                    if not os.path.exists(os.path.join(repo, dst)):
                        _git_mv(repo, rel, dst)
                        print("    [move] %s -> %s（请跑 lint 校验引用）" % (rel, dst))
    # 重建索引（Ingest 最后一环，包内直调）
    print("[ingest] 重建索引...")
    from .gen_index import gen_index
    gen_index(cfg.repo, cfg)
    print("[ingest] 完成。")
    return len(plan)


def main(argv=None):
    from .config import resolve_repo, load_config
    ap = argparse.ArgumentParser(prog="llmwiki ingest", description="摄入归一：补 FM/重命名/去重")
    ap.add_argument("--repo", default=None, help="知识库根目录（默认: 当前目录解析）")
    ap.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    ap.add_argument("--move", action="store_true", help="--apply 时额外执行建议目录移动（谨慎）")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    run_ingest(cfg, apply=args.apply, move=args.move, report=args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
