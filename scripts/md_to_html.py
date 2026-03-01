#!/usr/bin/env python3
"""Convert review Markdown to styled HTML using Jinja2 template."""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Template


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
    # Wrap "Suggested correction:" blocks
    html = re.sub(
        r'(<p>)(Suggested (?:correction|rewrite):)',
        r'\1<div class="correction"><span class="correction-label">Suggested correction:</span><br/>',
        html,
    )
    return html


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

    template_path = Path(__file__).parent / "review_template.html"
    template = Template(template_path.read_text(encoding="utf-8"))

    full_html = template.render(
        lang=lang,
        title=title,
        content=html_content,
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
