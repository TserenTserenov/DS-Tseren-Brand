#!/usr/bin/env python3
"""Cut an automatic meeting transcript into numbered fragments for speaker labelling (WP-619 F4).

Style 1.1 «Разговор с командой» needs the author's own speech, but the IT meeting transcripts
(MimEcoSys/it-meetings) do not mark speakers. The agreed procedure (peer session 2026-11-11-11):
an agent labels every fragment with one of three labels and a confidence, the author checks 25 %
of fragments (low confidence first, then random), conflicts are re-labelled, and norms for 1.1
are published only when agreement is at least 90 %.

The transcripts are private and contain other people's speech: sheets are written outside any
repository (default .iwe-runtime/wp619-transcript-labels/), only aggregated numbers are published.

Usage:
  transcript-sheet.py <transcript.txt>... [--out DIR] [--max-words N]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parents[2] / ".iwe-runtime" / "wp619-transcript-labels"
LABELS = "автор-ведёт | автор-участвует | не-автор"
SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+(?=[А-ЯЁA-Z])")


def fragments(text: str, max_words: int) -> list[str]:
    """Paragraphs of the transcript; a paragraph longer than max_words is cut at sentence ends."""
    header, _, rest = text.partition("\n")
    body = rest if header.startswith("Автоматическая расшифровка") else text
    out = []
    for para in re.split(r"\n\s*\n", body):
        para = " ".join(para.split())
        if not para:
            continue
        chunk: list[str] = []
        for sentence in SENT_SPLIT_RE.split(para):
            if chunk and len(" ".join(chunk + [sentence]).split()) > max_words:
                out.extend(hard_cut(" ".join(chunk), max_words))
                chunk = []
            chunk.append(sentence)
        if chunk:
            out.extend(hard_cut(" ".join(chunk), max_words))
    return out


def hard_cut(text: str, max_words: int) -> list[str]:
    """Auto-transcripts are often unpunctuated: a run without sentence ends is cut by word count."""
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def sheet(name: str, parts: list[str]) -> str:
    lines = [
        f"# Разметка говорящих: {name}",
        "",
        f"Метки: {LABELS}. Уверенность 0–1. Проверка автора: «да» или правильная метка.",
        "",
    ]
    for i, part in enumerate(parts, 1):
        lines += [
            f"## {name}-{i:03d}",
            "",
            part,
            "",
            "Метка: ",
            "Уверенность: ",
            "Проверка автора: ",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-words", type=int, default=120)
    args = parser.parse_args()
    inside_repo = subprocess.run(
        ["git", "-C", str(args.out.resolve().parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() == "true"
    if inside_repo:
        print(f"отказ: {args.out} внутри git-хранилища, а расшифровки закрытые", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    total = 0
    for path in args.transcripts:
        parts = fragments(path.read_text("utf-8"), args.max_words)
        target = args.out / f"{path.stem}.md"
        target.write_text(sheet(path.stem, parts), "utf-8")
        total += len(parts)
        print(f"{path.stem}: {len(parts)} фрагментов -> {target}")
    print(f"всего фрагментов: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
