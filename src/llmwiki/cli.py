# -*- coding: utf-8 -*-
"""cli.py — llmwiki 命令行入口。

命令族（docs/llmwiki-suite-design.md §4.2）：
  llmwiki init     生成 llmwiki.toml 模板 + 拷脚手架（.gitignore/pre-commit/CI）
  llmwiki ingest   补 frontmatter + 规范化 wikilink（默认 dry-run）
  llmwiki index    建检索索引（BM25 + wikilink 图）
  llmwiki query    召回 / 问答（配置 LLM_WIKI_API_KEY 后生成完整回答）
  llmwiki lint     巡检：断链 / 词表 / 命名
  llmwiki eval     评估召回质量（recall@k / MRR）
  llmwiki serve    启动 HTTP 桥接服务（需 extras: llmwiki[serve]）

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
# 非密钥项；LLM_WIKI_API_KEY 只走环境变量
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
    run_ingest(cfg, apply=args.apply, move=args.move, report=args.report,
               use_llm=not args.no_llm)
    return 0


def cmd_index(args) -> int:
    from .gen_index import gen_index
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    index = gen_index(repo, cfg)
    print("生成完成: %d 篇文档, %d 个分类, %d 个标签"
          % (index["doc_count"], len(index["category_index"]), len(index["tag_index"])))
    return 0


def _warn_stale(retriever) -> None:
    """P3：索引过期告警（结果可能过时，但不阻断查询）。"""
    fr = getattr(retriever, "freshness", None)
    if fr is None:
        return
    if fr.unknown:
        print("[query] 注意：索引由旧版生成（无过期指纹），建议运行 llmwiki index 重建",
              file=sys.stderr)
    elif fr.stale:
        print("[query] ⚠ %s；召回结果可能过时，建议运行 llmwiki index 重建"
              % fr.summary(), file=sys.stderr)


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
        link_gate=cfg.link_gate,
    )
    _warn_stale(assistant.retriever)
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
    return run_lint(cfg, files=args.files, staged=args.staged, report=args.report,
                    sync_vocab=args.sync_vocab)


def cmd_categories(args) -> int:
    """categories-sync：从 kb-index 派生全部实际类别，写回 llmwiki.toml。

    通用自愈入口：新增文档用新分类时，lint 不再因词表未收录而报错。
    --apply 直接写文件；否则打印建议补丁（默认 dry-run）。
    """
    from .config import derive_vocab_from_index
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    toml_path = repo / "llmwiki.toml"
    derived = derive_vocab_from_index(cfg)
    toml_allowed = set(cfg.categories_allowed)
    missing = sorted(derived - toml_allowed)   # 待补 = 派生词表 - 当前生效词表
    print("[categories] 当前词表: %d 类, 索引派生词表: %d 类, 待补: %d 类"
          % (len(toml_allowed), len(derived), len(missing)))
    if missing:
        print("[categories] 缺失类别: %s" % ", ".join(missing))
        if args.apply and toml_path.is_file():
            _write_vocab_to_toml(toml_path, missing)
        elif args.apply:
            print("[categories] toml 不存在，跳过写入（需先 llmwiki init）",
                  file=sys.stderr)
        else:
            print("[categories] dry-run：以上为建议补入 toml 的类别。加 --apply 写入。")
    else:
        print("[categories] 词表已覆盖全部实际类别，无需同步。")
    return 0


def _write_vocab_to_toml(toml_path, new_cats) -> None:
    """把待补类别合并进 llmwiki.toml 的 `[categories].allowed` 列表。

    文本级最小改写（不依赖 tomli_w）：读原文 → 在现有 allowed 列表后追加以
    下缺失类别 → 整行重写。找不到 allowed 行时在 [categories] 节追加一行。
    保留全部注释与其它节格式。
    """
    import re as _re
    text = toml_path.read_text(encoding="utf-8")
    cur = []
    m = _re.search(r'^\s*allowed\s*=\s*\[([^\]]*)\]\s*$', text, _re.M)
    if m:
        raw_inner = m.group(1)
        cur = [x.strip().strip('"\'')
               for x in raw_inner.split(",") if x.strip()]
    merged = list(dict.fromkeys(cur + list(new_cats)))
    rendered = 'allowed = ["%s"]' % '", "'.join(merged)
    if m:
        text = _re.sub(r'^\s*allowed\s*=\s*\[[^\]]*\]\s*$',
                       rendered, text, count=1, flags=_re.M)
    elif _re.search(r'^\[categories\]\s*$', text, _re.M):
        text = _re.sub(r'^(\[categories\]\s*)$', r'\1' + rendered + "\n",
                       text, count=1, flags=_re.M)
    else:
        text += "\n[categories]\n" + rendered + "\n"
    toml_path.write_text(text, encoding="utf-8")
    print("[categories] 已写入 %s 的 [categories].allowed（%d 类）"
          % (toml_path, len(merged)))


def cmd_eval(args) -> int:
    from .eval_recall import run_eval_cmd
    repo = resolve_repo(args.repo)
    cfg = load_config(repo)
    return run_eval_cmd(cfg, queries_path=args.queries, top_k=args.top_k,
                        min_score=args.min_score, out_dir=args.out_dir, tag=args.tag,
                        retriever_desc=args.retriever_desc, prod_top_k=args.prod_top_k,
                        chart=args.chart, demo=args.demo, seed=args.seed,
                        seed_limit=args.seed_limit)


def cmd_serve(args) -> int:
    """启动桥接服务（需 wechat extras：fastapi + uvicorn）。

    注意：`pip install llmwiki-suite`（不带 extras）**不会**装入
    fastapi/uvicorn，所以要跑微信/企业微信通道，必须安装带 wechat extra：
        pip install "llmwiki-suite[serve]"
    这里采用「延迟导入」（见下方 try/except）：
      - 没装 extras 时：命令友好报错并提示安装命令，不影响其它子命令；
      - 已装 extras 时：正常启动服务。
    """
    try:
        from .channels.wechat_bridge import app   # 延迟导入：仅 serve 时加载 fastapi 依赖
        import uvicorn
    except ImportError as e:
        print(f"[serve] 缺少通道依赖: {e}\n"
              f"       请安装: pip install \"llmwiki-suite[serve]\"", file=sys.stderr)
        return 1
    print(f"[serve] LlmWiki bridge on {args.host}:{args.port}  (Ctrl+C 退出)")
    uvicorn.run(app, host=args.host, port=args.port)
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
    sp.add_argument("--no-llm", action="store_true",
                    help="跳过 LLM 元数据推断（不配 key 时也无 LLM；配了想离线/秒级用则加）")
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
    sp.add_argument("--top-k", type=int, default=4)  # P5：与生产召回顶 K=4 对齐
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
    sp.add_argument("--sync-vocab", action="store_true",
                    help="自动把索引派生词表并入 toml 词表（自愈 categories 漏收）")
    sp.set_defaults(func=cmd_lint)

    # categories-sync
    sp = sub.add_parser("categories-sync",
                        help="从 kb-index 派生全部实际类别并写回 llmwiki.toml")
    _add_repo_arg(sp)
    sp.add_argument("--apply", action="store_true",
                    help="写入 toml（默认 dry-run 仅预览建议）")
    sp.set_defaults(func=cmd_categories)

    # eval
    sp = sub.add_parser("eval", help="评估召回质量（recall@k / MRR）")
    _add_repo_arg(sp)
    sp.add_argument("--queries", default=None,
                    help="评估集路径（默认: <repo>/eval_queries.json）")
    sp.add_argument("--demo", action="store_true",
                    help="显式演示模式：使用套件内置示例评测集（expected 指向套件 "
                         "testkb/demo 库，分数与你的库无关，仅套件自测/演示用）")
    sp.add_argument("--seed", action="store_true",
                    help="从索引采样自动生成首版评估集 eval_queries.json 后立即评估")
    sp.add_argument("--seed-limit", type=int, default=20,
                    help="--seed 采样上限（默认 20 条）")
    sp.add_argument("--top-k", type=int, default=None)
    sp.add_argument("--min-score", type=float, default=0.15)
    sp.add_argument("--out-dir", default=None)
    sp.add_argument("--tag", default=None)
    sp.add_argument("--retriever-desc", default=None)
    sp.add_argument("--prod-top-k", type=int, default=4)
    sp.add_argument("--chart", action="store_true",
                    help="额外生成自包含 SVG 评估图表")
    sp.set_defaults(func=cmd_eval)

    # serve
    sp = sub.add_parser("serve", help="启动 HTTP 桥接服务（需 wechat extras）")
    sp.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=cmd_serve)

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
