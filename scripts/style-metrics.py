#!/usr/bin/env python3
"""Measure the author's writing style on the club post corpus (WP-619 F3; F5 adds thresholds).

Corpus: DS-Knowledge-Index-Tseren/docs/<year>/*.md, one post per file with a header
(title, category, date, URL) followed by "---" and the body.

Subcommands:
  norms     per-group norms (median and 25-75% band) for the author corpus 2020-2024
  samples   sample candidates per stratum: centre of the stratum and dialogic peak
  contrast  marker frequencies: author corpus 2020-2024 vs agent-era corpus 2026
  check     pre-publication check of one text against style/thresholds/<style>-*.yaml;
            exit 1 when a hard threshold is breached (styles 2.1 post, 2.3 instruction)

Only the author's own texts are kept: blogs of other people are excluded by category,
bodies shorter than MIN_WORDS are dropped (announcements, link posts).
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import yaml

IWE_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = IWE_ROOT / "DS-Knowledge-Index-Tseren" / "docs"
THRESHOLDS_DIR = Path(__file__).resolve().parents[1] / "style" / "thresholds"
AUTHOR_YEARS = ("2020", "2021", "2022", "2023", "2024")
AGENT_YEARS = ("2026",)
MIN_WORDS = 150
TTR_WINDOW = 500
AUTHOR_BLOG = "Блоги|Tseren Tserenov"
DRAFT_CATEGORIES = ("Черновики", "Исчезающие заметки")

WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*")
# Sentence end may be followed by closing quotes/brackets/markup before the space.
SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])[»\"')*]*\s+(?=[«\"(А-ЯЁA-Z0-9])")
SENT_CLOSERS = " »\"')*"
# Markdown escapes left by the club export, e.g. "\\*\\*bold\\*\\*".
MD_ESCAPE_RE = re.compile(r"\\([*_#\-\[\]().!>`])")
# Em dash anywhere, en dash only with spaces around (not "2020–2024").
EM_DASH_RE = re.compile(r"—|\s–\s")
SPACED_HYPHEN_RE = re.compile(r"\s-\s")
BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")
ITALIC_RE = re.compile(r"(?<![*\w])[*_][^*_\n]+[*_](?![*\w])")
HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s", re.MULTILINE)
NOT_X_BUT_Y_RE = re.compile(r"\bне\s+[^,.!?\n]{1,40},\s+а\s", re.IGNORECASE)
NOMINAL_RE = re.compile(
    r"(?:ние|ния|нию|нием|нии|ний|ниям|тие|тия|тию|тием|тий|ция|ции|цию|цией|ций|ость|ости|остью|остей)$"
)

FIRST_PERSON = {
    "я",
    "мне",
    "меня",
    "мной",
    "мы",
    "нас",
    "нам",
    "нами",
    "мой",
    "моя",
    "моё",
    "мое",
    "мои",
    "моих",
    "наш",
    "наша",
    "наше",
    "наши",
    "наших",
}
ADDRESS = {
    "вы",
    "вам",
    "вас",
    "вами",
    "ты",
    "тебе",
    "тебя",
    "тобой",
    "ваш",
    "ваша",
    "ваше",
    "ваши",
    "ваших",
    "твой",
    "твоя",
    "твоё",
    "твои",
}
SUBORDINATORS = {
    "что",
    "чтобы",
    "который",
    "которая",
    "которое",
    "которые",
    "которого",
    "которой",
    "которых",
    "которым",
    "которую",
    "если",
    "когда",
    "хотя",
    "поэтому",
    "поскольку",
    "где",
    "куда",
    "пока",
    "будто",
}
COORDINATORS = {"и", "а", "но", "или", "однако", "зато"}
INTRO_MARKERS = (
    "кстати",
    "кажется",
    "видимо",
    "наверное",
    "пожалуй",
    "по сути",
    "на самом деле",
    "важно",
    "конечно",
    "впрочем",
    "в общем",
    "собственно",
    "ключевой",
    "ключевое",
    "именно",
    "итак",
    "итог",
)

# Normative metrics get F5 thresholds; descriptive ones are reported without a limit.
NORMATIVE = (
    "words",
    "sent_len_median",
    "em_dash_per_k",
    "bold_per_k",
    "headings",
    "lists_per_k",
)
DESCRIPTIVE = (
    "para_len",
    "sent_len_sd",
    "sent_len_autocorr",
    "commas_per_sent",
    "complex_share",
    "sub_coord_ratio",
    "nominal_per_k",
    "colon_per_k",
    "paren_per_k",
    "quote_per_k",
    "spaced_hyphen_per_k",
    "italic_per_k",
    "question_share",
    "exclaim_share",
    "first_person_per_k",
    "address_per_k",
    "ttr_500",
    "dialogic_index",
)


@dataclass
class Post:
    path: Path
    title: str
    category: str
    date: str
    url: str
    raw_body: str
    text: str = ""
    paragraphs: list[str] = field(default_factory=list)
    sentences: list[str] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)

    @property
    def year(self) -> str:
        return self.date[:4]

    @property
    def group(self) -> str:
        return "draft" if self.category.startswith(DRAFT_CATEGORIES) else "published"


def header_value(lines: list[str], label: str) -> str:
    prefix = f"**{label}:**"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def parse_index_post(path: Path) -> Post | None:
    """Author corpus 2020-2024: markdown header (title, category, date, URL), then "---"."""
    text = path.read_text("utf-8")
    head, sep, body = text.partition("\n---\n")
    if not sep:
        return None
    lines = head.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else path.stem
    return Post(
        path,
        title,
        header_value(lines, "Категория"),
        header_value(lines, "Дата"),
        header_value(lines, "URL"),
        body.strip(),
    )


def parse_channel_post(path: Path) -> Post | None:
    """Agent-era corpus 2026: YAML frontmatter, then "# title" and the body."""
    text = path.read_text("utf-8")
    if not text.startswith("---\n"):
        return None
    _, front_text, body = text.split("---\n", 2)
    front = yaml.safe_load(front_text) or {}
    body = re.sub(
        r"\A\s*#\s[^\n]*\n", "", body
    )  # the title heading is not part of the text
    return Post(
        path,
        str(front.get("title", path.stem)),
        "agent-era",
        str(front.get("created", "")),
        "",
        body.strip(),
    )


def is_author_text(post: Post) -> bool:
    """Blogs of other people live in the same index; only the author's blog is kept."""
    return not (post.category.startswith("Блоги|") and post.category != AUTHOR_BLOG)


