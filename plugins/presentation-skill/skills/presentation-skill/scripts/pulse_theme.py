#!/usr/bin/env python3
"""Reads pulse/theme.json for the Python half of the skill.

The JS renderer has the same loader in templates/pptxgenjs/pulse_theme.js.
Both read the one file a designer edits, so neither side carries a colour,
font, size or margin of its own.

Run as a script to validate the file:

    python scripts/pulse_theme.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
THEME_PATH = ROOT / "pulse" / "theme.json"

# theme.json inches -> renderer inches. The theme is written in the units a
# designer reads off PowerPoint (13.333in slide); the renderer authors at 10in.
SCALE = 4 / 3

HEX = re.compile(r"^[0-9a-fA-F]{6}$")

REQUIRED_COLORS = ("ink", "ink_muted", "bg", "surface", "accent", "line")
TYPE_ORDER = ("micro", "caption", "secondary", "body", "subtitle", "title", "hero")
REQUIRED_GRID = (
    "margin", "title_y", "title_h", "subtitle_y", "subtitle_h",
    "content_y", "content_bottom", "gutter",
)


class ThemeError(Exception):
    pass


def read_theme(path: Path | None = None) -> dict[str, Any]:
    file = Path(path) if path else THEME_PATH
    try:
        raw = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ThemeError(f"Не удалось прочитать {file}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThemeError(
            f"{file} — некорректный JSON: {exc}\n"
            "Частая причина: лишняя запятая перед закрывающей скобкой."
        ) from exc


def validate_theme(theme: dict[str, Any]) -> list[str]:
    """Return human-readable problems; empty list means the file is good."""
    problems: list[str] = []

    colors = theme.get("colors")
    if not isinstance(colors, dict):
        problems.append('корень: нет обязательного ключа "colors"')
    else:
        for key in REQUIRED_COLORS:
            if key not in colors:
                problems.append(f'colors: нет обязательного ключа "{key}"')
            elif not HEX.match(str(colors[key])):
                problems.append(
                    f'colors.{key} = "{colors[key]}" — нужен HEX из шести '
                    "символов без решётки, например 005AFE"
                )

    fonts = theme.get("fonts")
    if not isinstance(fonts, dict):
        problems.append('корень: нет обязательного ключа "fonts"')
    else:
        for key in ("heading", "body"):
            if not str(fonts.get(key, "")).strip():
                problems.append(f"fonts.{key} пустой или отсутствует")

    scale = theme.get("type_scale_pt")
    if not isinstance(scale, dict):
        problems.append('корень: нет обязательного ключа "type_scale_pt"')
    else:
        for key in TYPE_ORDER:
            if key not in scale:
                problems.append(f'type_scale_pt: нет обязательного ключа "{key}"')
                continue
            try:
                if float(scale[key]) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(
                    f'type_scale_pt.{key} = "{scale[key]}" — нужно число больше нуля'
                )
        for lo_key, hi_key in zip(TYPE_ORDER, TYPE_ORDER[1:]):
            try:
                lo, hi = float(scale[lo_key]), float(scale[hi_key])
            except (KeyError, TypeError, ValueError):
                continue
            if hi < lo:
                problems.append(
                    f'type_scale_pt: "{hi_key}" ({hi}) меньше "{lo_key}" ({lo}) — '
                    "шкала должна расти от micro к hero"
                )

    grid = theme.get("grid_in")
    if not isinstance(grid, dict):
        problems.append('корень: нет обязательного ключа "grid_in"')
    else:
        for key in REQUIRED_GRID:
            if key not in grid:
                problems.append(f'grid_in: нет обязательного ключа "{key}"')
                continue
            try:
                if float(grid[key]) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                problems.append(
                    f'grid_in.{key} = "{grid[key]}" — нужно число не меньше нуля (дюймы)'
                )
        try:
            width = float(theme.get("slide", {}).get("width_in", 13.333))
            if float(grid["margin"]) * 2 >= width:
                problems.append(
                    f'grid_in.margin = {grid["margin"]} — поля съедают всю ширину слайда'
                )
            if float(grid["content_bottom"]) <= float(grid["content_y"]):
                problems.append(
                    f'grid_in.content_bottom ({grid["content_bottom"]}) должен быть '
                    f'больше content_y ({grid["content_y"]})'
                )
            header_bottom = float(grid["subtitle_y"]) + float(grid["subtitle_h"])
            if float(grid["title_y"]) + float(grid["title_h"]) > float(grid["subtitle_y"]):
                problems.append("строка заголовка налезает на подзаголовок")
            if header_bottom > float(grid["content_y"]):
                problems.append(
                    f"шапка (до {header_bottom}) налезает на контент "
                    f'(начинается с {grid["content_y"]})'
                )
        except (KeyError, TypeError, ValueError):
            pass

    charts = theme.get("charts")
    if isinstance(charts, dict) and "series" in charts:
        series = charts["series"]
        if not isinstance(series, list) or not series:
            problems.append("charts.series должен быть непустым списком цветов")
        else:
            for i, value in enumerate(series):
                if not HEX.match(str(value)):
                    problems.append(
                        f'charts.series[{i}] = "{value}" — нужен HEX из шести символов'
                    )

    limits = theme.get("limits")
    if isinstance(limits, dict):
        try:
            if float(limits["blocks_max"]) < float(limits["blocks_min"]):
                problems.append("limits.blocks_max меньше limits.blocks_min")
        except (KeyError, TypeError, ValueError):
            pass
        try:
            if float(limits["donut_segments_max"]) < float(limits["donut_segments_min"]):
                problems.append("limits.donut_segments_max меньше limits.donut_segments_min")
        except (KeyError, TypeError, ValueError):
            pass

    return problems


def load_theme(path: Path | None = None) -> dict[str, Any]:
    """Read and validate; raises ThemeError listing every problem found."""
    theme = read_theme(path)
    problems = validate_theme(theme)
    if problems:
        raise ThemeError(
            "pulse/theme.json содержит ошибки:\n  - " + "\n  - ".join(problems)
        )
    return theme


def points(value: Any) -> float:
    """A theme point size in the renderer's own point space."""
    return round(float(value) / SCALE, 1)


