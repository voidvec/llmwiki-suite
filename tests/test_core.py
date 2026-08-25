"""核心纯函数单元测试：tokenize / frontmatter 解析 / 仓库定位 / 配置合并。

运行前提：已 `pip install -e .`（或 CI 中 `pip install .`）——直接 import 已安装的
llmwiki 包，保证「测试的就是发布的」，不注入仓库内 src 路径。
"""

from pathlib import Path

import pytest

from llmwiki import kb_core, recall  # noqa: E402


# ---- tokenize（中文滑 2-gram + 英文按词 + 停用字过滤） -----------------

class TestTokenize:
    def test_english_words(self):
        assert recall.tokenize("Hello World") == ["hello", "world"]

    def test_cjk_bigrams(self):
        toks = recall.tokenize("会议纪要")
        # "会议"、"议纪"、"要" 可能被停用字过滤，取决于 _CJK_STOP
        assert "会议" in toks
        assert "纪要" in toks

    def test_keeps_duplicates(self):
        toks = recall.tokenize("BM25 BM25")
        assert toks.count("bm25") == 2

    def test_empty(self):
        assert recall.tokenize("") == []
        assert recall.tokenize(None) == []


# ---- frontmatter 解析（扁平 YAML）----

class TestParseFm:
    def test_scalar(self):
        assert kb_core.parse_fm('title: "你好"') == {"title": "你好"}

    def test_scalar_bare_value_is_string(self):
        # 无括号单值按标量字符串解析（不是 list）
        assert kb_core.parse_fm("tags: demo") == {"tags": "demo"}

    def test_inline_list(self):
        assert kb_core.parse_fm("tags: [a, b]") == {"tags": ["a", "b"]}

    def test_block_list(self):
        fm = "tags:\n  - a\n  - b"
        assert kb_core.parse_fm(fm) == {"tags": ["a", "b"]}

    def test_no_fm(self):
        fm, body, raw = kb_core.split_fm("# just body")
        assert fm is None
        assert body == "# just body"


# ---- resolve_repo（D3 解析链）----

def _make_kb(tmp_path: Path) -> Path:
    """建最小知识库：README.md → 使 _looks_like_kb 判定通过。"""
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    return tmp_path


class TestResolveRepo:
    def test_explicit_repo(self, tmp_path):
        p = _make_kb(tmp_path)
        from llmwiki.config import resolve_repo
        assert resolve_repo(str(p)) == p

    def test_cwd_with_md(self, tmp_path, monkeypatch):
        p = _make_kb(tmp_path)
        monkeypatch.chdir(p)
        from llmwiki.config import resolve_repo
        assert resolve_repo(None) == p.resolve()

    def test_missing_repo_raises(self, tmp_path):
        from llmwiki.config import RepoNotFoundError, resolve_repo
        with pytest.raises(RepoNotFoundError):
            resolve_repo(str(tmp_path / "nope"))


# ---- load_config（toml 合并语义）----

class TestLoadConfig:
    def test_defaults_without_toml(self, tmp_path):
        p = _make_kb(tmp_path)
        from llmwiki.config import load_config
        cfg = load_config(p)
        assert cfg.index_file == "kb-index.json"
        assert "notes" in cfg.exclude_dirs or "templates" in cfg.exclude_dirs

    def test_custom_index_file(self, tmp_path):
        p = _make_kb(tmp_path)
        (p / "llmwiki.toml").write_text(
            '[repo]\nindex_file = "my-index.json"\n', encoding="utf-8")
        from llmwiki.config import load_config
        assert load_config(p).index_file == "my-index.json"

    def test_extra_exclude_extend(self, tmp_path):
        p = _make_kb(tmp_path)
        (p / "llmwiki.toml").write_text(
            '[ingest]\nextra_exclude = ["_private"]\n', encoding="utf-8")
        from llmwiki.config import load_config
        cfg = load_config(p)
        assert "_private" in cfg.exclude_dirs