def plain_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(
        r"^\s*>.*$", " ", text, flags=re.MULTILINE
    )  # quoted text is not the author's voice
    text = re.sub(
        r"^#{1,6}\s.*$", " ", text, flags=re.MULTILINE
    )  # headings are layout, not prose
    text = re.sub(
        r"^\s*\*\*[^*\n]+\*\*:?\s*$", " ", text, flags=re.MULTILINE
    )  # bold-only subtitle lines
    text = re.sub(r"^\s*(?:#\S+\s*)+$", " ", text, flags=re.MULTILINE)  # hashtag lines
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    return text.replace("**", "").replace("__", "")


def split_sentences(paragraphs: list[str]) -> list[str]:
    sentences = []
    for para in paragraphs:
        sentences.extend(
            s.strip() for s in SENT_SPLIT_RE.split(para) if WORD_RE.search(s)
        )
    return sentences


def words_of(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def per_k(count: int, n_words: int) -> float:
    return 1000.0 * count / n_words


def lag1_autocorr(values: list[int]) -> float | None:
    if len(values) < 5:
        return None
    mean = statistics.fmean(values)
    denom = sum((v - mean) ** 2 for v in values)
    if denom == 0:
        return None
    return sum((a - mean) * (b - mean) for a, b in pairwise(values)) / denom


def ttr_windowed(words: list[str]) -> float | None:
    windows = [
        words[i : i + TTR_WINDOW]
        for i in range(0, len(words) - TTR_WINDOW + 1, TTR_WINDOW)
    ]
    if not windows:
        return None
    return statistics.fmean(len(set(w)) / TTR_WINDOW for w in windows)


def is_imperative_start(sentence: str) -> bool:
    first = words_of(sentence[:40])
    return bool(first) and first[0].endswith(("ите", "йте"))


def sentence_is_dialogic(sentence: str) -> bool:
    words = set(words_of(sentence))
    return (
        sentence.rstrip(SENT_CLOSERS).endswith(("?", "!"))
        or bool(words & FIRST_PERSON)
        or bool(words & ADDRESS)
        or is_imperative_start(sentence)
    )


def measure(post: Post, min_words: int = MIN_WORDS) -> bool:
    """Fill post metrics; False when the body is too short to measure (announcements, link posts)."""
    post.raw_body = MD_ESCAPE_RE.sub(r"\1", post.raw_body)
    post.text = plain_text(post.raw_body)
    post.paragraphs = [
        p.strip() for p in re.split(r"\n+", post.text) if WORD_RE.search(p)
    ]
    post.sentences = split_sentences(post.paragraphs)
    post.words = words_of(post.text)
    n_words = len(post.words)
    if n_words < min_words or not post.sentences:
        return False
    sent_lens = [len(words_of(s)) for s in post.sentences]
    n_sent = len(sent_lens)
    counts = Counter(post.words)
    sub = sum(counts[w] for w in SUBORDINATORS)
    coord = sum(counts[w] for w in COORDINATORS)
    raw = post.raw_body
    post.metrics = {
        "words": n_words,
        "sent_len_median": statistics.median(sent_lens),
        "sent_len_sd": statistics.pstdev(sent_lens) if n_sent > 1 else None,
        "sent_len_autocorr": lag1_autocorr(sent_lens),
        "para_len": statistics.median(len(words_of(p)) for p in post.paragraphs),
        "commas_per_sent": statistics.fmean(s.count(",") for s in post.sentences),
        "complex_share": sum(
            bool(set(words_of(s)) & SUBORDINATORS) for s in post.sentences
        )
        / n_sent,
        "sub_coord_ratio": sub / coord if coord else None,
        "nominal_per_k": per_k(
            sum(1 for w in post.words if NOMINAL_RE.search(w)), n_words
        ),
        "em_dash_per_k": per_k(len(EM_DASH_RE.findall(post.text)), n_words),
        "spaced_hyphen_per_k": per_k(len(SPACED_HYPHEN_RE.findall(post.text)), n_words),
        "colon_per_k": per_k(post.text.count(":"), n_words),
        "paren_per_k": per_k(post.text.count("("), n_words),
        "quote_per_k": per_k(post.text.count("«") + post.text.count('"') // 2, n_words),
        "bold_per_k": per_k(len(BOLD_RE.findall(raw)), n_words),
        "italic_per_k": per_k(len(ITALIC_RE.findall(raw.replace("**", ""))), n_words),
        "headings": len(HEADING_RE.findall(raw)),
        "lists_per_k": per_k(len(LIST_RE.findall(raw)), n_words),
        "not_x_but_y_per_k": per_k(len(NOT_X_BUT_Y_RE.findall(post.text)), n_words),
        "question_share": sum(
            s.rstrip(SENT_CLOSERS).endswith("?") for s in post.sentences
        )
        / n_sent,
        "exclaim_share": sum(
            s.rstrip(SENT_CLOSERS).endswith("!") for s in post.sentences
        )
        / n_sent,
        "first_person_per_k": per_k(sum(counts[w] for w in FIRST_PERSON), n_words),
        "address_per_k": per_k(sum(counts[w] for w in ADDRESS), n_words),
        "ttr_500": ttr_windowed(post.words),
        "dialogic_index": sum(sentence_is_dialogic(s) for s in post.sentences) / n_sent,
    }
    return True


def keep_measured(posts: list[Post]) -> list[Post]:
    return [post for post in posts if measure(post)]


def load_author() -> list[Post]:
    posts = []
    for year in AUTHOR_YEARS:
        for path in sorted((CORPUS_DIR / year).glob("*.md")):
            post = parse_index_post(path)
            if post is None:
                print(f"skip (no header separator): {path}", file=sys.stderr)
            elif is_author_text(post):
                posts.append(post)
    return keep_measured(posts)


def load_agent_era() -> list[Post]:
    """One file per post: the club version (other channels are adaptations of the same text)."""
    posts = []
    for year in AGENT_YEARS:
        for path in sorted((CORPUS_DIR / year).rglob("*-club-*.md")):
            post = parse_channel_post(path)
            if post is None:
                print(f"skip (no frontmatter): {path}", file=sys.stderr)
            else:
                posts.append(post)
    return keep_measured(posts)


def band(values: list[float]) -> tuple[float, float, float]:
    q1, med, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, med, q3


def fmt(x: float) -> str:
    return f"{x:.0f}" if abs(x) >= 100 else f"{x:.2f}" if abs(x) < 10 else f"{x:.1f}"


def norms_table(posts: list[Post], metrics: tuple[str, ...]) -> str:
    groups = {
        "published": [p for p in posts if p.group == "published"],
        "draft": [p for p in posts if p.group == "draft"],
    }
    rows = [
        "| Показатель | "
        + " | ".join(f"{g} (n={len(ps)}) медиана [25–75 %]" for g, ps in groups.items())
        + " |",
        "|---|" + "---|" * len(groups),
    ]
    for m in metrics:
        cells = []
        for ps in groups.values():
            values = [p.metrics[m] for p in ps if p.metrics[m] is not None]
            if len(values) < 4:
                cells.append("мало данных")
                continue
            q1, med, q3 = band(values)
            cells.append(f"{fmt(med)} [{fmt(q1)}–{fmt(q3)}]")
        rows.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def cmd_norms(_args: argparse.Namespace) -> None:
    posts = load_author()
    print(
        f"Корпус автора {AUTHOR_YEARS[0]}–{AUTHOR_YEARS[-1]}: {len(posts)} постов после фильтра\n"
    )
    print("## Нормативные\n\n" + norms_table(posts, NORMATIVE))
    print("\n## Описательные\n\n" + norms_table(posts, DESCRIPTIVE))
    print("\n## По годам (опубликованные): слов на пост и длина предложения\n")
    for year in AUTHOR_YEARS:
        ps = [p for p in posts if p.year == year and p.group == "published"]
        if len(ps) >= 4:
            w, s = (
                band([p.metrics["words"] for p in ps]),
                band([p.metrics["sent_len_median"] for p in ps]),
            )
            print(
                f"- {year}: n={len(ps)}, слов {fmt(w[1])} [{fmt(w[0])}–{fmt(w[2])}], "
                f"предложение {fmt(s[1])} [{fmt(s[0])}–{fmt(s[2])}]"
            )


def zscores(
    posts: list[Post], metrics: tuple[str, ...]
) -> dict[str, tuple[float, float]]:
    stats = {}
    for m in metrics:
        values = [p.metrics[m] for p in posts]
        stats[m] = (statistics.median(values), statistics.pstdev(values) or 1.0)
    return stats


def centre_post(stratum: list[Post]) -> Post:
    stats = zscores(stratum, NORMATIVE)

    def distance(p: Post) -> float:
        return sum(((p.metrics[m] - med) / sd) ** 2 for m, (med, sd) in stats.items())

    return min(stratum, key=distance)


def peak_post(stratum: list[Post], exclude: Post) -> Post | None:
    """Most dialogic post, capped at the 90th percentile so an outlier does not win."""
    candidates = [p for p in stratum if p is not exclude]
    if not candidates:
        return None
    values = [p.metrics["dialogic_index"] for p in candidates]
    cap = (
        statistics.quantiles(values, n=10, method="inclusive")[8]
        if len(values) >= 4
        else max(values)
    )
    return max(
        (p for p in candidates if p.metrics["dialogic_index"] <= cap),
        key=lambda p: p.metrics["dialogic_index"],
    )


def excerpt(post: Post) -> str:
    """Densest dialogic paragraph and the one after it, verbatim from the source markdown."""
    source_paras = [
        p.strip()
        for p in re.split(r"\n+", post.raw_body)
        if WORD_RE.search(plain_text(p)) and not p.lstrip().startswith("![")
    ]

    def density(para: str) -> float:
        sentences = split_sentences([plain_text(para)])
        return (
            sum(sentence_is_dialogic(s) for s in sentences) / len(sentences)
            if sentences
            else 0.0
        )

    best = max(range(len(source_paras)), key=lambda i: density(source_paras[i]))
    # Link targets are noise for a reader judging the voice; the link text stays verbatim.
    return re.sub(
        r"(?<!!)\[([^\]]*)\]\([^)]*\)",
        r"\1",
        "\n\n".join(source_paras[best : best + 2]),
    )


def cmd_samples(_args: argparse.Namespace) -> None:
    posts = load_author()
    q1, q2, q3 = band([p.metrics["words"] for p in posts])
    strata: dict[tuple, list[Post]] = {}
    for p in posts:
        length_quartile = sum(p.metrics["words"] > q for q in (q1, q2, q3)) + 1
        strata.setdefault((p.year, p.group, length_quartile), []).append(p)
    print(
        f"Кандидаты в образцы: {len(posts)} постов, страт {len(strata)} "
        f"(год × группа × четверть длины; границы {fmt(q1)}/{fmt(q2)}/{fmt(q3)} слов)\n"
    )
    for key in sorted(strata):
        stratum = strata[key]
        centre = centre_post(stratum)
        picks = [("центр", centre), ("пик", peak_post(stratum, centre))]
        for kind, post in picks:
            if post is None:
                continue
            print(
                f"### {key[0]} · {key[1]} · Q{key[2]} · {kind} — {post.title} ({post.date})\n"
            )
            print(
                f"Адрес: {post.url}  ·  слов {post.metrics['words']}, "
                f"диалогичность {post.metrics['dialogic_index']:.2f}\n"
            )
            print(excerpt(post) + "\n")


def marker_counts(posts: list[Post]) -> dict[str, float]:
    n_words = sum(len(p.words) for p in posts)
    totals = {
        "длинное тире (—, –)": sum(len(EM_DASH_RE.findall(p.text)) for p in posts),
        "жирный": sum(len(BOLD_RE.findall(p.raw_body)) for p in posts),
        "заголовки": sum(len(HEADING_RE.findall(p.raw_body)) for p in posts),
        "пункты списков": sum(len(LIST_RE.findall(p.raw_body)) for p in posts),
        "«не X, а Y»": sum(len(NOT_X_BUT_Y_RE.findall(p.text)) for p in posts),
        "двоеточие": sum(p.text.count(":") for p in posts),
    }
    for marker in INTRO_MARKERS:
        pattern = re.compile(rf"\b{marker}\b", re.IGNORECASE)
        totals[marker] = sum(len(pattern.findall(p.text)) for p in posts)
    return {k: per_k(v, n_words) for k, v in totals.items()}


def cmd_contrast(args: argparse.Namespace) -> None:
    author, agent = load_author(), load_agent_era()
    print(
        f"Автор {AUTHOR_YEARS[0]}–{AUTHOR_YEARS[-1]}: {len(author)} постов; "
        f"эпоха агента {', '.join(AGENT_YEARS)}: {len(agent)} постов\n"
    )
    a, g = marker_counts(author), marker_counts(agent)
    print(
        "## Заданные приметы, на 1000 слов\n\n| Примета | автор | агент | во сколько раз |\n|---|---|---|---|"
    )
    for k in a:
        ratio = f"{g[k] / a[k]:.1f}" if a[k] else "н/д"
        print(f"| {k} | {a[k]:.2f} | {g[k]:.2f} | {ratio} |")
    print(
        f"\n## Слова, которые у агента чаще в ≥{args.ratio} раз и не реже {args.min_per_k} на 1000 слов\n"
    )
    ca = Counter(w for p in author for w in p.words)
    cg = Counter(w for p in agent for w in p.words)
    na, ng = sum(ca.values()), sum(cg.values())
    rows = []
    for w, n in cg.items():
        rate_g = per_k(n, ng)
        rate_a = per_k(ca[w] + 1, na)  # +1 smoothing: words absent in the author corpus
        if rate_g >= args.min_per_k and rate_g / rate_a >= args.ratio:
            rows.append((rate_g / rate_a, w, per_k(ca[w], na), rate_g))
    print("| Слово | автор | агент | раз |\n|---|---|---|---|")
    for ratio, w, ra, rg in sorted(rows, reverse=True)[: args.top]:
        print(f"| {w} | {ra:.3f} | {rg:.2f} | {ratio:.1f} |")


# --- check: pre-publication thresholds (WP-619 F5/F6) ---

# Fenced code blocks, also indented inside a list item and with ~~~ fences.
FENCE_RE = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<lang>[\w+-]*)[^\n]*\n(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
# Blocks that hold commands to run; config, data and expected output are pasted or read, not run.
COMMAND_LANGS = {"", "bash", "sh", "shell", "zsh", "console", "powershell", "ps1", "pwsh", "cmd", "bat"}
# Only top-level items count as steps: nested numbered sub-items are details of a step.
STEP_RE = re.compile(r"^\d+[.)]\s+(.*)$")
# Imperative verbs common in setup instructions (informal and formal forms); a heuristic for
# the soft "one action per step". A suffix test («-ите») catches nouns («на сайте»), so a list.
_IMPERATIVE_STEMS = (
    "нажми", "открой", "вставь", "введи", "выбери", "скопируй", "запусти", "перейди",
    "проверь", "дождись", "закрой", "установи", "скачай", "найди", "напиши", "кликни",
    "отметь", "сохрани", "перезапусти", "подтверди", "укажи", "добавь", "удали", "включи",
    "выключи", "создай", "вернись", "подожди", "убедись", "зайди", "войди", "впиши", "ответь",
)
IMPERATIVES = {form for stem in _IMPERATIVE_STEMS for form in (stem, stem + "те")}
# Confirming keys and the typed text of the same action are not separate actions
# (DP.SC.050 example: «Нажми Cmd+Пробел, напиши `Терминал` и нажми Enter» opens one program).
CONFIRM_RE = re.compile(r"нажми(?:те)?\s+(?:enter|return|ввод)|напиши(?:те)?\s+`[^`]+`", re.IGNORECASE)


def load_thresholds(style: str) -> dict:
    files = sorted(THRESHOLDS_DIR.glob(f"{style}-*.yaml"))
    if len(files) != 1:
        raise SystemExit(f"порогов для стиля {style} нет или их несколько в {THRESHOLDS_DIR}: {files}")
    return yaml.safe_load(files[0].read_text("utf-8"))


def text_post(path: Path) -> Post:
    """A text to check: frontmatter and a title heading are dropped, the rest is the body."""
    raw = path.read_text("utf-8")
    if raw.startswith("---\n") and raw.count("---\n") >= 2:
        raw = raw.split("---\n", 2)[2]
    raw = re.sub(r"\A\s*#\s[^\n]*\n", "", raw)
    return Post(path, path.stem, "check", "", "", raw.strip())


def command_blocks(raw: str) -> list[str]:
    return [m["body"] for m in FENCE_RE.finditer(raw) if m["lang"].lower() in COMMAND_LANGS and m["body"].strip()]


def commands_in_block(block: str) -> int:
    """Commands in a code block: non-empty, non-comment lines; a trailing backslash joins lines."""
    count, continued = 0, False
    for line in block.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not continued:
            count += 1
        continued = stripped.endswith("\\")
    return count


def step_lists(raw: str) -> list[list[str]]:
    """Top-level numbered lists outside code blocks, each as a list of step texts (first line).
    Blank lines and indented continuation keep a list open; any other unindented line closes it."""
    lists, current = [], []
    for line in FENCE_RE.sub("", raw).splitlines():
        m = STEP_RE.match(line)
        if m:
            current.append(m.group(1))
        elif line.strip() and not line.startswith((" ", "\t")):
            if current:
                lists.append(current)
            current = []
    if current:
        lists.append(current)
    return lists


def has_section(raw: str, titles: list[str]) -> bool:
    """A heading or a bold lead line whose text equals one of the titles (case and final dot ignored)."""
    wanted = {t.lower() for t in titles}
    for line in FENCE_RE.sub("", raw).splitlines():
        m = re.match(r"^\s*(?:#{1,6}\s+(?P<head>.+?)\s*$|\*\*(?P<bold>[^*]+)\*\*)", line)
        if m and (m["head"] or m["bold"]).strip().rstrip(".:").lower() in wanted:
            return True
    return False


def count_actions(step: str) -> int:
    return sum(1 for w in words_of(CONFIRM_RE.sub(" ", step)) if w in IMPERATIVES)


def instruction_metrics(raw: str) -> dict[str, float]:
    lists = step_lists(raw)
    steps = [s for lst in lists for s in lst]
    first_sentence = [SENT_SPLIT_RE.split(s)[0] for s in steps]
    return {
        "numbered_steps": len(steps),
        "commands_per_code_block": max((commands_in_block(b) for b in command_blocks(raw)), default=0),
        "steps_per_list": max((len(lst) for lst in lists), default=0),
        "words_per_step": max((len(words_of(s)) for s in first_sentence), default=0),
        "actions_per_step": max((count_actions(s) for s in steps), default=0),
    }


def breaches(metrics: dict, rules: list[dict]) -> list[tuple[dict, float]]:
    out = []
    for rule in rules:
        value = metrics.get(rule["metric"])
        if value is None:
            continue
        if ("max" in rule and value > rule["max"]) or ("min" in rule and value < rule["min"]):
            out.append((rule, value))
    return out


def bound(rule: dict) -> str:
    if "min" in rule and "max" in rule:
        return f"{rule['min']}–{rule['max']}"
    return f"не больше {rule['max']}" if "max" in rule else f"не меньше {rule['min']}"


def cmd_check(args: argparse.Namespace) -> int:
    spec = load_thresholds(args.style)
    post = text_post(Path(args.file))
    if not measure(post, min_words=1):
        print(f"Нечего проверять: в {args.file} нет текста.", file=sys.stderr)
        return 2
    metrics = dict(post.metrics)
    if args.style == "2.3":
        metrics.update(instruction_metrics(post.raw_body))
    rules = spec.get("thresholds", []) + spec.get("stop_list", [])
    found = [(r, v, f"{v:.1f} ({r['unit']}), норма {bound(r)}") for r, v in breaches(metrics, rules)]
    for section in spec.get("required_sections", []):
        if not has_section(post.raw_body, section["titles"]):
            found.append((section, 0.0, f"нет раздела «{section['titles'][0]}»"))
    hard = [f for f in found if f[0].get("level") == "hard"]
    soft = [f for f in found if f[0].get("level") != "hard"]
    print(f"Стиль {spec['style_id']}, файл {args.file}: слов {len(post.words)}")
    for title, group in (("Обязательное, переписать", hard), ("Рекомендация, решает автор", soft)):
        for rule, _value, detail in group:
            print(f"- {title}: {rule.get('metric', rule.get('id'))} — {detail} [{rule['source']}]")
    if not found:
        print("Нарушений нет.")
    return 1 if hard else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("norms").set_defaults(func=cmd_norms)
    sub.add_parser("samples").set_defaults(func=cmd_samples)
    contrast = sub.add_parser("contrast")
    contrast.add_argument("--ratio", type=float, default=3.0)
    contrast.add_argument("--min-per-k", type=float, default=0.2)
    contrast.add_argument("--top", type=int, default=40)
    contrast.set_defaults(func=cmd_contrast)
    check = sub.add_parser("check", help="pre-publication check of one text")
    check.add_argument("file")
    check.add_argument("--style", required=True, choices=["2.1", "2.3"])
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
