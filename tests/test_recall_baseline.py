"""端到端召回基线：在套件自带 testkb 上跑 eval，断言不低于历史基线。

历史基线（testkb 实测，docs/RELEASE.md §4）：
    recall@4 (contextual_recall) = 1.0
    MRR@4                        = 1.0

测试策略：
- 直接用 testkb（已 init + 建索引），不改动其内容；
- eval 输出写到临时 out_dir，不污染 testkb/eval_reports；
- 任何改动（分词/打分/补位/索引）跌破基线 → CI 红。
"""

import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTKB = REPO_ROOT / "testkb"

# 历史基线（testkb 实测）
RECALL_BASELINE = 1.0   # contextual_recall
MRR_BASELINE = 0.90     # MRR 允许小幅波动，防 flaky，但 testkb 实为 1.0


@pytest.fixture(scope="module")
def eval_result(tmp_path_factory):
    """在 testkb 上跑一次 eval，返回 JSON 报告 dict（输出到临时目录）。"""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from llmwiki.config import load_config
    from llmwiki.eval_recall import run_eval_cmd

    cfg = load_config(TESTKB)
    out_dir = tmp_path_factory.mktemp("eval_out")
    run_eval_cmd(cfg, out_dir=str(out_dir), tag="baseline-test")

    json_path = out_dir / f"recall-eval-baseline-test.json"
    assert json_path.is_file(), f"eval 未产生 {json_path}"
    return json.loads(json_path.read_text(encoding="utf-8"))


def test_report_shape(eval_result):
    s = eval_result["summary"]
    assert s["count"] > 0
    assert s["missed_queries"] == [], f"存在未命中: {s['missed_queries']}"


def test_recall_above_baseline(eval_result):
    s = eval_result["summary"]
    got = s["contextual_recall"]
    assert got >= RECALL_BASELINE, \
        f"contextual_recall={got} 跌破基线 {RECALL_BASELINE}"


def test_mrr_above_baseline(eval_result):
    s = eval_result["summary"]
    got = s["mrr"]
    assert got >= MRR_BASELINE, f"MRR={got} 跌破基线 {MRR_BASELINE}"