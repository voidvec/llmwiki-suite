"""核心纯函数单元测试：tokenize / frontmatter 解析 / 仓库定位 / 配置合并。

运行前提：已 `pip install -e .`（或 CI 中 `pip install .`）——直接 import 已安装的
llmwiki 包，保证「测试的就是发布的」，不注入仓库内 src 路径。
"""

from pathlib import Path

import json

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


# ---- categories 增量语义（0.1.3：默认之上追加，非整体替换）----

class TestCategoriesIncremental:
    def test_toml_allowed_merges_on_top_of_defaults(self, tmp_path):
        """[categories].allowed 为增量语义：默认词表 + toml 词表（去重保序）。"""
        p = _make_kb(tmp_path)
        (p / "llmwiki.toml").write_text(
            '[categories]\nallowed = ["kubernetes", "软件架构"]\n', encoding="utf-8")
        from llmwiki.config import load_config
        from llmwiki import defaults
        cfg = load_config(p)
        # 默认类别一个不丢（含「导航索引」产物类别）
        for c in defaults.DEFAULT_CATEGORIES:
            assert c in cfg.categories_allowed
        # toml 新增类别追加
        assert "kubernetes" in cfg.categories_allowed
        # 已在默认词表里的不重复添加
        assert cfg.categories_allowed.count("软件架构") == 1

    def test_replace_default_whitelist_mode(self, tmp_path):
        """replace_default=true 时为白名单（整体替换），默认类别全部丢弃。"""
        p = _make_kb(tmp_path)
        (p / "llmwiki.toml").write_text(
            '[categories]\nallowed = ["only-a"]\nreplace_default = true\n',
            encoding="utf-8")
        from llmwiki.config import load_config
        cfg = load_config(p)
        assert cfg.categories_allowed == ["only-a"]
        assert "导航索引" not in cfg.categories_allowed

    def test_categories_source_flag(self, tmp_path):
        """显式配置 toml 后 categories_source 记为 toml（load_vocab 据此前缀）。"""
        p = _make_kb(tmp_path)
        (p / "llmwiki.toml").write_text(
            '[categories]\nallowed = ["x"]\n', encoding="utf-8")
        from llmwiki.config import load_config
        assert load_config(p).categories_source == "toml"


# ---- derive_vocab_from_index（categories-sync 的数据源）----

class TestDeriveVocabFromIndex:
    def test_derive_from_index(self, tmp_path):
        p = _make_kb(tmp_path)
        (p / "kb-index.json").write_text(
            '{"category_index": {"工具指南": 1, "新分类A": 1}}', encoding="utf-8")
        from llmwiki.config import load_config, derive_vocab_from_index
        derived = derive_vocab_from_index(load_config(p))
        assert "新分类A" in derived
        assert "工具指南" in derived

    def test_missing_index_falls_back_to_defaults(self, tmp_path):
        p = _make_kb(tmp_path)
        from llmwiki.config import load_config, derive_vocab_from_index
        from llmwiki import defaults
        derived = derive_vocab_from_index(load_config(p))
        assert set(defaults.DEFAULT_CATEGORIES) <= derived


# ---- anchor_slug：序号前缀三态 + emoji 剥离 ----

