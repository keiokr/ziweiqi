from __future__ import annotations

from pathlib import Path


_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "cp936",
    "latin-1",
)


def read_text_guess(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    if not raw:
        return ""
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_lines_guess(path: str | Path) -> list[str]:
    return read_text_guess(path).splitlines()
