#!/usr/bin/env python3
"""Find blank slides in a built .pptx without LibreOffice.

`scripts/render_slides.py` needs soffice to produce a contact sheet, so on a
pod without LibreOffice the visual QA stage is simply skipped -- which is how a
deck full of header-only slides ships unnoticed. This reads the OOXML directly:
no soffice, no python-pptx, no network.

    python tools/check_deck.py build/deck.pptx
    python tools/check_deck.py build/deck.pptx --outline outline.json
    python tools/check_deck.py build/deck.pptx --json > deck_content_report.json

Exit code 1 when at least one content slide rendered nothing but its header,
so it can be used as a build gate:

    python tools/check_deck.py build/deck.pptx || echo "fix the outline"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.S)
# Footer chrome the renderer adds on its own; it is not deck content.
CHROME_RE = re.compile(r"^\s*(\d+\s*/\s*\d+|\d+|page \d+)\s*$", re.I)


def unescape(value: str) -> str:
    return (value.replace("&amp;", "&").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))


def slide_texts(archive: zipfile.ZipFile) -> list[tuple[int, list[str]]]:
    entries = []
    for name in archive.namelist():
        match = SLIDE_RE.match(name)
        if match:
            runs = [unescape(t).strip() for t in TEXT_RE.findall(
                archive.read(name).decode("utf-8"))]
            entries.append((int(match.group(1)), [r for r in runs if r]))
    entries.sort()
    return entries


def outline_slides(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    slides = data.get("slides") if isinstance(data, dict) else data
    return slides if isinstance(slides, list) else []


def analyse(deck: Path, outline: Path | None, thin_chars: int = 40) -> dict:
    with zipfile.ZipFile(deck) as archive:
        entries = slide_texts(archive)

    planned = outline_slides(outline) if outline else []
    rows = []
    for index, runs in entries:
        spec = planned[index - 1] if index - 1 < len(planned) else {}
        kind = str(spec.get("type") or "content").strip().lower() if spec else ""
        title = str(spec.get("title") or (runs[0] if runs else "")).strip()

        body = [r for r in runs[1:] if not CHROME_RE.match(r)]
        body_chars = sum(len(r) for r in body)
        blank = (not body) and kind not in {"title", "section"}
        thin = (not blank) and body_chars < thin_chars and kind not in {"title", "section"}

        rows.append({
            "slide": index,
            "type": kind or "?",
            "variant": str(spec.get("variant") or "").strip().lower(),
            "title": title[:70],
            "runs": len(runs),
            "body_runs": len(body),
            "body_chars": body_chars,
            "status": "BLANK" if blank else ("THIN" if thin else "ok"),
        })

    blanks = [r for r in rows if r["status"] == "BLANK"]
    thins = [r for r in rows if r["status"] == "THIN"]
    return {
        "deck": str(deck),
        "outline": str(outline) if outline else None,
        "slide_count": len(rows),
        "blank_count": len(blanks),
        "thin_count": len(thins),
        "slides": rows,
    }


def render_text(report: dict) -> None:
    print(f"{report['deck']}  ({report['slide_count']} slides)")
    print(f"{'#':>3}  {'status':<6} {'type':<9} {'variant':<16} {'body':>10}  title")
    for row in report["slides"]:
        marker = {"BLANK": "!!", "THIN": " ?", "ok": "  "}[row["status"]]
        print(f"{row['slide']:>3}{marker} {row['status']:<6} {row['type']:<9} "
              f"{row['variant']:<16} {row['body_chars']:>4}c/{row['body_runs']:<3}  {row['title']}")
    print()
    if report["blank_count"]:
        print(f"{report['blank_count']} slide(s) render a header and nothing else.")
        print("Most common cause: the outline used a payload key the renderer does not read")
        print("(content/points/items/text/stats/cards[].description). This fork repairs those")
        print("in templates/pptxgenjs/slot_aliases.js and warns at build time, so a slide")
        print("still listed here has no payload at all -- check the outline itself.")
    elif report["thin_count"]:
        print(f"{report['thin_count']} slide(s) carry very little body text -- worth a look.")
    else:
        print("No blank slides.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--outline", type=Path,
                    help="outline.json used to build the deck (adds type/variant columns)")
    ap.add_argument("--thin-chars", type=int, default=40,
                    help="flag a slide as THIN below this many body characters (default 40)")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args()

    if not args.deck.is_file():
        print(f"error: {args.deck} not found", file=sys.stderr)
        return 2

    report = analyse(args.deck, args.outline, args.thin_chars)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_text(report)
    return 1 if report["blank_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
