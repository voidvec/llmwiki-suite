# -*- coding: utf-8 -*-
"""config.py — 仓库根解析 + 三层配置合并（pip 化后的核心解耦点）。

设计决策（docs/llmwiki-suite-design.md §5，2026-08-24 拍板）：
  D3 路径注入：`--repo` 参数 > CWD（向上找 .git）> CWD 含 markdown 即认 > 报错。
               不做环境变量（隐式状态是多库切换的坑）。
  D4 三层模型：套件默认（defaults.py） < 用户库 llmwiki.toml < 环境变量（仅密钥）。
               密钥只走环境变量，本套件不读取任何 .env 文件。

合并语义：
  - 逐 key 覆盖（标量项：index_file / llm.model / llm.base_url ...）
  - [ingest].extra_exclude：在默认排除集之上**追加**
  - [categories].allowed：**整体替换**默认词表（避免合并歧义；lint 对过短词表给 warning）
  - [aliases].groups：在默认别名组之上**追加**（组内变体打分时双向扩展，见 recall.expand_aliases）
  - [recall].min_score_per_term：标量覆盖（R1 每词阈值，0 = 关闭查询长度门槛）
  - [recall].link_gate：标量覆盖（P4 via_link 补位门槛系数，0 = 关闭）
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import defaults


class RepoNotFoundError(SystemExit):
    """resolve_repo 定位失败（SystemExit 子类，携带友好提示）。"""


def _find_repo_root_from(start: Path) -> Path | None:
    """从 start 向上找最近的 .git，作为仓库根。找不到返回 None。"""
    cur = start.resolve()
    while True:
        if (cur / ".git").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def _looks_like_kb(path: Path) -> bool:
    """目录里有 .md 文件即认为像一个知识库（非 git 环境的宽容判定）。"""
    try:
        for _p in path.rglob("*.md"):
            return True
    except OSError:
        pass
    return False


def resolve_repo(cli_repo: str | os.PathLike | None) -> Path:
    """仓库根解析链（D3）：--repo → CWD 向上找 .git → CWD 有 .md 即认 → 报错。"""
    if cli_repo:
        p = Path(cli_repo).expanduser().resolve()
        if not p.is_dir():
            raise RepoNotFoundError(f"--repo 指定的目录不存在: {p}")
        return p
    cwd = Path.cwd()
    root = _find_repo_root_from(cwd)
    if root is not None:
        return root
    if _looks_like_kb(cwd):
        return cwd.resolve()
    raise RepoNotFoundError(
        "未定位到知识库：请 cd 到库目录，或用 --repo 指定路径。\n"
        "  解析链: --repo 参数 > 当前目录向上找 .git > 当前目录含 .md 文件"
    )


@dataclass
class Config:
    """三层配置合并后的有效配置。"""

    repo: Path
    index_file: str = "kb-index.json"
    exclude_dirs: set = field(default_factory=lambda: set(defaults.DEFAULT_EXCLUDE_DIRS))
    categories_allowed: list = field(
        default_factory=lambda: list(defaults.DEFAULT_CATEGORIES))
    llm_base_url: str = defaults.DEFAULT_LLM_BASE_URL
    llm_model: str = defaults.DEFAULT_LLM_MODEL
    # 别名组（P1）：套件默认 + toml 追加（extend 语义）
    alias_groups: list = field(
        default_factory=lambda: [list(g) for g in defaults.DEFAULT_ALIAS_GROUPS])
    # R1 每词阈值（查询长度感知门槛，见 recall.py 模块 docstring）
    min_score_per_term: float = defaults.DEFAULT_MIN_SCORE_PER_TERM
    # P4 via_link 补位门槛（补位文档自身分须达生效门槛 × 此系数；0 = 关闭）
    link_gate: float = defaults.DEFAULT_LINK_GATE
    # 词表来源（lint 用：来自 toml 显式配置 / 索引派生 / 套件默认）
    categories_source: str = "default"  # "toml" | "index" | "default"

    @property
    def index_path(self) -> Path:
        return self.repo / self.index_file


def load_config(repo: Path) -> Config:
    """读 repo/llmwiki.toml 并与套件默认合并（toml 缺失 → 纯默认，零摩擦）。"""
    cfg = Config(repo=repo)
    toml_path = repo / "llmwiki.toml"
    data = {}
    if toml_path.is_file():
        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"[config] 警告: llmwiki.toml 解析失败（{e}），使用默认配置",
                  file=sys.stderr)

    if not data:
        return cfg

    # [repo]
    cfg.index_file = data.get("repo", {}).get("index_file", cfg.index_file)

    # [ingest].extra_exclude：追加语义
    extra = data.get("ingest", {}).get("extra_exclude", [])
    if isinstance(extra, str):
        extra = [extra]
    cfg.exclude_dirs |= {e.strip("/") for e in extra if e.strip("/")}

    # [categories].allowed：增量语义（在套件默认词表之上追加，而非整体替换）。
    # 理由：默认词表是「通用、起点」，用户库按各自主题扩展 —— 整体替换会让
    # 写少类别就「丢默认类别」，造成大类库的误报（2026-08-26 实战教训）。
    # 若确实想整体替换（白名单模式），用 [categories].replace_default = true。
    allowed = data.get("categories", {}).get("allowed")
    if isinstance(allowed, list) and allowed:
        if data.get("categories", {}).get("replace_default", False):
            cfg.categories_allowed = [str(c) for c in allowed]
        else:
            # 增量：默认词表 + toml 词表（保持顺序、去重）
            merged = list(defaults.DEFAULT_CATEGORIES)
            for c in allowed:
                c = str(c).strip()
                if c and c not in merged:
                    merged.append(c)
            cfg.categories_allowed = merged
        cfg.categories_source = "toml"

    # [aliases].groups：追加语义（在套件默认别名组之上扩展自定义组）
    groups = data.get("aliases", {}).get("groups", [])
    if isinstance(groups, list):
        for g in groups:
            if isinstance(g, list) and len(g) >= 2 \
                    and all(isinstance(v, str) and v.strip() for v in g):
                cfg.alias_groups.append([v.strip() for v in g])

    # [recall].min_score_per_term：R1 每词阈值（标量覆盖；0 = 关闭查询长度门槛）
    mspt = data.get("recall", {}).get("min_score_per_term")
    if isinstance(mspt, (int, float)) and not isinstance(mspt, bool):
        cfg.min_score_per_term = float(mspt)

    # [recall].link_gate：P4 补位门槛系数（0 = 关闭，恢复旧补位行为）
    lg = data.get("recall", {}).get("link_gate")
    if isinstance(lg, (int, float)) and not isinstance(lg, bool):
        cfg.link_gate = float(lg)

    # [llm]：非密钥项（LLM_WIKI_API_KEY 只走环境变量）
    llm = data.get("llm", {})
    cfg.llm_base_url = llm.get("base_url", cfg.llm_base_url)
    cfg.llm_model = llm.get("model", cfg.llm_model)

    return cfg


def load_vocab(cfg: Config) -> set | None:
    """受控词表解析（lint / ingest 共用）。

    优先级：llmwiki.toml 显式配置 > kb-index.json 派生（向后兼容旧行为）> 套件默认。
    返回 None 表示「无词表可校验」（调用方据此跳过词表检查）。
    """
    if cfg.categories_source == "toml":
        return set(cfg.categories_allowed)
    # 索引派生（兼容无 toml 的既有库：词表 = 现存文档实际使用的分类）
    try:
        import json
        with open(cfg.index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        derived = set(idx.get("category_index", {}).keys())
        if derived:
            return derived
    except Exception:
        pass
    return set(cfg.categories_allowed)


def derive_vocab_from_index(cfg: Config) -> set:
    """从 kb-index.json 的 category_index 派生全部**实际使用中**的类别。

    供 `llmwiki categories-sync` 与 lint 的增量自愈用：类别 = 默认类别 ∪ 现存文档类别。
    索引缺失时返回默认词表。
    """
    try:
        import json
        with open(cfg.index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        derived = set(idx.get("category_index", {}).keys())
    except Exception:
        derived = set()
    return derived | set(cfg.categories_allowed)
