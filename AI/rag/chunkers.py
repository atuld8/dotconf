#/usr/bin/env python3
import re
from pathlib import Path

def normalize_ws(text: str) -> str:
    # Preserve code lines, normalize excessive blank lines
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def sliding_window_chunks(text: str, max_chars: int, overlap: int):
    text = normalize_ws(text)
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        yield text[start:end]
        if end == n: break
        start = end - overlap

def language_hint(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".py": "python", ".ts": "typescript", ".js": "javascript",
        ".go": "go", ".java": "java", ".cs": "csharp",
        ".rb": "ruby", ".rs": "rust", ".cpp": "cpp", ".c": "c"
    }.get(ext, "text")
