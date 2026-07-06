import pytest

from src.rag import prompts
from src.rag.chunking import chunk_text


def test_chunk_small_text_is_single_chunk():
    chunks = chunk_text("just a few words here", size=512, overlap=64)
    assert chunks == ["just a few words here"]


def test_chunk_windows_and_overlap():
    words = [f"w{i}" for i in range(300)]
    chunks = chunk_text(" ".join(words), size=100, overlap=20)
    # step = 80 -> windows start at 0, 80, 160, 240
    assert len(chunks) == 4
    first, second = chunks[0].split(), chunks[1].split()
    assert first[-20:] == second[:20]  # overlap preserved
    assert chunks[-1].split()[-1] == "w299"  # no words dropped


def test_chunk_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("a b c", size=10, overlap=10)


def test_prompt_registry_has_all_active_versions():
    for name, version in prompts.ACTIVE.items():
        assert version in prompts.PROMPTS[name], f"missing {name} {version}"


def test_prompt_render_fills_placeholders():
    text, version = prompts.render("generate", question="What is X?", context="[a001] X is Y")
    assert "What is X?" in text
    assert "[a001] X is Y" in text
    assert version == prompts.ACTIVE["generate"]
