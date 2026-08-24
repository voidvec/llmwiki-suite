# -*- coding: utf-8 -*-
"""cli.py — llmwiki 命令行入口。

命令族（docs/llmwiki-suite-design.md §4.2）：
  llmwiki init     生成 llmwiki.toml 模板 + 拷脚手架（.gitignore/pre-commit/CI）
  llmwiki ingest   补 frontmatter + 规范化 wikilink（默认 dry-run）
  llmwiki index    建检索索引（BM25 + wikilink 图）
  llmwiki query    召回 / 问答（配置 LLM_API_KEY 后生成完整回答）
  llmwiki lint     巡检：断链 / 词表 / 命名
  llmwiki eval     评估召回质量（recall@k / MRR）

所有命令支持 `--repo <path>` 覆盖 CWD（D3 解析链：--repo → CWD 向上找 .git → 报错）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from . import __version__
from .config import resolve_repo, load_config

# 包内置数据目录（templates / scaffold / eval_queries.json）
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TOML_TEMPLATE = """\
# llmwiki 配置（由 `llmwiki init` 生成）
# 三层模型：套件默认 < 本文件 < 环境变量（密钥只走环境变量，本套件不读 .env）

[repo]
index_file = "kb-index.json"                  # 检索索引产物路径

[ingest]
# 在套件默认排除集（.git/.obsidian/scripts 等）之上追加，追加语义
extra_exclude = []

[categories]
# 覆盖默认词表（整体替换语义）。默认：知识库规范/软件架构/会议纪要/读书笔记/工具指南/参考手册
# 注意：「导航索引」为生成产物 category-index.md 专用，自定义词表时请保留
allowed = ["知识库规范", "软件架构", "会议纪要", "读书笔记", "工具指南", "参考手册", "导航索引"]

[aliases]
# 别名组（追加语义，在套件默认组之上扩展）：组内变体打分时双向扩展，
# 用于中英/缩写互查（如查「系统架构」命中标题为 architecture 的文档）。
# groups = [
#     ["反向代理", "nginx"],
#     ["消息队列", "mq", "message-queue"],
# ]