class TestAnchorSlug:
    def test_pure_number_prefix(self):
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("1. 概述") == "概述"
        assert anchor_slug("3.1 配置") == "配置"
        assert anchor_slug("1、概述") == "概述"

    def test_cn_ordinal_number_after(self):
        """第 N 步：数字在后。"""
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("第 1 步：初始化") == "初始化"
        assert anchor_slug("第2章:安装") == "安装"

    def test_cn_prefix_number_before(self):
        """步骤 N：数字在前（此前漏处理的场景）。"""
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("步骤 1：生成 GitHub PAT") == "生成-github-pat"
        assert anchor_slug("步骤2：部署") == "部署"

    def test_en_ordinal(self):
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("Step 4 - 部署") == "部署"
        assert anchor_slug("Part IV: 进阶") == "进阶"

    def test_emoji_and_heading_mark_stripped(self):
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("1. 📖 概述") == "概述"
        assert anchor_slug("## 1. 📖 概述") == "概述"

    def test_slash_folds_into_single_token(self):
        """C/C++ 前后缀并入（cc），链接侧 #c-c 与该形态不匹配 => 修链接侧而非过度容错。"""
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("3.1 🧠 C/C++ 扩展配置") == "cc-扩展配置"

    def test_star_decor_stripped(self):
        """⭐(U+2B50) 属装饰前缀，应被剥离（真实库 claude-mcp 目录链接场景）。"""
        from llmwiki.kb_core import anchor_slug
        assert anchor_slug("## 2. ⭐ 必装 MCP 服务器") == "必装-mcp-服务器"

    def test_four_backtick_fence_does_not_swallow_headings(self):
        """4 反引号闭合的围栏（```text 内容 ````）不应吞掉其后的标题。

        真实库案例：claude-cli 集成指南用 ```` 闭合 ```text，旧正则 ```.*?``` 按 3
        个反引号配对导致多吞一整个代码块、丢失 6 个章节标题。"""
        from llmwiki.kb_core import extract_headings
        bt = "`"  # backtick
        md = (
            "# 标题一\n\n"
            f"{bt*3}text\n目录结构\n{bt*4}\n\n"      # 4 反引号闭合
            f"## 启动服务\n\n{bt*3}code\n{bt*3}\n"
        )
        heads = [h.strip() for h in extract_headings(md)]
        assert "启动服务" in heads
        assert len(heads) == 2


# ---- heading_exists：gh_slug 严格 + anchor_slug 宽松双段比对 ----

class TestHeadingExistsAnchorFallback:
    @staticmethod
    def _build(tmp_path: Path, heading: str) -> Path:
        (tmp_path / "README.md").write_text("# t\n", encoding="utf-8")
        (tmp_path / "notes").mkdir()
        md = ("---\ntitle: t\ntags: [a]\ndescription: d\ndifficulty: beginner\n---\n"
              + heading + "\n")
        (tmp_path / "notes" / "doc.md").write_text(md, encoding="utf-8")
        return tmp_path

    def test_strict_gh_slug_hit(self, tmp_path):
        from llmwiki.kb_core import build_link_index, heading_exists
        p = self._build(tmp_path, "# 概述")
        idx = build_link_index(str(p), {"templates"})
        assert heading_exists("notes/doc.md", "概述", idx)

    def test_loose_number_prefix(self, tmp_path):
        """链接 `#1-概述` ↔ 标题 `## 1. 📖 概述`。"""
        from llmwiki.kb_core import build_link_index, heading_exists
        p = self._build(tmp_path, "# 1. 📖 概述")
        idx = build_link_index(str(p), {"templates"})
        assert heading_exists("notes/doc.md", "1-概述", idx)
        assert heading_exists("notes/doc.md", "概述", idx)

    def test_loose_step_prefix(self, tmp_path):
        """链接 `#2-生成-github-pat` ↔ 标题 `步骤 1：生成 GitHub PAT`。"""
        from llmwiki.kb_core import build_link_index, heading_exists
        p = self._build(tmp_path, "# 步骤 1：生成 GitHub PAT")
        idx = build_link_index(str(p), {"templates"})
        assert heading_exists("notes/doc.md", "生成-github-pat", idx)

    def test_no_overmatching_short_anchor(self, tmp_path):
        """宽松比对是「短锚匹配长头」：`#安装` 不得命中 `## 安装脚本`（防过度容错）。"""
        from llmwiki.kb_core import build_link_index, heading_exists
        p = self._build(tmp_path, "# 安装脚本")
        idx = build_link_index(str(p), {"templates"})
        assert not heading_exists("notes/doc.md", "安装", idx)


# ---- eval：无评估集行为 + 索引缺失指引 + --demo / --seed ----

