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
import urllib.request

from .recall import KbRetriever

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
                 llm_model=None, exclude_dirs=None, alias_groups=None):
        self.index_path = index_path
        # 索引缺失会让 KbRetriever 抛错；这里延迟到首次召回时暴露，便于排查。
        self.retriever = KbRetriever(index_path, exclude_dirs=exclude_dirs,
                                     alias_groups=alias_groups)
        self.llm_base_url = (llm_base_url or os.getenv(
            "LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.llm_api_key = llm_api_key if llm_api_key is not None \
            else os.getenv("LLM_API_KEY", "")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    # ---- LLM 调用（OpenAI 兼容 /chat/completions，标准库 urllib）----
    def call_llm(self, prompt):
        if not self.llm_api_key:
            return "（未配置 LLM_API_KEY，以下为检索片段预览）\n" + prompt[:600]
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

    # ---- 上下文拼装：章节级取数，省 token ----
    def build_context(self, hits, max_chapters=6):
        parts = []
        for h in hits[:max_chapters]:
            if h.matched_headings:
                chunk = self.retriever.fetch_chapter(h.path, h.matched_headings[0])
            else:
                chunk = self.retriever.read_doc(h.path)
            parts.append("【%s】\n%s" % (h.title, chunk[:1200]))
        return "\n\n".join(parts)

    # ---- 对外：召回 + 生成 ----
    def answer(self, query, top_k=5, categories=None, tags=None):
        hits = self.retriever.recall(query, top_k=top_k,
                                     categories=categories or None, tags=tags or None)
        if not hits:
            return "知识库中未找到相关信息。", []
        context = self.build_context(hits)
        prompt = PROMPT_TMPL.format(context=context, question=query)
        answer = self.call_llm(prompt)
        candidates = [{"path": h.path, "title": h.title, "score": h.score} for h in hits]
        return answer, candidates

    # ---- 对外：仅召回（调试用）----
    def recall(self, query, top_k=5, categories=None, tags=None):
        return self.retriever.recall(query, top_k=top_k,
                                     categories=categories or None, tags=tags or None)
