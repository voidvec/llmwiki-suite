"""端到端召回基线：在 CI 可复现的 fixtures 迷你库上跑 eval，断言不低于历史基线。

历史基线（套件 testkb 实测，docs/RELEASE.md §4）：recall@4 = 100%，MRR@4 = 1.0。
fixtures/kb 用与 testkb 相同的 4 篇评估目标笔记复刻，可被包内置 eval_queries.json
（8 条 query，expected 指向这 4 个文件）100% 命中，使其在 CI（无 testkb）可复现。

测试策略：
- 对 tests/fixtures/kb 原地跑 ingest + index + eval（迷你库，不改动内容）；
- check_recall_baseline.py 为独立回归入口（不经 pytest）；
- 任何改动（分词/打分/补位/索引）跌破基线 → 红。

运行前提：与 test_core.py 一致，基于**已安装的 llmwiki 包**（`pip install -e .` /
CI `pip install .`）——子进程调用 `sys.executable -m llmwiki.cli` 与脚本，均从
site-packages 取包，不注入仓库内 src（保证「测试的就是发布的」）。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_KB = REPO_ROOT / "tests" / "fixtures" / "kb"
RECALL_BASELINE = 1.0   # contextual_recall
MRR_BASELINE = 0.90     # MRR 允许小幅波动，防 flaky


@pytest.fixture(scope="module")
def eval_result(tmp_path_factory):
    """在 fixtures 迷你库上跑 ingest + index + eval，返回 JSON 报告 dict。

    使用临时副本，避免污染仓库内 fixtures/kb 的生成产物。
    """
    work = tmp_path_factory.mktemp("kb_copy")
    # fixtures/kb 里只保留源笔记与配置（排除可能产生的生成产物）
    shutil.copytree(FIXTURE_KB, work / "kb", ignore=shutil.ignore_patterns(
        "*report.json", "kb-index.json", "eval_reports", "__pycache__", ".cache"))
    kb = work / "kb"

    env = {**os.environ}  # 不注入 PYTHONPATH —— 用已安装的 llmwiki 包
    # 与 CI 相同：init 已在 fixtures 内（llmwiki.toml）——若缺则 init
    if not (kb / "llmwiki.toml").is_file():
        subprocess.run([sys.executable, "-m", "llmwiki.cli", "init", "--repo", str(kb)],
                       check=True, env=env, capture_output=True, text=True)
    subprocess.run([sys.executable, "-m", "llmwiki.cli", "ingest", "--repo", str(kb), "--apply"],
                   check=True, env=env, capture_output=True, text=True)
    subprocess.run([sys.executable, "-m", "llmwiki.cli", "index", "--repo", str(kb)],
                   check=True, env=env, capture_output=True, text=True)

    # 用独立脚本输出到临时目录（不经 pytest），并对失败断言
    out_dir = tmp_path_factory.mktemp("eval_out")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_recall_baseline.py"),
         "--repo", str(kb), "--out-dir", str(out_dir)],
        check=True, env=env, capture_output=True, text=True)
    json_path = out_dir / "recall-eval-baseline-check.json"
    assert json_path.is_file(), f"未产生 {json_path}"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data["summary"]


def test_eval_ran(eval_result):
    assert eval_result["count"] > 0
    assert eval_result["missed_queries"] == [], \
        f"存在未命中: {eval_result['missed_queries']}"


def test_recall_above_baseline(eval_result):
    got = eval_result["contextual_recall"]
    assert got >= RECALL_BASELINE, f"recall={got} 跌破基线 {RECALL_BASELINE}"


def test_mrr_above_baseline(eval_result):
    got = eval_result["mrr"]
    assert got >= MRR_BASELINE, f"MRR={got} 跌破基线 {MRR_BASELINE}"