class TestEvalNoQueries:
    def test_missing_index_gives_guidance_exitcode3(self, tmp_path, capsys):
        """索引缺失时返回 3 并提示先 `llmwiki index`，不裸抛 FileNotFoundError。"""
        from llmwiki.config import load_config
        from llmwiki.eval_recall import run_eval_cmd
        p = _make_kb(tmp_path)  # 只有 README，无 kb-index.json
        cfg = load_config(p)
        rc = run_eval_cmd(cfg, queries_path=str(p / "eval_queries.json"))
        err = capsys.readouterr().err
        assert rc == 3
        assert "llmwiki index" in err

    def test_no_queries_exit2(self, tmp_path, capsys):
        """>=0.1.4：库根无 eval_queries.json → 不评估（杜绝回退内置假分数），退出码 2。"""
        import json
        from llmwiki.config import load_config
        from llmwiki.eval_recall import run_eval_cmd
        p = _make_kb(tmp_path)
        (p / "kb-index.json").write_text(json.dumps({"documents": []}),
                                         encoding="utf-8")
        cfg = load_config(p)
        with capsys.disabled():
            pass
        rc = run_eval_cmd(cfg, queries_path=str(p / "eval_queries.json"),
                          out_dir=str(tmp_path / "out"))
        err = capsys.readouterr().err
        assert rc == 2
        assert "未找到评估集" in err
        assert "eval --seed" in err
        assert not list((tmp_path / "out").glob("recall-eval-*.json")), \
            "无评估集时不应产出报告（不能留下假分数）"

    def test_demo_mode_runs_explicitly(self, tmp_path, monkeypatch, capsys):
        """--demo：显式要求用内置评测集，能正常产出且 meta 标记 queries_is_builtin。"""
        import json
        from llmwiki.config import load_config
        import llmwiki.eval_recall as er
        p = _make_kb(tmp_path)
        (p / "kb-index.json").write_text("{}", encoding="utf-8")
        cfg = load_config(p)

        class _FakeFreshness:
            stale = unknown = False
            changed = added = deleted = []
            def summary(self):
                return "fresh"

        class _FakeRetriever:
            freshness = _FakeFreshness()
            def recall(self, *a, **k):
                return []   # 不对真实召回敏感，本测试只验证 demo 标记/路径

        monkeypatch.setattr(er, "KbRetriever", lambda *a, **k: _FakeRetriever())
        out_dir = tmp_path / "out-demo"
        rc = er.run_eval_cmd(cfg, queries_path=str(p / "missing.json"),
                             out_dir=str(out_dir), demo=True)
        err = capsys.readouterr().err
        assert rc == 0
        assert "内置示例评测集" in err  # demo 模式提示
        snaps = list(out_dir.glob("recall-eval-*.json"))
        assert snaps, "demo 模式应产出报告"
        meta = json.loads(snaps[0].read_text(encoding="utf-8"))["meta"]
        assert meta["queries_is_builtin"] is True
        assert meta["queries_source"] == "demo-builtin"

    def test_seed_generates_and_runs(self, tmp_path, monkeypatch, capsys):
        """--seed：从索引采样写 eval_queries.json 并立即评估。"""
        import json
        from llmwiki.config import load_config
        import llmwiki.eval_recall as er
        p = _make_kb(tmp_path)
        # 造一份含 3 个普通文档 + 1 个 generated-index 的假索引
        (p / "kb-index.json").write_text(json.dumps({
            "documents": [
                {"path": "notes/aaa.md", "title": "AAA 主题",
                 "kind": "doc"},
                {"path": "notes/bbb.md", "title": "BBB 主题",
                 "kind": "doc"},
                {"path": "templates/tpl.md", "title": "模板",
                 "kind": "doc"},     # 应被过滤（templates/ 排除）
                {"path": "category-index.md", "title": "导航索引",
                 "kind": "generated-index"},  # 应被过滤
            ],
        }), encoding="utf-8")
        cfg = load_config(p)

        class _FakeFreshness:
            stale = unknown = False
            changed = added = deleted = []
            def summary(self):
                return "fresh"

        class _FakeRetriever:
            freshness = _FakeFreshness()
            def recall(self, *a, **k):
                return []

        monkeypatch.setattr(er, "KbRetriever", lambda *a, **k: _FakeRetriever())
        qp = p / "eval_queries.json"
        rc = er.run_eval_cmd(cfg, queries_path=str(qp), seed=True,
                             out_dir=str(tmp_path / "out"))
        capsys.readouterr()  # 丢弃标注输出
        assert rc == 0
        assert qp.is_file(), "--seed 应写出 eval_queries.json"
        seeded = json.loads(qp.read_text(encoding="utf-8"))
        paths = {q["expected"][0] for q in seeded["queries"]}
        assert "notes/aaa.md" in paths
        assert "notes/bbb.md" in paths
        # 过滤断言：templates 与 generated-index 都不进 seed
        assert "templates/tpl.md" not in paths
        assert "category-index.md" not in paths

    def test_seed_requires_index(self, tmp_path, capsys):
        """--seed 但无索引 → 退出码 3 并提示先 llmwiki index。"""
        from llmwiki.config import load_config
        from llmwiki.eval_recall import run_eval_cmd
        p = _make_kb(tmp_path)  # 无 kb-index.json
        cfg = load_config(p)
        rc = run_eval_cmd(cfg, seed=True, out_dir=str(tmp_path / "out"))
        err = capsys.readouterr().err
        assert rc == 3
        assert "llmwiki index" in err


