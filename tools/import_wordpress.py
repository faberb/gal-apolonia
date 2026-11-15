#!/usr/bin/env python3
"""Export published WordPress posts and a media manifest from a SQL backup."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, unquote, urlparse


TABLE_PATTERN = re.compile(r"INSERT INTO `([^`]+)`")
IMAGE_PATTERN = re.compile(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)", re.IGNORECASE)
TEXT_TAG_PATTERN = re.compile(r"<[^>]*>")
UPLOAD_MARKER = "/wp-content/uploads/"
PUBLISHED_POST = "post"
MAX_ANIMATED_GIF_BYTES = 3_000_000


def parse_sql_values(line: str) -> list[str]:
    values: list[str] = []
    value: list[str] = []
    quoted = False
    index = 1
    replacements = {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
    }

    while index < len(line):
        char = line[index]
        if quoted:
            if char == "\\" and index + 1 < len(line):
                index += 1
                escaped = line[index]
                value.append(replacements.get(escaped, escaped))
            elif char == "'":
                if index + 1 < len(line) and line[index + 1] == "'":
                    value.append("'")
                    index += 1
                else:
                    quoted = False
            else:
                value.append(char)
        elif char == "'":
            quoted = True
        elif char == ",":
            values.append("".join(value).strip())
            value = []
        elif char == ")":
            values.append("".join(value).strip())
            break
        else:
            value.append(char)
        index += 1

    return values


def iter_sql_rows(database: Path, table_name: str) -> Iterator[list[str]]:
    active = False

    with database.open(encoding="utf-8", errors="replace") as sql_file:
        for line in sql_file:
            match = TABLE_PATTERN.match(line)
            if match:
                active = match.group(1) == table_name
                continue

            if not active or not line.startswith("("):
                continue

            yield parse_sql_values(line)
            if line.rstrip().endswith(";"):
                active = False


def image_source_path(url: str) -> str | None:
    parsed = urlparse(url)
    if UPLOAD_MARKER not in parsed.path:
        return None

    relative_path = unquote(parsed.path.split(UPLOAD_MARKER, 1)[1])
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Image URL points outside the uploads directory: {url}")
    return path.as_posix()


def plain_text(markup: str) -> str:
    text = TEXT_TAG_PATTERN.sub(" ", markup)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def rewritten_url(
    url: str,
    media_by_source: dict[str, str],
    attachment_media: dict[str, str],
    slug_by_id: dict[str, str],
) -> str | None:
    parsed = urlparse(url)
    source_path = image_source_path(url)
    if source_path is not None:
        return media_by_source.get(source_path)

    query = parse_qs(parsed.query)
    attachment_id = query.get("attachment_id", [None])[0]
    if attachment_id in attachment_media:
        return attachment_media[attachment_id]

    post_id = query.get("p", query.get("page_id", [None]))[0]
    if post_id in slug_by_id:
        return f"?post={slug_by_id[post_id]}"

    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {
        "galapolonia.com",
        "www.galapolonia.com",
    }:
        if parsed.path in {"", "/"}:
            return "index.html"
        return None

    if parsed.scheme in {"http", "https", "mailto", "tel"} or url.startswith("#"):
        return url

    return None


class SafeContent(HTMLParser):
    allowed_tags = {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "caption",
        "cite",
        "code",
        "dd",
        "del",
        "div",
        "dl",
        "dt",
        "em",
        "figcaption",
        "figure",
        "h2",
        "h3",
        "h4",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "q",
        "s",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
    void_tags = {"br", "hr", "img"}
    suppressed_tags = {"embed", "iframe", "object", "script", "style"}

    def __init__(
        self,
        media_by_source: dict[str, str],
        attachment_media: dict[str, str],
        slug_by_id: dict[str, str],
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.media_by_source = media_by_source
        self.attachment_media = attachment_media
        self.slug_by_id = slug_by_id
        self.parts: list[str] = []
        self.suppressed: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.suppressed:
            if tag not in self.void_tags:
                self.suppressed.append(tag)
            return
        if tag in self.suppressed_tags:
            self.suppressed.append(tag)
            return
        if tag not in self.allowed_tags:
            return

        safe_attrs: list[tuple[str, str]] = []
        for name, value in attrs:
            if value is None:
                continue
            name = name.lower()
            if name in {"href", "src"}:
                rewritten = rewritten_url(
                    value,
                    self.media_by_source,
                    self.attachment_media,
                    self.slug_by_id,
                )
                if rewritten is None:
                    continue
                safe_attrs.append((name, rewritten))
            elif name in {"alt", "title"}:
                safe_attrs.append((name, value))

        if tag == "img":
            if not any(name == "src" for name, _ in safe_attrs):
                return
            safe_attrs.extend((("loading", "lazy"), ("decoding", "async")))
        if tag == "a":
            href = next((value for name, value in safe_attrs if name == "href"), "")
            if href.startswith(("http://", "https://", "mailto:", "tel:")):
                safe_attrs.extend(
                    (("target", "_blank"), ("rel", "noopener noreferrer"))
                )

        attrs_text = "".join(
            f' {name}="{html.escape(value, quote=True)}"'
            for name, value in safe_attrs
        )
        self.parts.append(f"<{tag}{attrs_text}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.suppressed:
            if tag == self.suppressed[-1]:
                self.suppressed.pop()
            return
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(html.escape(data, quote=False))

    def clean(self, markup: str) -> str:
        self.feed(markup)
        self.close()
        return "".join(self.parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="WordPress SQL dump")
    parser.add_argument("--uploads", required=True, type=Path, help="WordPress uploads folder")
    parser.add_argument("--output", type=Path, default=Path.cwd(), help="Static site root")
    args = parser.parse_args()

    if not args.database.is_file():
        parser.error(f"SQL dump does not exist: {args.database}")
    if not args.uploads.is_dir():
        parser.error(f"Uploads directory does not exist: {args.uploads}")

    post_rows = [
        row
        for row in iter_sql_rows(args.database, "wp_posts")
        if len(row) >= 23
        and row[20] == PUBLISHED_POST
        and row[7] == "publish"
    ]
    if not post_rows:
        raise RuntimeError("The SQL dump contains no published WordPress posts.")

    postmeta: dict[str, dict[str, str]] = {}
    for row in iter_sql_rows(args.database, "wp_postmeta"):
        if len(row) >= 4:
            postmeta.setdefault(row[1], {})[row[2]] = row[3]

    relationships: dict[str, list[str]] = {}
    for row in iter_sql_rows(args.database, "wp_term_relationships"):
        if len(row) >= 2:
            relationships.setdefault(row[0], []).append(row[1])

    taxonomy: dict[str, tuple[str, str]] = {}
    for row in iter_sql_rows(args.database, "wp_term_taxonomy"):
        if len(row) >= 3:
            taxonomy[row[0]] = (row[1], row[2])

    terms: dict[str, str] = {}
    for row in iter_sql_rows(args.database, "wp_terms"):
        if len(row) >= 3:
            terms[row[0]] = html.unescape(row[1])

    attachments: dict[str, str] = {}
    for row in iter_sql_rows(args.database, "wp_posts"):
        if len(row) >= 23 and row[20] == "attachment":
            attached_file = postmeta.get(row[0], {}).get("_wp_attached_file")
            if attached_file:
                attachments[row[0]] = Path(attached_file).as_posix()

    image_paths: list[str] = []
    for row in post_rows:
        for url in IMAGE_PATTERN.findall(row[4]):
            source_path = image_source_path(url)
            if source_path and source_path not in image_paths:
                image_paths.append(source_path)

    output_root = args.output.resolve()
    media_by_source: dict[str, str] = {}
    manifest: list[dict[str, str | int]] = []

    for source_path in image_paths:
        source = args.uploads / Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"Referenced WordPress image is missing: {source}")

        suffix = source.suffix.lower()
        optimize_as = "copy"
        output_suffix = suffix
        if suffix in {".jpg", ".jpeg"}:
            output_suffix = ".jpg"
            optimize_as = "jpeg"
        elif suffix == ".gif" and source.stat().st_size > MAX_ANIMATED_GIF_BYTES:
            output_suffix = ".jpg"
            optimize_as = "first-frame"

        path_hash = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:14]
        target = f"assets/images/posts/{path_hash}{output_suffix}"
        media_by_source[source_path] = target
        manifest.append(
            {
                "source": source_path,
                "target": target,
                "operation": optimize_as,
                "size": source.stat().st_size,
            }
        )

    attachment_media = {
        attachment_id: media_by_source[source_path]
        for attachment_id, source_path in attachments.items()
        if source_path in media_by_source
    }
    slug_by_id = {row[0]: unquote(row[11]) for row in post_rows if row[11]}
    posts: list[dict[str, object]] = []

    for row in post_rows:
        post_id = row[0]
        sanitizer = SafeContent(media_by_source, attachment_media, slug_by_id)
        clean_content = sanitizer.clean(row[4])
        excerpt = plain_text(row[6]) or plain_text(clean_content)
        post_categories: list[str] = []
        post_tags: list[str] = []

        for taxonomy_id in relationships.get(post_id, []):
            term_record = taxonomy.get(taxonomy_id)
            if term_record is None:
                continue
            term_id, kind = term_record
            term_name = terms.get(term_id)
            if (
                term_name
                and term_name.casefold() != "uncategorized"
                and kind == "category"
                and term_name not in post_categories
            ):
                post_categories.append(term_name)
            if term_name and kind == "post_tag" and term_name not in post_tags:
                post_tags.append(term_name)

        image_match = IMAGE_PATTERN.search(row[4])
        featured = None
        if image_match:
            source_path = image_source_path(image_match.group(1))
            featured = media_by_source.get(source_path) if source_path else None

        posts.append(
            {
                "id": post_id,
                "title": html.unescape(row[5]),
                "slug": unquote(row[11]) if row[11] else post_id,
                "date": row[2][:10],
                "excerpt": excerpt[:360],
                "categories": post_categories,
                "tags": post_tags,
                "image": featured,
                "content": clean_content,
            }
        )

    posts.sort(key=lambda post: (str(post["date"]), int(str(post["id"]))), reverse=True)

    data_directory = output_root / "data"
    data_directory.mkdir(parents=True, exist_ok=True)
    (data_directory / "posts.json").write_text(
        json.dumps(posts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (data_directory / "media-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Exported {len(posts)} published posts.")
    print(f"Prepared {len(manifest)} original story photos for optimized local copies.")


if __name__ == "__main__":
    main()
