"""Build the approved Russian and English public edition of tserenov.com."""

from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public-release"
PUBLIC_URL = "https://tserenov.com"
APPROVED = {"approved", "published"}


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.language = None
        self.heading_count = 0
        self.ids = set()
        self.links = []
        self.canonical = None
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang")
        if tag == "h1":
            self.heading_count += 1
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag in {"a", "link"} and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag in {"img", "script"} and attributes.get("src"):
            self.links.append(attributes["src"])
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href")
        if tag == "meta" and attributes.get("name") == "robots":
            self.noindex = "noindex" in attributes.get("content", "")


def editorial_errors():
    editorial = json.loads((ROOT / "data/editorial.json").read_text())
    errors = []
    for language in ("ru", "en"):
        edition = editorial[language]
        if not edition.get("ready"):
            errors.append(f"{language}: редакция не готова")
        if not edition.get("publication_approved"):
            errors.append(f"{language}: нет авторского разрешения на публикацию")
    if editorial["xal"].get("publication_approved"):
        errors.append("xal: калмыцкая редакция требует проверки носителем")

    for path in sorted((ROOT / "content").rglob("*.md")):
        if path.name.endswith(".xal.md") or path.name.startswith("_index"):
            continue
        source = path.read_text()
        parts = source.split("+++", 2)
        if len(parts) != 3 or parts[0].strip():
            errors.append(f"{path.relative_to(ROOT)}: нет TOML frontmatter")
            continue
        metadata = tomllib.loads(parts[1])
        if metadata.get("extra", {}).get("editorial_status") not in APPROVED:
            errors.append(f"{path.relative_to(ROOT)}: материал не утверждён")
    return errors


def replace_once(source, pattern, replacement):
    updated, count = re.subn(pattern, replacement, source, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Ожидалась одна строка конфигурации: {pattern}")
    return updated


def prepare_source(stage):
    for directory in ("data", "templates", "static"):
        shutil.copytree(ROOT / directory, stage / directory)
    shutil.copytree(
        ROOT / "content", stage / "content",
        ignore=lambda _, names: {name for name in names if name.endswith(".xal.md")},
    )
    config = (ROOT / "config.toml").read_text()
    config = replace_once(config, r'^base_url = ".*"$', f'base_url = "{PUBLIC_URL}"')
    config = replace_once(config, r"^preview = true$", 'preview = false\nactive_languages = ["ru", "en"]')
    config = replace_once(config, r"(?s)^\[languages\.xal\]\n.*?(?=^\[|\Z)", "")
    parsed = tomllib.loads(config)
    if set(parsed["languages"]) != {"en"} or parsed["extra"]["preview"]:
        raise ValueError("Публичная конфигурация языков некорректна")
    (stage / "config.toml").write_text(config)
    (stage / "static/robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_URL}/sitemap.xml\n"
    )


def verify_output(public):
    errors = []
    documents = {}
    for path in public.rglob("*.html"):
        document = PageLinks()
        source = path.read_text()
        document.feed(source)
        relative = path.relative_to(public).as_posix()
        expected = "en" if relative.startswith("en/") else "ru"
        if relative != "404.html" and document.language != expected:
            errors.append(f"Неверный язык: {relative}")
        if relative != "404.html" and document.heading_count != 1:
            errors.append(f"Нужен один заголовок H1: {relative}")
        if document.noindex or "127.0.0.1" in source or "localhost" in source:
            errors.append(f"Предпросмотр попал в публичную страницу: {relative}")
        if relative != "404.html" and not (document.canonical or "").startswith(PUBLIC_URL + "/"):
            errors.append(f"Нет публичного canonical: {relative}")
        if "/xal/" in source or "edition-xal" in source:
            errors.append(f"Калмыцкая редакция попала в страницу: {relative}")
        if relative in {"index.html", "en/index.html"} and 'class="ask-form"' not in source:
            errors.append(f"Нет формы вопросов в публичной странице: {relative}")
        documents[path] = document

    if not documents or not (public / "index.html").is_file() or not (public / "en/index.html").is_file():
        errors.append("Нет обеих главных страниц")
    if (public / "xal").exists():
        errors.append("Калмыцкая редакция попала в сборку")
    if "Disallow" in (public / "robots.txt").read_text():
        errors.append("Публичный robots.txt запрещает обход")
    if "/xal/" in (public / "sitemap.xml").read_text():
        errors.append("Калмыцкая редакция попала в sitemap")

    for path, document in documents.items():
        for href in document.links:
            url = urlsplit(href)
            if url.scheme in {"mailto", "data"} or (url.netloc and url.hostname != "tserenov.com"):
                continue
            if url.netloc and url.scheme != "https":
                errors.append(f"Небезопасная внутренняя ссылка: {href}")
            target = public / unquote(url.path).lstrip("/") if url.path else path
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"Неработающая ссылка: {path.relative_to(public)} → {href}")
            elif url.fragment and target in documents and unquote(url.fragment) not in documents[target].ids:
                errors.append(f"Нет якоря: {href}")
    return errors


def main():
    errors = editorial_errors()
    if errors:
        print("Публичная сборка остановлена:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    with TemporaryDirectory(prefix="tserenov-release-") as temporary:
        stage = Path(temporary)
        prepare_source(stage)
        subprocess.run([os.environ.get("ZOLA_BIN", "zola"), "build"], cwd=stage, check=True)
        errors = verify_output(stage / "public")
        if errors:
            print("Проверка публичной сборки не пройдена:\n" + "\n".join(errors), file=sys.stderr)
            return 1
        if OUTPUT.exists():
            shutil.rmtree(OUTPUT)
        shutil.copytree(stage / "public", OUTPUT)
    print(f"Публичная сборка проверена: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
