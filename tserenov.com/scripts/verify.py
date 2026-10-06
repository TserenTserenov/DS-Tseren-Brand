"""Check the rendered preview: links, locale isolation, and publication boundaries."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import sys


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.language = None
        self.noindex = False
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang")
        if tag == "h1":
            self.h1_count += 1
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag in {"a", "link"} and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag in {"img", "script"} and attributes.get("src"):
            self.links.append(attributes["src"])
        if tag == "meta" and attributes.get("name") == "robots":
            self.noindex = "noindex" in attributes.get("content", "")


def main():
    root = Path(__file__).resolve().parents[1]
    public = root / "public"
    errors = []
    documents = {}
    for path in public.rglob("*.html"):
        if path.name == "404.html":
            continue
        parser = Document()
        parser.feed(path.read_text())
        documents[path] = parser
        relative = path.relative_to(public).as_posix()
        expected = "en" if relative.startswith("en/") else "xal" if relative.startswith("xal/") else "ru"
        if parser.language != expected:
            errors.append(f"Wrong language: {relative}")
        if parser.h1_count != 1 or not parser.noindex:
            errors.append(f"Missing heading or preview boundary: {relative}")

    for path, document in documents.items():
        for href in document.links:
            url = urlsplit(href)
            if url.scheme in {"mailto", "data"}:
                continue
            if url.netloc and url.hostname not in {"127.0.0.1", "localhost"}:
                continue
            target = public / unquote(url.path).lstrip("/") if url.path else path
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"Broken internal link: {path.relative_to(public)} → {href}")
            elif url.fragment and target in documents and unquote(url.fragment) not in documents[target].ids:
                errors.append(f"Missing anchor: {href}")

    editorial = json.loads((root / "data/editorial.json").read_text())
    if editorial["ru"]["socials"] == editorial["en"]["socials"]:
        errors.append("Russian and English channels are not independently configured")
    if editorial["xal"]["ready"]:
        errors.append("Kalmyk review has not been completed")
    for route in ["index.html", "en/index.html", "xal/index.html", "video/index.html", "library/manifesto/index.html"]:
        if not (public / route).is_file():
            errors.append(f"Missing required route: {route}")
    if not documents:
        errors.append("No rendered pages; run zola build first")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Проверено страниц: {len(documents)}. Внутренние ссылки, языки и границы предпросмотра корректны.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
