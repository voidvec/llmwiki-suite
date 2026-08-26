# -*- coding: utf-8 -*-
"""
lint.py — 知识库健康巡检（LlmWiki Lint 阶段，自研核心）

为什么必须自研（而非交给 lychee / markdown-link-check）：
  标准链接检查器只认 `[](url)` 与 http(s) URL，**不认 `[[wikilink]]`**，且不做
  「separator/case + 子目录相对路径」归一——假阳性事故正是源于此。
  ⇒ wikilink 判死 + frontmatter 校验 + 受控词表 三检必须由本模块承担；lychee 只补外链。

三检内容：
  1. 链接判死（铁律，来自 kb_core）：wikilink 路径式/裸名分别解析 + 归一；md 相对链接
     按源文件目录相对解析；`#anchor` 校验章节存在。
  2. frontmatter 必填：title / description / tags / difficulty；difficulty ∈ 受控枚举。
  3. 受控词表：categories ∈ 配置词表（llmwiki.toml > 索引派生 > 套件默认，见 config.load_vocab）。

退出码：errors == 0 则 0（通过），否则 1（pre-commit / CI 据此阻断）。

套件化改造（相对个人库 scripts/lint_kb.py）：
  - repo 参数化（不再锚定 .git）；报告默认写在 repo 根。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

from .kb_core import (
    build_link_index, split_fm, strip_code,
    extract_headings, resolve_wikilink, resolve_md_link, heading_exists,
    WIKILINK_RE, MD_LINK_RE, is_vendored,
)
from .config import Config, load_vocab

REQUIRED_FM = ["title", "description", "tags", "difficulty"]
DIFFICULTY_ENUM = {"beginner", "intermediate", "advanced"}
IGNORE_FILE = ".kb-lint-ignore.json"


def load_ignore(repo):
    """读取库根的 `.kb-lint-ignore.json`（忽略规则数组，正则串，匹配 `rel :: detail`）。

    用于隔离**历史遗留**断链，使基线可达 0；新增断链仍会失败。
    规则需附注释说明来源。
    """
    path = os.path.join(repo, IGNORE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            rules = json.load(f)
        return [re.compile(r) for r in rules if isinstance(r, str)]
    except Exception:
        return []


def is_ignored(rel, issue, rules):
    key = "%s :: %s" % (rel, issue["detail"])
    return any(r.search(key) for r in rules)


def _norm_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).split(",") if x.strip()]


def collect_staged_md():
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")
    except Exception:
        return []
    return [l.strip() for l in out.splitlines() if l.strip().endswith(".md")]


def lint_file(rel, index, vocab, repo):
    """返回该文件的 issue 列表：{level, rule, detail}。"""
    doc = index["files"].get(rel)
    if not doc:
        return []
    fm, body = doc["fm"], doc["body"]
    issues = []

    # ---- FM 缺失（vendored 除外） ----
    if fm is None:
        if not is_vendored(rel):
            issues.append({"level": "error", "rule": "fm.missing",
                           "detail": "缺少 frontmatter，文档不会进入召回索引"})
        return issues  # 无 FM 不继续做 FM/链接细检（避免噪声）

    # ---- FM 必填与枚举 ----
    for k in REQUIRED_FM:
        if not fm.get(k):
            issues.append({"level": "error", "rule": "fm.required:%s" % k,
                           "detail": "frontmatter 缺少必填字段 `%s`" % k})
    diff = (fm.get("difficulty") or "").strip()
    if diff and diff not in DIFFICULTY_ENUM:
        issues.append({"level": "error", "rule": "fm.enum:difficulty",
                       "detail": "difficulty=`%s` 不在 %s" % (diff, sorted(DIFFICULTY_ENUM))})

    # ---- 受控词表 ----
    if vocab is not None:
        for c in _norm_list(fm.get("categories")):
            if c not in vocab:
                issues.append({"level": "error", "rule": "fm.category",
                               "detail": "categories 含非受控词 `%s`（受控 %d 类）" % (c, len(vocab))})
    elif _norm_list(fm.get("categories")):
        issues.append({"level": "warning", "rule": "fm.category:novocab",
                       "detail": "词表不可用，跳过 categories 受控校验"})

    # ---- 链接判死 ----
    clean = strip_code(body)
    for m in WIKILINK_RE.finditer(clean):
        target = m.group(1)
        status, resolved = resolve_wikilink(target, rel, index)
        if status == "missing":
            issues.append({"level": "error", "rule": "link.wikilink.dead",
                           "detail": "断链 [[%s]]（归一后仍无匹配目标）" % target})
    for m in MD_LINK_RE.finditer(clean):
        target = m.group("target")
        status, resolved, anchor = resolve_md_link(target, rel, index, repo)
        if status == "external":
            continue  # 外链交给 lychee
        if status == "anchor_same":
            if anchor and not heading_exists(rel, anchor, index):
                issues.append({"level": "warning", "rule": "link.anchor",
                               "detail": "本文件锚点 #%s 无对应章节" % anchor})
            continue
        if status == "missing":
            issues.append({"level": "error", "rule": "link.md.dead",
                           "detail": "断链 [..](%s)（相对路径归一后不存在）" % target})
        elif status == "ok" and anchor:
            if not heading_exists(resolved, anchor, index):
                issues.append({"level": "warning", "rule": "link.anchor",
                               "detail": "[..](%s) 锚点 #%s 在目标文件中无对应章节" % (target, anchor)})
    return issues


def run_lint(cfg: Config, files=None, staged=False, report=None, sync_vocab=False):
    """巡检主入口。返回退出码（0 通过 / 1 有 error）。"""
    repo = str(cfg.repo)
    index = build_link_index(repo, cfg.exclude_dirs)
    vocab = load_vocab(cfg)

    # 自愈：把索引派生的实际类别并入生效词表（不持久化到 toml，仅本次校验用）
    if sync_vocab:
        from .config import derive_vocab_from_index
        derived = derive_vocab_from_index(cfg)
        if derived - set(vocab or {}):
            added = sorted(derived - set(vocab or {}))
            vocab = (vocab or set()) | derived
            print("[lint] --sync-vocab：并入索引派生类别 %d 个：%s"
                  % (len(added), ", ".join(added)))
        else:
            print("[lint] 词表已覆盖全部实际类别，无需同步。")
    ignore_rules = load_ignore(repo)

    if files:
        targets = [f for f in files if f.endswith(".md")]
    elif staged:
        targets = collect_staged_md()
        if not targets:
            print("[lint] 暂存区无 .md 变更，跳过。")
            return 0
    else:
        targets = list(index["files"].keys())

    all_issues = {}
    ignored = 0
    for rel in targets:
        issues = lint_file(rel, index, vocab, repo)
        kept = []
        for i in issues:
            if is_ignored(rel, i, ignore_rules):
                ignored += 1
                continue
            kept.append(i)
        if kept:
            all_issues[rel] = kept

    errors = sum(1 for iss in all_issues.values() for i in iss if i["level"] == "error")
    warns = sum(1 for iss in all_issues.values() for i in iss if i["level"] == "warning")

    report_path = report or os.path.join(repo, "lint-report.json")
    report_data = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "checked_files": len(targets),
        "errors": errors,
        "warnings": warns,
        "ignored": ignored,
        "issues_by_file": all_issues,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print("[lint] 检查 %d 个文件 | errors=%d warnings=%d ignored=%d"
          % (len(targets), errors, warns, ignored))
    if all_issues:
        for rel, iss in sorted(all_issues.items()):
            for i in iss:
                print("  %-7s %s :: %s" % (i["level"], rel, i["detail"]))
    print("[lint] 报告已写 %s" % report_path)
    return 0 if errors == 0 else 1


def main(argv=None):
    from .config import resolve_repo, load_config
    ap = argparse.ArgumentParser(prog="llmwiki lint", description="知识库健康巡检")
    ap.add_argument("--repo", default=None, help="知识库根目录（默认: 当前目录解析）")
    ap.add_argument("--staged", action="store_true", help="仅检查 git 暂存区 .md")
    ap.add_argument("files", nargs="*", help="指定文件（相对于库根）")
    ap.add_argument("--report", default=None, help="JSON 报告输出路径")
    args = ap.parse_args(argv)

    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    return run_lint(cfg, files=args.files, staged=args.staged, report=args.report)


if __name__ == "__main__":
    sys.exit(main())
