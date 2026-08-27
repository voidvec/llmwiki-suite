# -*- coding: utf-8 -*-
"""
assistant.py — LlmWiki 应答编排层（Answer Orchestration）

把「召回 -> 拼 prompt -> 调 LLM -> 附来源」这一业务闭环从传输层（微信/HTTP/CLI）
中抽离出来，成为与传输方式无关的纯逻辑层。各 ChannelAdapter 都调用它来生成回答。

依赖：recall（KbRetriever，零三方依赖）+ 标准库 urllib 调 OpenAI 兼容端点。
LLM 未配置时降级返回检索片段预览，保证离线可联调。

套件化改造（相对个人库 scripts/kb_assistant.py）：
  - index_path 必须显式给出（cli 层从 config 解析注入）；LLM 非密钥默认值来自 cfg。
"""
import json
import os

from . import _env
import urllib.request

# 注意：recall 在 _ensure_retriever 内延迟导入（惰性构造，避免 serve 初始化即读索引）

PROMPT_TMPL = """你是知识库助手。仅根据以下检索到的文档片段回答用户问题。
若片段足以回答，请直接、准确地回答并引用片段来源标题；
若片段不足以回答，请说明"根据检索到的 N 篇文档，未涵盖该问题的完整答案"，
并列出相关文档标题（相关文档可能包括：<标题列表>），建议换个关键词或补充查询。
不要编造，不要声称"知识库中未找到"——存在候选但内容不足时如实说明覆盖缺口。

# 检索片段
{context}

# 用户问题
{question}

# 回答（中文，简洁，引用片段来源标题）"""


class KbAssistant:
    """知识库问答助手：封装检索与生成。通道层（WeCom/iLink）只管消息收发，
    业务语义全部在这里。"""

    def __init__(self, index_path, llm_base_url=None, llm_api_key=None,
                 llm_model=None, exclude_dirs=None, alias_groups=None,
                 min_score_per_term=None, link_gate=None):
        self.index_path = index_path
        self._exclude_dirs = exclude_dirs
        self._alias_groups = alias_groups
        self._min_score_per_term = min_score_per_term
        self._link_gate = link_gate
        # 惰性构造 KbRetriever：serve / CLI 初始化不因索引缺失崩溃；
        # 首次召回时才读索引并暴露可读错误（见 _ensure_retriever）。
        self._retriever = None
        self.llm_base_url = (llm_base_url or _env.getenv(
            "BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.llm_api_key = llm_api_key if llm_api_key is not None \
            else _env.getenv("API_KEY", "")
        self.llm_model = llm_model or _env.getenv("MODEL", "gpt-4o-mini")

    @property
    def retriever(self):
        """惰性初始化 KbRetriever（首次访问时构造）。"""
        if self._retriever is None:
            from .recall import KbRetriever
            self._retriever = KbRetriever(
                self.index_path,
                exclude_dirs=self._exclude_dirs,
                alias_groups=self._alias_groups,
                min_score_per_term=self._min_score_per_term,
                link_gate=self._link_gate,
            )
        return self._retriever

    @retriever.setter
    def retriever(self, r):
        self._retriever = r

    # ---- LLM 调用（OpenAI 兼容 /chat/completions，标准库 urllib）----
    def call_llm(self, prompt):
        if not self.llm_api_key:
            return "（未配置 LLM_WIKI_API_KEY，以下为检索片段预览）\n" + prompt[:600]
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            self.llm_base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.llm_api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            # LLM 端点不可达/鉴权失败时降级为片段预览（与未配置 key 同待遇，CLI 不崩溃）
            return ("（LLM 调用失败: %s。以下为检索片段预览）\n" % e) + prompt[:600]
        return data["choices"][0]["message"]["content"]

    # ---- 流式 LLM 调用（P3：SSE 打字机；不配置 key / 端点异常 → 一次 yield 降级文案）----
    def call_llm_stream(self, prompt):
        """逐 chunk 生成回答文本（生成器）。与 call_llm 同请求语义，仅 stream=True。
        任何异常（未配置 key、网络、非流式响应兜底）都收敛为一次 yield 的完整文案，
        保证调用方（SSE 生成器）永远能消费完整个生成器而不抛错。"""
        if not self.llm_api_key:
            yield "（未配置 LLM_WIKI_API_KEY，以下为检索片段预览）\n" + prompt[:600]
            return
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "stream": True,
        }
        req = urllib.request.Request(
            self.llm_base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.llm_api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        piece = json.loads(data)
                    except ValueError:
                        continue
                    delta = (piece.get("choices") or [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
        except Exception as e:
            # 与 call_llm 同待遇：端点不可达/鉴权失败降级为片段预览（一次性 yield）
            yield ("（LLM 调用失败: %s。以下为检索片段预览）\n" % e) + prompt[:600]

    # ---- 上下文拼装：章节级取数，省 token ----
    def build_context(self, hits, max_chapters=4):
        parts = []
        for h in hits[:max_chapters]:
            if h.matched_headings:
                chunk = self.retriever.fetch_chapter(h.path, h.matched_headings[0])
            else:
                chunk = self.retriever.read_doc(h.path)
            parts.append("【%s】\n%s" % (h.title, chunk[:1200]))
        return "\n\n".join(parts)

    # ---- 对外：召回 + 生成 ----
    def answer(self, query, top_k=4, categories=None, tags=None):
        hits = self.retriever.recall(query, top_k=top_k,
            categories=categories or None, tags=tags or None)
        if not hits:
            return "知识库中未找到相关信息。", []
        context = self.build_context(hits)
        prompt = PROMPT_TMPL.format(context=context, question=query)
        answer = self.call_llm(prompt)
        candidates = [{"path": h.path, "title": h.title, "score": h.score} for h in hits]
        return answer, candidates

    # ---- 对外：流式召回 + 生成（P3：SSE 打字机）----
    def answer_stream(self, query, top_k=4, categories=None, tags=None):
        """流式应答生成器：先 yield 候选（dict），再逐块 yield 回答文本（str）。

        事件序列约定（与 wechat_bridge 的 SSE 帧对齐）：
            {"candidates": [...], "index_stale": ...}   # 首个产出：候选 + 过期告警
            "..."                                       # 若干 str：回答增量
        无命中时仅 yield 一个 {"candidates": [], "not_found": "..."} 帧，不产出文本。
        降级语义与 answer() 完全一致：LLM 不可用时文本一次到位（含预览前缀）。
        """
        hits = self.retriever.recall(query, top_k=top_k,
            categories=categories or None, tags=tags or None)
        candidates = [{"path": h.path, "title": h.title, "score": h.score}
                      for h in hits]
        if not hits:
            yield {"candidates": [], "not_found": "知识库中未找到相关信息。"}
            return
        context = self.build_context(hits)
        prompt = PROMPT_TMPL.format(context=context, question=query)
        yield {"candidates": candidates}
        for chunk in self.call_llm_stream(prompt):
            yield chunk

    # ---- 对外：仅召回（调试用）----
    def recall(self, query, top_k=4, categories=None, tags=None):
        return self.retriever.recall(query, top_k=top_k,
                                     categories=categories or None, tags=tags or None)
