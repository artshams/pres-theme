---
name: presentation-skill
description: Build, edit, redesign, render, and verify polished editable PowerPoint `.pptx` decks from a prompt, structured JSON, local data, or a saved workspace. Use for scientific, lab, clinical, consulting, board, investor, editorial, policy, and operational presentations where narrative, visual hierarchy, readability, and reproducibility matter.
---

# Presentation Skill

Create editable PowerPoint decks from source. The model owns the argument,
evidence, and design judgment; the skill owns deterministic rendering and QA.

## Core Contract

- Treat `outline.json`, planning files, data, and figure scripts as source.
- Build with repository commands. Do not write one-off deck generators or patch
  a generated PPTX when source exists.
- Keep text, charts, tables, diagrams, and figures editable where practical.
- Use the selected grammar as a design system, not a fixed slide sequence.
- Fix source and rebuild until geometry, readability, placeholders, and rendered
  visual review pass.
- Do not copy proprietary slides, logos, wording, or distinctive geometry.

Run commands from this skill directory. Use absolute paths for deck files kept
elsewhere. Check the pinned runtime once:

```bash
npm run doctor
```

If required, run `npm run setup:python` once. Do not substitute arbitrary Python
or Office application workflows for the supported runtime.

## Choose A Route

### Quick Deck

Use for a one-off 5-10 slide deck.

1. Emit a small model-ready brief:

```bash
python3 scripts/present.py brief \
  --topic "Deck topic" \
  --prompt "Original request" \
  --slides 7 \
  --profile auto \
  --output quick_deck_agent_brief.json
```

2. Read the brief and author `outline.json`. Select one bounded route candidate,
   then adapt its starter sequence to the actual evidence. `role` names the
   editable structure; `slide_intent` names the story job.

3. Build, render, and hard-gate it:

```bash
python3 scripts/present.py finalize \
  --outline /absolute/path/outline.json \
  --output /absolute/path/output.pptx \
  --qa-dir /absolute/path/qa
```

Read `finalize_receipt.json`, `qa_report.json`, and the contact sheet. Repair
source once, then rerun. Warning-only preflight findings are recorded; outline
errors and final QA findings remain blocking.

### Saved Workspace

Use for decks that will be rebuilt, audited, or iterated:

```bash
python3 scripts/present.py init \
  --workspace /absolute/path/deck-workspace \
  --title "Deck title" \
  --prompt "Original request" \
  --profile auto \
  --style-preset auto

python3 scripts/present.py build \
  --workspace /absolute/path/deck-workspace \
  --draft

python3 scripts/present.py build \
  --workspace /absolute/path/deck-workspace
```

The default workspace is compact. Add `--audit-packet` to `present.py init` only
when a full intake/multi-agent recovery ledger is useful.

Author or update:

- `design_brief.json`: audience, style, readability, and QA contract
- `content_plan.json`: thesis, narrative arc, and slide roles
- `evidence_plan.json`: claims, sources, and chart candidates
- `asset_plan.json`: figures, tables, charts, images, and icons
- `outline.json`: renderable slide source
- `notes.md`: assumptions and unresolved decisions

The build also writes deterministic `build/deck_ir.json`, a coordinate-free
semantic representation with stable object IDs, evidence links, reading order,
and editability metadata. Renderer scripts continue to own coordinates.

### Existing PPTX

When source exists, edit source. For a standalone PPTX, inspect it first:

```bash
python3 scripts/python_runtime.py scripts/reference_deck.py inspect \
  --input /absolute/path/input.pptx \
  --output /absolute/path/reference_deck_manifest.json
```

Use a typed `reference_deck_patch_v1` for narrow text or alt-text edits. Use
`scripts/extract_pptx_style.py` plus a fresh workspace for a source-first
redesign inspired by an existing deck. Read `references/editing.md` before
editing package internals.

## Model Profiles

Profiles change orchestration, not the final quality definition:

- `fast` / `luna`: one deterministic grammar, no scouts, render-free draft,
  then one final render.
- `balanced` / `terra`: two bounded grammar candidates, at most one useful
  scout, one focused repair loop.
- `quality-first` / `sol`: three bounded grammar candidates, optional design
  and data scouts, full rendered review for difficult or high-stakes work.
- `auto`: quality-first for high-stakes/evidence-heavy work, fast for explicit
  rough drafts, balanced otherwise.

