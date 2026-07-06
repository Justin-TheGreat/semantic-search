"""Agentic RAG orchestration: retrieve -> grade -> generate -> verify.

The compiled LangGraph (`RAGAgent.graph`) is the canonical state machine and is
what `answer()` runs for eval and non-streaming callers. `astream_chat()` walks
the same node functions but streams generation tokens live for the /chat SSE
endpoint (it grades and retries retrieval, then generates once and attaches a
verified/low-confidence flag instead of re-generating mid-stream).
"""
import time
from typing import AsyncIterator, TypedDict

from langgraph.graph import END, StateGraph

from src.config import settings
from src.metrics import completion_tokens, node_latency
from src.rag import prompts
from src.rag.generator import (
    extract_citations,
    format_context,
    get_llm,
    llm_complete,
)
from src.rag.reranker import Reranker
from src.rag.retriever import HybridRetriever

REFUSAL = "I don't know based on the indexed articles — no relevant context was retrieved."


def _observe(fn):
    """Wrap a node with Langfuse tracing when enabled + installed; no-op otherwise."""
    if settings.langfuse_enabled:
        try:
            from langfuse.decorators import observe

            return observe()(fn)
        except Exception:
            return fn
    return fn


class RAGState(TypedDict, total=False):
    question: str  # current (possibly rewritten) query
    original_question: str
    docs: list  # list[RetrievedDoc]
    grade: str  # "yes" | "no"
    answer: str
    citations: list
    attempts: int  # retrieval rewrites so far
    generation_attempts: int
    verified: bool
    prompt_version: str