# ---- _git_mv：目标已存在不覆盖、返回诊断（防静默失败回归） ---------------

class TestGitMv:
    def test_dest_exists_returns_not_ok(self, tmp_path):
        """目标文件已存在 → 返回 (False, 含「目标已存在」诊断)，且不覆盖原文件。"""
        import subprocess
        from llmwiki.ingest import _git_mv
        repo = tmp_path / "kb"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "07_config：xxx.md").write_text("a", encoding="utf-8")
        (repo / "07-config-xxx.md").write_text("b", encoding="utf-8")  # 既定目标已存在
        ok, reason = _git_mv(str(repo), "07_config：xxx.md", "07-config-xxx.md")
        assert ok is False
        assert "目标已存在" in reason
        # 不应覆盖目标内容
        assert (repo / "07-config-xxx.md").read_text(encoding="utf-8") == "b"
        # 源文件仍在（未被删除）
        assert (repo / "07_config：xxx.md").exists()

    def test_dst_missing_renames(self, tmp_path):
        """目标不存在 → fallback os.rename 成功，返回 True。"""
        import subprocess
        from llmwiki.ingest import _git_mv
        repo = tmp_path / "kb"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a_config.md").write_text("x", encoding="utf-8")
        ok, reason = _git_mv(str(repo), "a_config.md", "a-config.md")
        assert ok is True, reason
        assert (repo / "a-config.md").exists()
        assert not (repo / "a_config.md").exists()


class TestIlinkActivate:
    """iLink 激活：扫码 confirmed 后必须立即可见（connected=True），
    WebUI 轮询 /ilink/status 才能从「等待扫码」跳转到「已激活」。"""

    def test_confirmed_sets_connected(self):
        from unittest import mock
        from llmwiki.channels.ilink_adapter import IlinkAdapter
        a = IlinkAdapter(assistant=None)
        a.connected = False
        with mock.patch.object(a, "check_qrcode_status",
                               return_value=(True, "tok123", "https://x.cn")), \
             mock.patch.object(a, "_save_session"):
            ok, detail = a.activate(qrcode="abc", timeout=5, interval=0)
        assert ok is True
        assert detail == "activated"
        assert a.connected is True   # 根因修复点
        assert a.bot_token == "tok123"

    def test_not_confirmed_keeps_disconnected(self):
        from unittest import mock
        from llmwiki.channels.ilink_adapter import IlinkAdapter
        a = IlinkAdapter(assistant=None)
        a.connected = False
        with mock.patch.object(a, "check_qrcode_status", return_value=(False, "", "")), \
             mock.patch("time.sleep"):
            ok, detail = a.activate(qrcode="abc", timeout=0, interval=0)
        assert ok is False
        assert a.connected is False