[llm]
# 非密钥项；LLM_API_KEY 只走环境变量
model = "gpt-4o-mini"
# base_url = "https://api.openai.com/v1"
"""

GITIGNORE_LINES = """\
# --- llmwiki 产物（自动生成，勿提交） ---
kb-index.json
category-index.md
ingest-report.json
lint-report.json
eval_reports/
.env
"""


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------
def _install_scaffold(repo: str) -> list[str]:
    """把 scaffold 模板拷进用户库（已存在的文件不覆盖，.gitignore 追加）。"""
    installed = []
    scaffold_dir = os.path.join(_DATA_DIR, "scaffold")

    # .gitignore：追加 llmwiki 产物行（若无标记则追加）
    gi = os.path.join(repo, ".gitignore")
    marker = "# --- llmwiki 产物"
    existing = ""
    if os.path.isfile(gi):
        with open(gi, "r", encoding="utf-8") as f:
            existing = f.read()
    if marker not in existing:
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("\n" if existing and not existing.endswith("\n") else "")
                    + GITIGNORE_LINES)
        installed.append(".gitignore (追加产物忽略)")

    # pre-commit / CI：不存在才拷
    for name, dst_rel in [
        (".pre-commit-config.yaml", ".pre-commit-config.yaml"),
        ("kb-lint.yml", os.path.join(".github", "workflows", "kb-lint.yml")),
    ]:
        src = os.path.join(scaffold_dir, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(repo, dst_rel)
        if os.path.isfile(dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        installed.append(dst_rel.replace("\\", "/"))

    # templates/：通用模板拷到库根 templates/（默认排除，不进索引）
    tpl_src = os.path.join(_DATA_DIR, "templates")
    tpl_dst = os.path.join(repo, "templates")
    if os.path.isdir(tpl_src):
        os.makedirs(tpl_dst, exist_ok=True)
        for fn in os.listdir(tpl_src):
            if fn.endswith(".md") and not os.path.isfile(os.path.join(tpl_dst, fn)):
                shutil.copyfile(os.path.join(tpl_src, fn), os.path.join(tpl_dst, fn))
                installed.append(f"templates/{fn}")
    return installed


def cmd_init(args) -> int:
    repo = str(resolve_repo(args.repo))
    toml_path = os.path.join(repo, "llmwiki.toml")
    if os.path.isfile(toml_path) and not args.force:
        print(f"[init] {toml_path} 已存在（--force 覆盖）")
    else:
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(TOML_TEMPLATE)
        print(f"[init] 已生成 {toml_path}")

    installed = _install_scaffold(repo)
    if installed:
        print("[init] 脚手架已安装：")
        for i in installed:
            print(f"  - {i}")
    else:
        print("[init] 脚手架均已存在，跳过")
    print("[init] 下一步：llmwiki ingest → llmwiki index → llmwiki query")
    return 0


# --------------------------------------------------------------------------
# 其他子命令（转发到对应模块）
# --------------------------------------------------------------------------
def cmd_ingest(args) -> int:
    from .ingest import run_ingest
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    run_ingest(cfg, apply=args.apply, move=args.move, report=args.report)
    return 0


def cmd_index(args) -> int:
    from .gen_index import gen_index
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    index = gen_index(repo, cfg)
    print("生成完成: %d 篇文档, %d 个分类, %d 个标签"
          % (index["doc_count"], len(index["category_index"]), len(index["tag_index"])))
    return 0


def cmd_query(args) -> int:
    from .assistant import KbAssistant
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    if not cfg.index_path.is_file():
        print("[query] 索引不存在（%s），请先运行 llmwiki index" % cfg.index_path,
              file=sys.stderr)
        return 1
    assistant = KbAssistant(
        cfg.index_path,
        llm_base_url=cfg.llm_base_url,
        llm_model=cfg.llm_model,
        exclude_dirs=cfg.exclude_dirs,
        alias_groups=cfg.alias_groups,
        min_score_per_term=cfg.min_score_per_term,
    )
    if args.recall_only:
        hits = assistant.recall(args.query, top_k=args.top_k,
                                categories=args.categories, tags=args.tags)
        for h in hits:
            tag = " [link]" if h.via_link else ""
            print(f"[{h.score:.3f}]{tag} {h.path}")
            if h.matched_headings:
                print(f"        命中章节: {h.matched_headings[:3]}")
        if not hits:
            print("（无命中）")
        return 0
    answer, candidates = assistant.answer(
        args.query, top_k=args.top_k,
        categories=args.categories, tags=args.tags)
    print(answer)
    if candidates:
        print("\n来源:")
        for c in candidates:
            print(f"  - {c['path']} (score={c['score']:.3f})")
    return 0


def cmd_lint(args) -> int:
    from .lint import run_lint
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    return run_lint(cfg, files=args.files, staged=args.staged, report=args.report)


def cmd_eval(args) -> int:
    from .eval_recall import run_eval_cmd
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    run_eval_cmd(cfg, queries_path=args.queries, top_k=args.top_k,
                 min_score=args.min_score, out_dir=args.out_dir, tag=args.tag,
                 retriever_desc=args.retriever_desc, prod_top_k=args.prod_top_k)
    return 0


# --------------------------------------------------------------------------
# 参数装配
# --------------------------------------------------------------------------
def _add_repo_arg(ap):
    ap.add_argument("--repo", default=None,
                    help="知识库根目录（默认: --repo > CWD 向上找 .git > CWD）")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmwiki",
        description="LLM-compiled personal wiki toolkit（Ingest / Query / Lint）")
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # init
    sp = sub.add_parser("init", help="生成 llmwiki.toml 模板 + 脚手架")
    _add_repo_arg(sp)
    sp.add_argument("--force", action="store_true", help="覆盖已存在的 llmwiki.toml")
    sp.set_defaults(func=cmd_init)

    # ingest
    sp = sub.add_parser("ingest", help="补 frontmatter + 规范化（默认 dry-run）")
    _add_repo_arg(sp)
    sp.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    sp.add_argument("--move", action="store_true", help="--apply 时额外执行建议目录移动（谨慎）")
    sp.add_argument("--report", default=None)
    sp.set_defaults(func=cmd_ingest)

    # index
    sp = sub.add_parser("index", help="建检索索引（BM25 + wikilink 图）")
    _add_repo_arg(sp)
    sp.set_defaults(func=cmd_index)

    # query
    sp = sub.add_parser("query", help="召回 / 问答")
    _add_repo_arg(sp)
    sp.add_argument("query", help="查询文本")
    sp.add_argument("--top-k", type=int, default=6)
    sp.add_argument("--recall-only", action="store_true", help="仅打印召回候选，不调 LLM")
    sp.add_argument("--categories", nargs="*", default=None)
    sp.add_argument("--tags", nargs="*", default=None)
    sp.set_defaults(func=cmd_query)

    # lint
    sp = sub.add_parser("lint", help="健康巡检（断链/词表/命名）")
    _add_repo_arg(sp)
    sp.add_argument("--staged", action="store_true", help="仅检查 git 暂存区 .md")
    sp.add_argument("files", nargs="*", help="指定文件（相对于库根）")
    sp.add_argument("--report", default=None)
    sp.set_defaults(func=cmd_lint)

    # eval
    sp = sub.add_parser("eval", help="评估召回质量（recall@k / MRR）")
    _add_repo_arg(sp)
    sp.add_argument("--queries", default=None)
    sp.add_argument("--top-k", type=int, default=None)
    sp.add_argument("--min-score", type=float, default=0.15)
    sp.add_argument("--out-dir", default=None)
    sp.add_argument("--tag", default=None)
    sp.add_argument("--retriever-desc", default=None)
    sp.add_argument("--prod-top-k", type=int, default=3)
    sp.set_defaults(func=cmd_eval)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise


if __name__ == "__main__":
    sys.exit(main())