class RAGAgent:
    def __init__(self, retriever: HybridRetriever, reranker: Reranker):
        self.retriever = retriever
        self.reranker = reranker
        self.graph = self._build_graph()

    # ---------- nodes ----------

    def retrieve(self, state: RAGState) -> RAGState:
        docs = self.retriever.retrieve(state["question"])
        if settings.enable_hybrid:
            docs = self.reranker.rerank(state["question"], docs)
        state["docs"] = docs
        return state

    def grade_docs(self, state: RAGState) -> RAGState:
        """Corrective RAG: an LLM judges whether retrieval is good enough to answer from."""
        if not state["docs"]:
            state["grade"] = "no"
            return state
        prompt, _ = prompts.render(
            "grade",
            question=state["question"],
            context=format_context(state["docs"][:4]),
        )
        try:
            reply = llm_complete(prompt, max_tokens=8)
            state["grade"] = "yes" if "yes" in reply.lower() else "no"
        except Exception:
            # Grader LLM unreachable: fail open so retrieval-only paths still work.
            state["grade"] = "yes"
        return state

    def rewrite_query(self, state: RAGState) -> RAGState:
        prompt, _ = prompts.render("rewrite", question=state["question"])
        try:
            new_q = llm_complete(prompt, max_tokens=64).strip().strip('"')
        except Exception:
            new_q = ""
        state["question"] = new_q or state["question"]
        state["attempts"] = state.get("attempts", 0) + 1
        return state

    def generate(self, state: RAGState) -> RAGState:
        if not state["docs"]:
            # Guardrail: never generate without graded context.
            state["answer"] = REFUSAL
            state["citations"] = []
            state["prompt_version"] = prompts.ACTIVE["generate"]
            return state
        prompt, version = prompts.render(
            "generate",
            question=state["question"],
            context=format_context(state["docs"]),
        )
        answer = llm_complete(prompt)
        state["answer"] = answer
        state["citations"] = extract_citations(answer, state["docs"]) or self._fallback_citations(
            state
        )
        state["prompt_version"] = version
        return state

    def verify(self, state: RAGState) -> RAGState:
        """Hallucination guard: check the answer against its sources before returning."""
        state["generation_attempts"] = state.get("generation_attempts", 0) + 1
        if not state["docs"]:
            state["verified"] = False
            return state
        prompt, _ = prompts.render(
            "verify",
            context=format_context(state["docs"]),
            answer=state["answer"],
        )
        try:
            reply = llm_complete(prompt, max_tokens=8)
            state["verified"] = "yes" in reply.lower()
        except Exception:
            state["verified"] = False
        return state

    @staticmethod
    def _fallback_citations(state: RAGState) -> list:
        """Small models sometimes skip [id] markers; attribute the top sources used."""
        seen: set[str] = set()
        out = []
        for d in state["docs"][:3]:
            if d.article_id not in seen:
                seen.add(d.article_id)
                out.append(d.article_id)
        return out

    # ---------- routing ----------

    def route_after_grade(self, state: RAGState) -> str:
        if state["grade"] == "yes" or state.get("attempts", 0) >= settings.max_agent_attempts:
            return "generate"
        return "rewrite"

    def route_after_verify(self, state: RAGState) -> str:
        if (
            state.get("verified")
            or not state["docs"]
            or state.get("generation_attempts", 0) >= settings.max_agent_attempts
        ):
            return "done"
        return "retry"

    # ---------- graph ----------

    def _timed(self, name: str, fn):
        fn = _observe(fn)

        def wrapper(state: RAGState) -> RAGState:
            start = time.time()
            try:
                return fn(state)
            finally:
                node_latency.labels(node=name).observe(time.time() - start)

        wrapper.__name__ = name
        return wrapper

    def _build_graph(self):
        builder = StateGraph(RAGState)
        builder.add_node("retrieve", self._timed("retrieve", self.retrieve))
        builder.add_node("grade_docs", self._timed("grade_docs", self.grade_docs))
        builder.add_node("rewrite_query", self._timed("rewrite_query", self.rewrite_query))
        builder.add_node("generate", self._timed("generate", self.generate))
        builder.add_node("verify", self._timed("verify", self.verify))
        builder.set_entry_point("retrieve")
        builder.add_edge("retrieve", "grade_docs")
        builder.add_conditional_edges(
            "grade_docs",
            self.route_after_grade,
            {"generate": "generate", "rewrite": "rewrite_query"},
        )
        builder.add_edge("rewrite_query", "retrieve")
        builder.add_edge("generate", "verify")
        builder.add_conditional_edges(
            "verify",
            self.route_after_verify,
            {"done": END, "retry": "generate"},
        )
        return builder.compile()

    # ---------- entry points ----------

    def answer(self, question: str) -> dict:
        """Blocking full-graph run (used by the eval harness)."""
        state: RAGState = {
            "question": question,
            "original_question": question,
            "docs": [],
            "attempts": 0,
            "generation_attempts": 0,
        }
        final = self.graph.invoke(state)
        return {
            "answer": final.get("answer", ""),
            "citations": final.get("citations", []),
            "verified": bool(final.get("verified")),
            "prompt_version": final.get("prompt_version", prompts.ACTIVE["generate"]),
        }

    async def astream_chat(self, question: str) -> AsyncIterator[dict]:
        """Streaming run for /chat: node events, live tokens, then a final summary."""
        from starlette.concurrency import run_in_threadpool

        state: RAGState = {
            "question": question,
            "original_question": question,
            "docs": [],
            "attempts": 0,
            "generation_attempts": 0,
        }
        while True:
            yield {"event": "node", "node": "retrieve"}
            state = await run_in_threadpool(self._timed("retrieve", self.retrieve), state)
            yield {"event": "node", "node": "grade_docs"}
            state = await run_in_threadpool(self._timed("grade_docs", self.grade_docs), state)
            if self.route_after_grade(state) == "generate":
                break
            yield {"event": "node", "node": "rewrite_query"}
            state = await run_in_threadpool(
                self._timed("rewrite_query", self.rewrite_query), state
            )

        yield {"event": "node", "node": "generate"}
        if not state["docs"]:
            state["answer"] = REFUSAL
            state["citations"] = []
            state["prompt_version"] = prompts.ACTIVE["generate"]
            state["verified"] = False
            yield {"token": REFUSAL}
        else:
            prompt, version = prompts.render(
                "generate",
                question=state["question"],
                context=format_context(state["docs"]),
            )
            start = time.time()
            parts: list[str] = []
            async for chunk in get_llm().astream(prompt):
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    parts.append(text)
                    yield {"token": text}
            node_latency.labels(node="generate").observe(time.time() - start)
            answer = "".join(parts)
            # Streaming responses don't always carry usage; approximate by words.
            completion_tokens.inc(len(answer.split()))
            state["answer"] = answer
            state["citations"] = extract_citations(answer, state["docs"]) or (
                self._fallback_citations(state)
            )
            state["prompt_version"] = version
            yield {"event": "node", "node": "verify"}
            state = await run_in_threadpool(self._timed("verify", self.verify), state)

        yield {
            "event": "done",
            "answer": state.get("answer", ""),
            "citations": state.get("citations", []),
            "verified": bool(state.get("verified")),
            "prompt_version": state.get("prompt_version", ""),
            "question": state["question"],
        }