class TestApiRoutes:
    """P2 路由收敛：/api/* 为正式机器接口，旧 /chat /recall 保留为兼容别名。
    校验路由注册（等价性由同一处理函数保证，见 wechat_bridge._chat/_recall）。"""

    def _bridge(self, monkeypatch, tmp_path):
        import os
        monkeypatch.setenv("KB_INDEX", str(tmp_path / "kb-index.json"))
        from llmwiki.channels import wechat_bridge as wb
        monkeypatch.setattr(wb, "BRIDGE_TOKEN", "")  # 隔离外部残留口令
        return wb

    def test_api_and_legacy_routes_registered(self, monkeypatch, tmp_path):
        wb = self._bridge(monkeypatch, tmp_path)
        routes = {(getattr(r, "path", None), ",".join(sorted(r.methods or [])))
                  for r in wb.app.routes}
        for expect in [("/api/chat", "POST"), ("/api/recall", "POST"),
                       ("/chat", "POST"), ("/recall", "POST")]:
            assert expect in routes, f"路由缺失: {expect}"
        # /api/* 与旧别名共用同一处理函数（结构化等价，非复制代码）
        assert wb.api_chat.__doc__ is None or "兼容" not in (wb.api_chat.__doc__ or "")
        assert wb.chat is not wb.api_chat  # 两个端点函数（同一 _chat 后端）

    def test_webui_js_uses_api_prefix(self, monkeypatch, tmp_path):
        wb = self._bridge(monkeypatch, tmp_path)
        js = wb._CHAT_WEBUI_HTML
        assert "'/api/chat'" in js, "网页问答页应调用正式接口 /api/chat"


