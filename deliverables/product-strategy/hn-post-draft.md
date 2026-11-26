# Show HN — llmwiki-suite · main post draft (D6)

> **状态标注（截至 2026-11-26）· [未兑现]**
> 本文为 2026-09-01 的 D6 HN 主帖英文草稿（服务于当时拟定的 W4 发布），仅记录当时的计划 / 决策意图，**不代表仓库现状**；正文一律按历史快照阅读，不作为现状依据。
> 当前版本为 `0.1.7`（2026-11-26 发布）；原定 W4（09-22）的 `v0.1.7` 已延期落地，而 HN 发布、W37–W44 周报、`docs/cr/`、发布响应台账、pivot / 止损决策、范围冻结签署，仓库内仍无记录。
> 仓库内无记录 ≠ 确定未执行（外部动作可能发生在仓库外）；观测快照覆盖 2026-09-01 ~ 2026-11-25（缺 09-02），此后无新快照。全仓权威口径见 `docs/project-records/00-canonical-baseline.md`。
> 发布前 Checklist 中的 `llmwiki query` 演示截图 / GIF、终稿人审、标题终选仓库内无记录；本文 `title < 80 chars` / `Tuesday evening PT` 与 `hn-launch-timing.md` 口径不同。


> Working draft — W2 人工评审用。发布前「独占审一轮」：正文不改不改，只补素材。
> Target: W4 硬发布（周二 PT 时间锚点前）· title < 80 chars · body ≤ 350 words.

---

## Title A/B (6 candidates, 3 pairs)

**Pair 1 — mechanism-framed**
- A1: `Show HN: llmwiki — compile your Markdown notes into a searchable, decaying-proof knowledge base`  (78 chars ✓)
- A2: `Show HN: llmwiki — answer questions over Markdown notes that never go stale`  (69 chars ✓)

**Pair 2 — pain-framed**
- B1: `Show HN: Stop re-embedding every night — compile your Markdown notes once and query instantly`  (76 chars ✓)
- B2: `Show HN: A local knowledge base for developers who are tired of nightly re-embedding`  (72 chars ✓)

**Pair 3 — Karpathy-framed (community hook)**
- C1: `Show HN: llmwiki-suite — LLM-compiled personal wiki (Karpathy's idea, pip-installable, zero deps)`  (77 chars ✓)
- C2: `Show HN: Karpathy's LLM-wiki idea, as a real tool — compile notes to BM25+link index, no vector DB`  (78 chars ✓)

### Recommendation: **Pair 1-A** (or B1 as fallback)
- **A1** nails the *unique* angle ("compile" not "RAG"), promises the searchable outcome, fits 80-char limit, and sets up the "never decays" hook in the body. It's concrete, mechanism-first, honest — best for HN's anti-hype culture.
- **B1** is the strongest pain-driven alternative if the community reads "RAG fatigue"; keep it as B-tier.
- Avoid C-variants as *main* title: leans on "Karpathy" which can feel name-drop-y; keep the Karpathy connection in the body instead.

---

## Body draft (English, Show HN)

**Show HN: llmwiki — compile your Markdown notes into a searchable, self-maintaining knowledge base**

I got tired of two things about local RAG: the search pipeline re-embeds every question, nightly re-embed jobs to keep the index fresh, and the answers can't explain which note they came from. So I built llmwiki — a **compile-first** personal wiki. Inspired by Karpathy's LLM-wiki idea, it flips the work: at *import time* it builds a BM25 + wikilink-graph index over your notes and normalizes frontmatter; at *query time* retrieval is pointer arithmetic, not magic.

**Three commands to get going:**

```
pip install llmwiki-suite
llmwiki init --repo ~/notes        # adopts an existing Markdown vault
llmwiki ingest --apply             # compile: frontmatter + index + link lint
llmwiki query "what did I decide about X?"   # answer + cites the note
```

Runs entirely offline, **zero Python dependencies**, plain Markdown + a JSON index — nothing to break, reversible anytime. The index follows your notes, so it **never quietly drifts** from what you actually wrote.

**Why it's better than dust in a folder:** every note is normalized, linked, linted and *auditable* — the health score (0-100, D1) tells you at a glance when the vault is getting stale.

**Numbers from a real run (testkb, 8 queries):** recall@4 = 1.0, MRR@4 = 1.0, in under 1s, on **pure BM25 + graph, no embeddings, no vector DB**. Gate in CI keeps it honest (≥0.95/≥0.90).

Zero deps, MIT, Python ≥ 3.11. Docs: README, API, architecture. Channels: CLI now; iLink/WeCom/Feishu/Telegram for the phone crowd.

Love to hear your "huh, I wish that existed" cases — and your honest "this would fail for me" ones. Roast it.

---

## Pre-publish checklist (owner to fill)

- [ ] Screenshot / GIF: `llmwiki query` demo on a real vault (small animated gif, <2 MB)
- [ ] Final title pick (A1 preferred) + fallback keep
- [ ] Links to insert: repo (github.com/voidvec/llmwiki-suite), PyPI page, health-score doc
- [ ] Publishing account: voidvec HN account (verify karma/age for Show HN eligibility)
- [ ] Time: Tuesday evening PT (matches D8 anchor) + 48h reply-window calendar block
- [ ] Slot in comparison post (`llmwiki-vs-rag-comparison.md`) in the opening comment (not the OP)

---

*Draft v1 — 2026-09-01 · refs: testkb/eval_reports/recall-eval-baseline-2026-08-31.json · Roadmap W4.*