Use the smallest profile that can pass the artifact gates. Stronger models may
choose and mix bounded treatments dynamically; they should not receive the full
corpus or arbitrary coordinates. If uncertain, use the deterministic fallback
recorded in the brief.

## Design Decisions

Choose one primary grammar from topic, audience, evidence shape, and density.
The eight structural grammar families own distinct title, section, evidence,
comparison, data, decision, and references systems. Presets contribute palette,
type, and treatment vocabulary; they are not static templates.

Maintain these invariants:

- One dominant idea and a clear reading path per slide.
- Every content slide has a visual or evidence anchor: chart, table, figure,
  image, KPI, timeline, matrix, or structured comparison.
- No centered body copy and no sequence dominated by bullet-only slides.
- Vary composition with the argument; avoid repeating one card grid, border,
  title treatment, or two-column shell.
- Use `header_variant: auto` with a stable seed for reproducible heading,
  top-line, bottom-line, no-line, and compact report treatments.
- Keep source text and page numbers in the reserved footer region; do not let
  footer chrome compete with the evidence.
- Use `role_layout_variant: primary | alternate | dense` for bounded structural
  variation. Do not place arbitrary coordinates in `outline.json`.
- Keep one grammar coherent across the deck. Borrow at most two isolated
  treatments when the content shape benefits.
- For a visual A/B, freeze one outline and vary only `deck_style`; this exposes
  real grammar differences without letting content changes bias the comparison.
- Treat auxiliary title-stage anchors as content slots, not decoration. Leave
  them absent unless the outline supplies a value or asset.

Readable defaults for ordinary delivery:

- titles at least 28 pt;
- body text at least 16 pt;
- supporting subtitles at least 13 pt;
- captions, sources, and metadata at least 9 pt;
- no more than two title lines;
- shorten, split, or convert prose into evidence objects before shrinking.

Use actual content to balance white space. Sparse slides need a stronger anchor;
dense slides need fewer words or a more suitable structure, not smaller type.

For structural routing details, read
`references/composition_grammar_catalog.md`. For screenshot/template
inspiration, read `references/style_reference_catalog.md`. The descriptor corpus
is retrieval memory; load only the selected record or distilled atoms.

## Data And Figures

For local CSV, TSV, XLSX, or JSON evidence, keep generated artifacts
reproducible:

```bash
python3 scripts/python_runtime.py scripts/scaffold_figure_artifacts.py \
  --workspace /absolute/path/deck-workspace \
  --run \
  --bind-outline
```

Preserve source fingerprints, figure scripts, chart/table JSON, artifact
manifests, slide bindings, and rebuild commands. Solve whitespace and label
readability in the figure script before placing the figure. Stage sourced images
through `asset_plan.json` with attribution. Generated imagery must remain
optional and carry prompt/model/purpose metadata.

Read `references/reproducible_workflow.md` only when the deck contains computed
evidence or generated figures.

## QA And Delivery

A deliverable deck must pass:

1. planning and outline preflight;
2. geometry, overflow, overlap, density, and whitespace checks;
3. rendered contact-sheet and slide-level visual review;
4. placeholder-text checks;
5. accessibility checks when required;
6. final delivery readiness.

Visual review should search for defects: clipped text, weak contrast, awkward
empty regions, crowded edges, tiny labels, inconsistent alignment, repeated
grammar, and unreadable sources. Fix source and rebuild.

If rendering is unavailable in the execution environment, preserve the built
deck and static QA report, record the deferred render stage in the receipt, and
do not probe unrelated Office apps.

## Progressive References

Read only what the current task needs:

- `DESIGN.md`: compact design contract
- `references/model_adaptive_workflow.md`: profile selection and context budgets
- `references/deck_workspace_mode.md`: persistent workspace workflow
- `references/outline_schema.md`: schema or preflight failures
- `references/editing.md`: existing PPTX edits
- `references/reproducible_workflow.md`: data and figure artifacts
- `references/style_reference_catalog.md`: inspiration and screenshot matching
- `references/composition_grammar_catalog.md`: structural grammar routing
- `references/pptxgenjs.md`: renderer development only
- `references/visual_qa_prompt.md`: independent rendered review
- `references/benchmark_protocol.md`: fair comparison or superiority claims

Do not preload all references, presets, or corpus records.

## Development

After changing runtime behavior, run:

```bash
npm run check:python
npm run check:node
npm run check:present
npm run check:focused
```

Visual changes require a rendered proof. Showcase decks alone do not justify a
claim that this skill outperforms another generator; use the frozen benchmark
protocol and report only supported results.