class TestSseStream:
    """P3 SSE 流式：/api/chat 带 Accept: text/event-stream 时返回事件流，
    事件序 meta → candidates → delta* → done；默认无该头保持 JSON。"""

    @staticmethod
    def _bridge(monkeypatch, tmp_path):
        import os
        monkeypatch.setenv("KB_INDEX", str(tmp_path / "kb-index.json"))
        from llmwiki.channels import wechat_bridge as wb
        # 关键：BRIDGE_TOKEN 在模块 import 时求值并缓存；外部环境可能残留
        # LLM_WIKI_BRIDGE_TOKEN，导致守卫 401。测试显式置空模块变量
        # （比 delenv 可靠——模块可能已被其它测试类首次 import 缓存）。
        monkeypatch.setattr(wb, "BRIDGE_TOKEN", "")
        return wb

    @staticmethod
    def _mock(monkeypatch, tmp_path, answer_stream):
        wb = TestSseStream._bridge(monkeypatch, tmp_path)
        monkeypatch.setattr(wb, "_stale_warning", lambda: None)
        monkeypatch.setattr(wb.assistant, "answer_stream", answer_stream)
        return wb

    @staticmethod
    def _flatten(text: str) -> list[dict]:
        """把 SSE 文本解析为 [{"event": ..., "data": ...}, ...]。"""
        frames = []
        for frame in text.split("\n\n"):
            if not frame.strip():
                continue
            ev, data = "message", ""
            for line in frame.splitlines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    data += line[5:].strip()
            if not data:
                continue
            try:
                payload = json.loads(data)
            except Exception:
                payload = data
            frames.append({"event": ev, "data": payload})
        return frames

    def test_accept_header_triggers_sse(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient
        wb = self._mock(
            monkeypatch, tmp_path,
            lambda q, top_k=4, categories=None, tags=None: iter([
                {"candidates": [{"path": "a.md", "title": "A", "score": 2.5}]},
                "你",
                "好",
            ]))
        client = TestClient(wb.app)
        resp = client.post("/api/chat", headers={"Accept": "text/event-stream"},
                           json={"query": "hi"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        frames = self._flatten(resp.text)
        names = [f["event"] for f in frames]
        assert names[0] == "meta"          # 先行索引过期告警
        assert "candidates" in names       # 候选（引用卡）先于正文
        assert "delta" in names            # 正文增量（打字机）
        assert names[-1] == "done"         # 结束帧
        answer = "".join(f["data"].get("text", "") for f in frames
                         if f["event"] == "delta")
        assert answer == "你好"

    def test_stream_query_flag_also_sse(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient
        wb = self._mock(
            monkeypatch, tmp_path,
            lambda q, top_k=4, categories=None, tags=None: iter([
                {"candidates": []}, "x"]))
        client = TestClient(wb.app)
        resp = client.post("/api/chat?stream=1", json={"query": "hi"})
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert [f["event"] for f in self._flatten(resp.text)][0] == "meta"

    def test_legacy_chat_alias_supports_sse(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient
        wb = self._mock(
            monkeypatch, tmp_path,
            lambda q, top_k=4, categories=None, tags=None: iter([
                {"candidates": []}, "别名"]))
        client = TestClient(wb.app)
        resp = client.post("/chat", headers={"Accept": "text/event-stream"},
                           json={"query": "hi"})
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_no_accept_stays_json(self, monkeypatch, tmp_path):
        """不带 Accept 头 / ?stream → 保持 JSON（老客户端零影响）。"""
        from fastapi.testclient import TestClient
        wb = self._mock(
            monkeypatch, tmp_path,
            lambda q, top_k=4, categories=None, tags=None: iter([
                {"candidates": []}, "x"]))
        monkeypatch.setattr(wb.assistant, "answer",
                            lambda *a, **k: ("好", [{"path": "a.md",
                                                     "title": "A",
                                                     "score": 1.0}]))
        client = TestClient(wb.app)
        resp = client.post("/api/chat", json={"query": "hi"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "好"
        assert "text/event-stream" not in resp.headers.get("content-type", "")

    def test_not_found_frame(self, monkeypatch, tmp_path):
        """无命中：candidates 事件携带 not_found 文案，无 delta，done 落确。"""
        from fastapi.testclient import TestClient
        wb = self._mock(
            monkeypatch, tmp_path,
            lambda q, top_k=4, categories=None, tags=None: iter([
                {"candidates": [], "not_found": "知识库中未找到相关信息。"}]))
        client = TestClient(wb.app)
        resp = client.post("/api/chat", headers={"Accept": "text/event-stream"},
                           json={"query": "no-hit"})
        frames = self._flatten(resp.text)
        # meta + candidates(not_found) + done = 3 帧，无 delta
        assert [f["event"] for f in frames] == ["meta", "candidates", "done"]
        cand = frames[1]["data"]
        assert cand["not_found"] == "知识库中未找到相关信息。"

    def test_webui_clears_thinking_placeholder_on_first_delta(
            self, monkeypatch, tmp_path):
        """前端修复：收到第一条 delta 前必须先清空「思考中…」占位，
        否则正文会带占位前缀（用户报告的 bug）。"""
        wb = self._bridge(monkeypatch, tmp_path)
        js = wb._CHAT_WEBUI_HTML
        # 占位常量定义存在
        assert "THINKING" in js
        # delta 帧处理：先清占位（textContent=THINKING 判定）再渲染
        assert "pending.textContent===THINKING" in js
        assert "pending.textContent = " in js  # 清占位（三目：THINKING→''）
        assert "pending.innerHTML = mdText(acc)" in js

    def test_webui_has_markdown_paragraph_renderer(self, monkeypatch, tmp_path):
        """前端新增：mdText 轻量 Markdown 渲染（段落/加粗/列表/行内码），
        流式打字机与非流式 JSON 共用，保证段落排版一致。"""
        wb = self._bridge(monkeypatch, tmp_path)
        js = wb._CHAT_WEBUI_HTML
        assert "function mdText(s)" in js
        # 段落：按行切块渲染 <p>（JS 源码里是 HTML 串 '<p>'+…）
        assert "'<p>'" in js
        # 列表：全列表行块 → <ul>
        assert "allList" in js and "'<ul>'" in js
        # 加粗 → <strong>、行内码 → <code>
        assert "'<strong>$1</strong>'" in js
        assert "<code>" in js
        # delta 打字机期间用 mdText 渲染（段落即时成形）
        assert "pending.innerHTML = mdText(acc)" in js
        # 非流式 JSON 路径也用同一渲染器
        assert "pending.innerHTML = mdText(d.answer)" in js
