"""Thin client around the vLLM OpenAI-compatible endpoint, with token metrics."""
import re

from langchain_openai import ChatOpenAI

from src.config import settings
from src.metrics import completion_tokens, prompt_tokens
from src.rag.retriever import RetrievedDoc

CITATION_RE = re.compile(r"\[([a-zA-Z]\d+)\]")


def get_llm(max_tokens: int | None = None, temperature: float | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.vllm_base_url,
        api_key="not-needed",  # vLLM accepts any non-empty key
        model=settings.vllm_model,
        temperature=settings.llm_temperature if temperature is None else temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        timeout=120,
    )


def record_usage(msg) -> None:
    usage = getattr(msg, "usage_metadata", None) or {}
    prompt_tokens.inc(usage.get("input_tokens", 0))
    completion_tokens.inc(usage.get("output_tokens", 0))


def llm_complete(prompt: str, max_tokens: int | None = None) -> str:
    """Single blocking completion; returns the text content."""
    msg = get_llm(max_tokens=max_tokens).invoke(prompt)
    record_usage(msg)
    return msg.content if isinstance(msg.content, str) else str(msg.content)


def format_context(docs: list[RetrievedDoc]) -> str:
    return "\n\n".join(f"[{d.article_id}] {d.title}: {d.text}" for d in docs)


def extract_citations(answer: str, docs: list[RetrievedDoc]) -> list[str]:
    """Citations the model wrote, filtered to ids that were actually in context."""
    valid = {d.article_id for d in docs}
    cited = [c for c in CITATION_RE.findall(answer) if c in valid]
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    return [c for c in cited if not (c in seen or seen.add(c))]
