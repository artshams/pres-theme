#!/usr/bin/env python3
"""Small, model-friendly entrypoint for presentation-skill workflows."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from composition_grammar_catalog import quick_deck_agent_brief, route_composition_grammars  # noqa: E402


def _run(script: str, arguments: list[str]) -> int:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "python_runtime.py"), str(SCRIPTS / script), *arguments],
        cwd=ROOT,
        check=False,
    )
    return int(completed.returncode)


def _write_or_print(payload: dict[str, Any], output: Path | None) -> None:
    # This handoff is consumed by a model, so avoid spending context on JSON whitespace.
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if output is None:
        print(encoded, end="")
        return
    destination = output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(encoded, encoding="utf-8")
    print(destination)


def _brief(args: argparse.Namespace) -> int:
    style = "" if args.style_preset == "auto" else args.style_preset
    route = route_composition_grammars(
        topic=args.topic,
        user_prompt=args.prompt,
        style_preset=style,
        limit=3,
    )
    brief = quick_deck_agent_brief(
        route,
        slide_count=max(3, min(30, args.slides)),
        agent_profile=args.profile,
    )
    _write_or_print(brief, args.output)
    return 0


def _init(args: argparse.Namespace) -> int:
    command = [
        "--workspace", str(args.workspace.expanduser().resolve()),
        "--title", args.title,
        "--style-preset", args.style_preset,
        "--agent-profile", args.profile,
    ]
    if args.prompt:
        command.extend(["--user-prompt", args.prompt])
    if args.audit_packet:
        command.append("--emit-start-packet")
    else:
        command.append("--skip-start-packet")
    if args.overwrite:
        command.append("--overwrite")
    return _run("init_deck_workspace.py", command)


def _build(args: argparse.Namespace) -> int:
    command = [
        "--workspace", str(args.workspace.expanduser().resolve()),
        "--qa",
        "--overwrite",
    ]
    if args.draft:
        command.extend(
            [
                "--skip-render",
                "--fail-on-planning-warnings",
                "--fail-on-whitespace-warnings",
            ]
        )
    else:
        command.extend(
            [
                "--visual-review",
                "--fail-on-visual-review-warnings",
                "--fail-on-planning-warnings",
                "--fail-on-whitespace-warnings",
            ]
        )
    return _run("build_workspace.py", command)


def _finalize(args: argparse.Namespace) -> int:
    command = [
        "--outline", str(args.outline.expanduser().resolve()),
        "--output", str(args.output.expanduser().resolve()),
        "--style-preset", args.style_preset,
    ]
    if args.qa_dir:
        command.extend(["--qa-dir", str(args.qa_dir.expanduser().resolve())])
    if args.asset_root:
        command.extend(["--asset-root", str(args.asset_root.expanduser().resolve())])
    return _run("finalize_quick_deck.py", command)


def _doctor(_args: argparse.Namespace) -> int:
    return _run("runtime_doctor.py", [])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Route, initialize, build, and finalize reproducible editable PowerPoint decks."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Check the pinned local runtime.")
    doctor.set_defaults(handler=_doctor)

    brief = commands.add_parser("brief", help="Emit a compact model-ready quick-deck brief.")
    brief.add_argument("--topic", required=True)
    brief.add_argument("--prompt", default="")
    brief.add_argument("--slides", type=int, default=7)
    brief.add_argument("--style-preset", default="auto")
    brief.add_argument(
        "--profile",
        choices=("auto", "fast", "balanced", "quality-first", "luna", "terra", "sol"),
        default="auto",
    )
    brief.add_argument("--output", type=Path)
    brief.set_defaults(handler=_brief)

    init = commands.add_parser("init", help="Create a rebuildable deck workspace.")
    init.add_argument("--workspace", type=Path, required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--prompt", default="")
    init.add_argument("--style-preset", default="auto")
    init.add_argument(
        "--profile",
        choices=("auto", "fast", "balanced", "quality-first", "luna", "terra", "sol"),
        default="auto",
    )
    init.add_argument("--overwrite", action="store_true")
    init.add_argument(
        "--audit-packet",
        action="store_true",
        help="Also persist the full deck-start audit/recovery packet.",
    )
    init.set_defaults(handler=_init)

    build = commands.add_parser("build", help="Build a saved workspace.")
    build.add_argument("--workspace", type=Path, required=True)
    build.add_argument("--draft", action="store_true", help="Run source/static QA without rendering.")
    build.set_defaults(handler=_build)

    final = commands.add_parser("finalize", help="Build, render, and QA a quick deck.")
    final.add_argument("--outline", type=Path, required=True)
    final.add_argument("--output", type=Path, required=True)
    final.add_argument("--style-preset", default="auto")
    final.add_argument("--qa-dir", type=Path)
    final.add_argument("--asset-root", type=Path)
    final.set_defaults(handler=_finalize)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