def inches(value: Any) -> float:
    return float(value) / SCALE


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка pulse/theme.json")
    parser.add_argument("--check", action="store_true", help="проверить файл и выйти")
    parser.add_argument("--path", help="путь к theme.json (по умолчанию pulse/theme.json)")
    args = parser.parse_args()

    try:
        theme = read_theme(Path(args.path) if args.path else None)
    except ThemeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    problems = validate_theme(theme)
    if problems:
        print("pulse/theme.json — найдены ошибки:")
        for problem in problems:
            print(f"  - {problem}")
        print("\nИсправьте их и запустите проверку снова.")
        return 1

    scale = theme["type_scale_pt"]
    grid = theme["grid_in"]
    print("pulse/theme.json — ошибок нет.")
    print(f"  тема      {theme.get('name', 'pulse-library')}")
    print(f"  шрифты    {theme['fonts']['heading']} / {theme['fonts']['body']}")
    print(f"  текст     #{theme['colors']['ink']}   акцент #{theme['colors']['accent']}")
    print(f"  подложка  #{theme['colors']['surface']}   линии #{theme['colors']['line']}")
    print(
        "  кегли     "
        + ", ".join(f"{k} {scale[k]}pt" for k in TYPE_ORDER if k in scale)
    )
    print(
        f"  сетка     поля {grid['margin']}\", заголовок {grid['title_y']}\", "
        f"контент {grid['content_y']}–{grid['content_bottom']}\""
    )
    if isinstance(theme.get("charts"), dict):
        series = theme["charts"].get("series", [])
        print(f"  графики   {len(series)} цветов серий, подписи "
              f"{'вкл' if theme['charts'].get('show_value') else 'выкл'}, "
              f"легенда {'вкл' if theme['charts'].get('show_legend') else 'выкл'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
