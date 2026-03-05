#!/usr/bin/env python3
"""Convert review Markdown to styled HTML using Jinja2 template."""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, select_autoescape
from markupsafe import Markup

try:
    import nh3  # type: ignore
except ImportError:  # pragma: no cover
    nh3 = None

try:
    import bleach  # type: ignore
except ImportError:  # pragma: no cover
    bleach = None


def detect_language(md_text: str) -> str:
    """Detect if the review is in Hungarian or English."""
    hu_markers = [
        "Bírálói vélemény", "Összefoglalás", "Értékelés",
        "Főbb észrevételek", "Kisebb észrevételek", "Javaslat",
        "módszertan", "irodalomjegyzék", "hivatkozás",
    ]
    count = sum(1 for m in hu_markers if m.lower() in md_text.lower())
    return "hu" if count >= 2 else "en"


def extract_title(md_text: str) -> str:
    """Extract paper title from the review metadata."""
    for line in md_text.split("\n"):
        if line.startswith("**Manuscript:**") or line.startswith("**Kézirat:**"):
            return line.split(":**", 1)[1].strip().strip("*")
        match = re.match(r"^#\s+Referee Report", line)
        if match:
            continue
        match = re.match(r"^#\s+(.+)", line)
        if match:
            return match.group(1).strip()
    return "Untitled"


def enhance_html(html: str) -> str:
    """Add CSS classes for severity labels and corrections."""
    severity_map = {
        "Critical": "severity-critical",
        "Major": "severity-major",
        "Minor": "severity-minor",
        "Suggestion": "severity-suggestion",
    }
    for label, css_class in severity_map.items():
        html = html.replace(
            f"<td>{label}</td>",
            f'<td class="{css_class}">{label}</td>',
        )
    # Wrap "Suggested correction/rewrite:" paragraphs in a highlighted box.
    def _wrap_suggested(match: re.Match[str]) -> str:
        text = match.group(1).strip()
        label_match = re.match(r"Suggested (?:correction|rewrite):", text, flags=re.IGNORECASE)
        if not label_match:
            return match.group(0)
        label = label_match.group(0)
        body = text[label_match.end() :].strip()
        return (
            '<div class="correction">'
            f'<span class="correction-label">{label}</span><br/>{body}'
            "</div>"
        )

    html = re.sub(
        r"<p>(Suggested (?:correction|rewrite):.*?)</p>",
        _wrap_suggested,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html


def sanitize_html(html: str) -> str:
    """Sanitize generated HTML to prevent script/style injection."""
    allowed_tags = {
        "a",
        "blockquote",
        "br",
        "code",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
    allowed_attributes = {
        "*": {"id", "class"},
        "a": {"href", "title", "name"},
        "img": {"src", "alt", "title"},
    }
    url_schemes = {"http", "https", "mailto"}
    if nh3 is not None:
        return nh3.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            url_schemes=url_schemes,
            strip_comments=True,
            link_rel=None,
        )

    if bleach is None:
        raise RuntimeError(
            "No HTML sanitizer backend available. Install nh3 (preferred) or bleach."
        )

    return bleach.clean(
        html,
        tags=list(allowed_tags),
        attributes={tag: list(attrs) for tag, attrs in allowed_attributes.items()},
        protocols=list(url_schemes),
        strip=True,
    )


def sanitize_title(title: str) -> str:
    """Strip any markup from a title before template rendering."""
    if nh3 is not None:
        return nh3.clean(title, tags=set(), attributes={}, strip_comments=True, link_rel=None).strip()
    if bleach is None:
        raise RuntimeError(
            "No HTML sanitizer backend available. Install nh3 (preferred) or bleach."
        )
    return bleach.clean(title, tags=[], attributes={}, strip=True).strip()  # type: ignore[name-defined]


def convert(md_path: str, output_path: str | None = None) -> str:
    """Convert markdown review to styled HTML."""
    md_text = Path(md_path).read_text(encoding="utf-8")

    lang = detect_language(md_text)
    title = extract_title(md_text)

    extensions = [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.footnotes",
        "markdown.extensions.toc",
    ]
    html_content = markdown.markdown(md_text, extensions=extensions)
    html_content = enhance_html(html_content)
    html_content = sanitize_html(html_content)
    safe_title = sanitize_title(title)

    template_path = Path(__file__).parent / "review_template.html"
    env = Environment(
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=True,
        )
    )
    template = env.from_string(template_path.read_text(encoding="utf-8"))

    full_html = template.render(
        lang=lang,
        title=safe_title,
        content=Markup(html_content),
        date=datetime.now().strftime("%Y-%m-%d"),
    )

    if output_path is None:
        output_path = str(Path(md_path).with_suffix(".html"))

    Path(output_path).write_text(full_html, encoding="utf-8")
    print(f"HTML generated: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert review Markdown to styled HTML"
    )
    parser.add_argument("input", help="Path to review Markdown file")
    parser.add_argument(
        "--output", "-o", help="Output HTML path (default: same name with .html)"
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    convert(args.input, args.output)


if __name__ == "__main__":
    main()
