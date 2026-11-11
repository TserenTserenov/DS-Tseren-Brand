#!/usr/bin/env python3
"""Measure the author's spoken style from speaker-labelled transcripts (WP-619 F4, style 1.2).

Style 1.2 «Ведение практикума» is measured on raw Zoom transcripts of the personal development
practicum, where speakers are labelled (pilot decision 11.11.2026: start with 1.2, postpone 1.1
because the IT meeting transcripts have no speaker labels). Transcripts processed by an agent
are not used (pilot decision 05.11.2026).

Accepted line formats (one turn may span several lines until the next speaker line):
  WebVTT:        00:00:01.000 --> 00:00:04.000  then  "Имя Фамилия: текст"
  Zoom txt:      "[Имя Фамилия] 10:02:33" then text lines, or "10:02:33 Имя Фамилия: текст"
  Plain:         "Имя Фамилия: текст"

The transcripts are private (other participants' speech): only aggregated numbers are printed,
no text of the turns. Nothing is written to disk.

Usage:
  speech-metrics.py --speaker "Церен" [--speaker "Tseren"] <transcript>...
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*")
TIMING_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s+-->\s+")
BRACKET_SPEAKER_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")
INLINE_SPEAKER_RE = re.compile(r"^(?:\d{1,2}:\d{2}(?::\d{2})?\s+)?(?P<name>[^:\d][^:]{0,60}?):\s+(?P<text>.*)$")
# Spoken markers worth tracking for an oral style; descriptive, no thresholds.
MARKERS = ("то есть", "в принципе", "как бы", "короче", "значит", "собственно", "конечно", "вот")


@dataclass
class Turn:
    speaker: str
    text: str


def parse(text: str) -> list[Turn]:
    turns: list[Turn] = []
    speaker = None
    lines = [raw.strip() for raw in text.splitlines()]
    # In the "[Name] time" format a colon inside the text («Важно: …») is not a new speaker.
    bracket_format = any(BRACKET_SPEAKER_RE.match(line) for line in lines)
    for line in lines:
        if not line or line == "WEBVTT" or TIMING_RE.match(line) or line.isdigit():
            continue
        m = BRACKET_SPEAKER_RE.match(line)
        if m:
            speaker = m["name"].strip()
            turns.append(Turn(speaker, ""))
            continue
        m = None if bracket_format else INLINE_SPEAKER_RE.match(line)
        if m:
            speaker = m["name"].strip()
            turns.append(Turn(speaker, m["text"]))
        elif speaker and turns:
            turns[-1].text += " " + line
    return [t for t in turns if WORD_RE.search(t.text)]


def merge_consecutive(turns: list[Turn]) -> list[Turn]:
    """Zoom splits one long turn into many captions: consecutive lines of one speaker are one turn."""
    merged: list[Turn] = []
    for turn in turns:
        if merged and merged[-1].speaker == turn.speaker:
            merged[-1].text += " " + turn.text
        else:
            merged.append(Turn(turn.speaker, turn.text))
    return merged


def is_author(speaker: str, names: list[str]) -> bool:
    return any(name.lower() in speaker.lower() for name in names)


def band(values: list[float]) -> str:
    if len(values) < 4:
        return f"{statistics.median(values):.1f}" if values else "н/д"
    q1, med, q3 = statistics.quantiles(values, n=4)
    return f"{med:.1f} [{q1:.1f}–{q3:.1f}]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="+", type=Path)
    parser.add_argument("--speaker", action="append", required=True, help="part of the author's name as labelled")
    args = parser.parse_args()

    author_turns: list[str] = []
    author_words = all_words = 0
    speakers_seen: set[str] = set()
    for path in args.transcripts:
        turns = merge_consecutive(parse(path.read_text("utf-8", errors="replace")))
        speakers_seen.update(t.speaker for t in turns)
        for turn in turns:
            n = len(WORD_RE.findall(turn.text))
            all_words += n
            if is_author(turn.speaker, args.speaker):
                author_turns.append(turn.text)
                author_words += n
    if not author_turns:
        print(f"Реплик автора не найдено. Говорящие в файлах: {sorted(speakers_seen)}", file=sys.stderr)
        return 2

    lens = [len(WORD_RE.findall(t)) for t in author_turns]
    questions = [t.count("?") / max(1, len(re.findall(r"[.!?…]", t))) for t in author_turns]
    text = " ".join(author_turns).lower()
    print(f"Файлов: {len(args.transcripts)}; реплик автора: {len(author_turns)}; слов автора: {author_words}")
    print(f"Доля речи автора: {100 * author_words / all_words:.0f} % слов")
    print(f"Слов в реплике, медиана [нижняя–верхняя четверть]: {band(lens)}")
    print(f"Доля вопросительных предложений в реплике: {band(questions)}")
    print("Маркеры устной речи на 1000 слов автора:")
    for marker in MARKERS:
        count = len(re.findall(rf"\b{marker}\b", text))
        print(f"  {marker}: {1000 * count / author_words:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
