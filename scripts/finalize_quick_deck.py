#!/usr/bin/env python3
"""Build, render, and hard-gate one source-first quick deck."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from workflow_atom_context import DEFAULT_FAMILY, build_workflow_atom_context  # noqa: E402
from design_tokens import FORCED_STYLE_PRESET, force_style_preset  # noqa: E402


QA_BLOCKING_KEYS = (
    "overflow_count",
    "overlap_count",
    "geometry_error_count",
    "geometry_warning_count",
    "whitespace_warning_count",
    "visual_warning_count",
    "visual_review_warning_count",
    "design_error_count",
    "design_warning_count",
    "accessibility_error_count",
    "accessibility_warning_count",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_outline(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("outline root must be a JSON object")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _completion_status(records: list[dict[str, Any]], qa_dir: Path) -> dict[str, Any]:
    qa = _load_json(qa_dir / "qa_report.json")
    qa_counts = {key: int(qa.get(key, 0) or 0) for key in QA_BLOCKING_KEYS}
    failed_stage = next(
        (str(record.get("stage") or "") for record in records if not bool(record.get("accepted", False))),
        "",
    )
    render_rc = qa.get("render_rc")
    render_failed = render_rc is not None and int(render_rc or 0) != 0
    static_keys = tuple(key for key in QA_BLOCKING_KEYS if key not in {"visual_review_warning_count"})
    static_findings = sum(qa_counts[key] for key in static_keys)
    if not failed_stage:
        category = "passed"
        next_action = "Deliver the deck and receipt."
    elif failed_stage == "preflight":
        category = "outline_preflight"
        next_action = "Fix the reported outline fields, then rerun the finalizer once."
    elif failed_stage == "build":
        category = "build_failure"
        next_action = "Fix the reported source or asset error; do not patch the generated PPTX."
    elif failed_stage == "qa" and render_failed and static_findings == 0:
        category = "render_environment"
        next_action = (
            "Preserve the built deck and static QA report. Do not probe alternate Office apps, "
            "Python installations, or preview tools; rerun the same finalizer outside the sandbox "
            "to complete rendered visual review."
        )
    else:
        category = "qa_findings"
        next_action = "Read qa_report.json and the contact sheet, edit outline.json, then rerun once."
    return {
        "failure_category": category,
        "failed_stage": failed_stage,
        "render_status": "deferred_environment" if category == "render_environment" else (
            "passed" if qa and not render_failed else "not_completed"
        ),
        "qa_counts": qa_counts,
        "next_action": next_action,
    }


def _thresholds(
    outline: dict[str, Any],
    body_override: float | None,
    support_override: float | None,
    metadata_override: float | None,
) -> tuple[float, float, float]:
    style = outline.get("deck_style") if isinstance(outline.get("deck_style"), dict) else {}
    contract = style.get("readability_contract") if isinstance(style.get("readability_contract"), dict) else {}
    body = body_override if body_override is not None else float(contract.get("min_body_pt", 16))
    support = support_override if support_override is not None else float(contract.get("min_support_pt", 13))
    metadata = metadata_override
    if metadata is None:
        metadata = float(
            contract.get(
                "min_metadata_pt",
                contract.get("min_footer_pt", contract.get("min_caption_pt", 9)),
            )
        )
    return body, support, metadata


def _resolve_style_preset(outline: dict[str, Any], requested: str) -> tuple[str, str]:
    if FORCED_STYLE_PRESET:
        # Nothing below can select a preset while one is forced -- not the CLI
        # flag, not outline.deck_style, not the outline's own wording.
        return force_style_preset(requested), "forced_house_style"
    explicit = str(requested or "auto").strip().lower()
    if explicit and explicit != "auto":
        return explicit, "explicit_cli"
    deck_style = outline.get("deck_style") if isinstance(outline.get("deck_style"), dict) else {}
    metadata = outline.get("metadata") if isinstance(outline.get("metadata"), dict) else {}
    for value in (
        outline.get("style_preset"),
        deck_style.get("style_preset"),
        metadata.get("style_preset"),
    ):
        candidate = str(value or "").strip().lower()
        if candidate and candidate != "auto":
            return candidate, "outline_design_choice"
    slides = outline.get("slides") if isinstance(outline.get("slides"), list) else []
    prompt_parts = [str(outline.get("title") or "")]
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        prompt_parts.extend(
            str(slide.get(key) or "")
            for key in ("title", "subtitle", "slide_intent", "role", "variant")
        )
    context = build_workflow_atom_context(
        user_prompt=" ".join(part for part in prompt_parts if part).strip(),
        style_preset="",
        slide_count=max(3, len(slides)),
        include_prompt=False,
    )
    resolved = str(context.get("target_family") or DEFAULT_FAMILY).strip().lower()
    return resolved or DEFAULT_FAMILY, "deterministic_outline_fallback"


def _run(
    stage: str,
    command: list[str],
    records: list[dict[str, Any]],
    *,
    accepted_returncodes: tuple[int, ...] = (0,),
) -> bool:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout or ""
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    records.append(
        {
            "stage": stage,
            "command": command,
            "returncode": completed.returncode,
            "accepted_returncodes": list(accepted_returncodes),
            "accepted": completed.returncode in accepted_returncodes,
            "duration_seconds": round(time.perf_counter() - started, 3),
        }
    )
    return completed.returncode in accepted_returncodes


def _write_receipt(
    path: Path,
    *,
    outline: Path,
    output: Path,
    qa_dir: Path,
    style_preset: str,
    style_resolution_basis: str,
    thresholds: tuple[float, float, float],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    passed = bool(records) and all(bool(record.get("accepted", False)) for record in records)
    completion = _completion_status(records, qa_dir)
    payload = {
        "schema_version": "quick-deck-finalization/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "outline": str(outline),
        "outline_sha256": _sha256(outline),
        "output": str(output),
        "output_exists": output.is_file(),
        "output_sha256": _sha256(output) if output.is_file() else "",
        "style_preset": style_preset,
        "style_resolution_basis": style_resolution_basis,
        "readability": {
            "min_body_pt": thresholds[0],
            "min_support_pt": thresholds[1],
            "min_metadata_pt": thresholds[2],
        },
        "qa_dir": str(qa_dir),
        "qa_report": str(qa_dir / "qa_report.json"),
        "contact_sheet": str(qa_dir / "visual_review" / "contact_sheet.jpg"),
        "total_duration_seconds": round(
            sum(float(record.get("duration_seconds", 0) or 0) for record in records),
            3,
        ),
        **completion,
        "stages": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--style-preset",
        default="auto",
        help="Preset name, or auto to honor outline.deck_style.style_preset and route only as fallback.",
    )
    parser.add_argument("--qa-dir", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--min-body-pt", type=float)
    parser.add_argument("--min-support-pt", type=float)
    parser.add_argument("--min-metadata-pt", type=float)
    parser.add_argument(
        "--strict-preflight-warnings",
        action="store_true",
        help="Treat preflight warnings as blocking. By default they are recorded and the hard QA gate decides.",
    )
    args = parser.parse_args()

    outline = args.outline.resolve()
    output = args.output.resolve()
    qa_dir = (args.qa_dir or output.parent / f"{output.stem}-qa").resolve()
    receipt_path = qa_dir / "finalize_receipt.json"
    records: list[dict[str, Any]] = []
    try:
        outline_payload = _load_outline(outline)
        thresholds = _thresholds(
            outline_payload,
            args.min_body_pt,
            args.min_support_pt,
            args.min_metadata_pt,
        )
        style_preset, style_resolution_basis = _resolve_style_preset(
            outline_payload,
            args.style_preset,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL Could not load outline: {exc}", file=sys.stderr)
        return 2

    node = shutil.which("node")
    if not node:
        print("FAIL Node.js is required", file=sys.stderr)
        return 2

    preflight_returncodes = (0,) if args.strict_preflight_warnings else (0, 1)
    stages = [
        (
            "preflight",
            [sys.executable, str(ROOT / "scripts" / "preflight.py"), "--outline", str(outline)],
            preflight_returncodes,
        ),
        (
            "build",
            [
                node,
                str(ROOT / "scripts" / "build_deck_pptxgenjs.js"),
                "--outline",
                str(outline),
                "--output",
                str(output),
                "--style-preset",
                style_preset,
                *(["--asset-root", str(args.asset_root.resolve())] if args.asset_root else []),
            ],
            (0,),
        ),
        (
            "qa",
            [
                sys.executable,
                str(ROOT / "scripts" / "qa_gate.py"),
                "--input",
                str(output),
                "--outline",
                str(outline),
                "--outdir",
                str(qa_dir),
                "--style-preset",
                style_preset,
                "--strict-geometry",
                "--fail-on-geometry-warnings",
                "--fail-on-whitespace-warnings",
                "--run-visual-review",
                "--fail-on-visual-review-warnings",
                "--fail-on-design-warnings",
                "--accessibility",
                "--strict-accessibility",
                "--accessibility-min-body-pt",
                str(thresholds[0]),
                "--accessibility-min-support-pt",
                str(thresholds[1]),
                "--accessibility-min-metadata-pt",
                str(thresholds[2]),
                "--skip-manual-review",
            ],
            (0,),
        ),
    ]

    for stage, command, accepted_returncodes in stages:
        if not _run(stage, command, records, accepted_returncodes=accepted_returncodes):
            receipt = _write_receipt(
                receipt_path,
                outline=outline,
                output=output,
                qa_dir=qa_dir,
                style_preset=style_preset,
                style_resolution_basis=style_resolution_basis,
                thresholds=thresholds,
                records=records,
            )
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return 1

    receipt = _write_receipt(
        receipt_path,
        outline=outline,
        output=output,
        qa_dir=qa_dir,
        style_preset=style_preset,
        style_resolution_basis=style_resolution_basis,
        thresholds=thresholds,
        records=records,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
