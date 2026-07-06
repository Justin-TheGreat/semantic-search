def chunk_text(text: str, size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping word windows.

    `size` and `overlap` are word counts (a cheap proxy for tokens that needs
    no tokenizer dependency). Small documents yield a single chunk.
    """
    words = text.split()
    if not words:
        return []
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks
