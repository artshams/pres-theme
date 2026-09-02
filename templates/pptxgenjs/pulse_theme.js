/*
 * Loads pulse/theme.json and turns it into a renderer preset.
 *
 * The point of this file is that pulse/theme.json is the only place a colour,
 * font, size or margin is written down. Designers edit that; nothing here
 * carries a value of its own, only the conversion.
 *
 * Two coordinate systems are involved. theme.json is written in the units a
 * designer reads off PowerPoint: inches on a 13.333 x 7.5in slide, and points
 * at that size. The renderer authors in a 10 x 5.625in space. Both are 16:9,
 * so the conversion is a single constant and the result is visually identical.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const THEME_PATH = path.join(__dirname, '..', '..', 'pulse', 'theme.json');

// theme.json inches -> renderer inches. 13.333 / 10.
const SCALE = 4 / 3;

const HEX = /^[0-9a-fA-F]{6}$/;

class ThemeError extends Error {}

function readTheme(themePath) {
  const file = themePath || THEME_PATH;
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch (err) {
    throw new ThemeError(`Не удалось прочитать ${file}: ${err.message}`);
  }
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new ThemeError(
      `${file} — некорректный JSON: ${err.message}\n` +
      'Частая причина: лишняя запятая перед закрывающей скобкой.',
    );
  }
}

/**
 * Validate the parts the renderer depends on, and say what is wrong in the
 * designer's own terms -- this runs behind `npm run pulse:check`.
 * Returns an array of human-readable problems; empty means the file is good.
 */
function validateTheme(theme) {
  const problems = [];
  const req = (obj, key, where) => {
    if (obj === undefined || obj === null || obj[key] === undefined) {
      problems.push(`${where}: нет обязательного ключа "${key}"`);
      return false;
    }
    return true;
  };

  if (!req(theme, 'colors', 'корень')) return problems;
  for (const key of ['ink', 'ink_muted', 'bg', 'surface', 'accent', 'line']) {
    if (!req(theme.colors, key, 'colors')) continue;
    const value = theme.colors[key];
    if (!HEX.test(String(value))) {
      problems.push(
        `colors.${key} = "${value}" — нужен HEX из шести символов без решётки, ` +
        'например 005AFE',
      );
    }
  }

  if (req(theme, 'fonts', 'корень')) {
    for (const key of ['heading', 'body']) {
      if (req(theme.fonts, key, 'fonts') && !String(theme.fonts[key]).trim()) {
        problems.push(`fonts.${key} пустой`);
      }
    }
  }

  if (req(theme, 'type_scale_pt', 'корень')) {
    for (const key of ['title', 'subtitle', 'body', 'secondary', 'caption', 'micro', 'hero']) {
      if (!req(theme.type_scale_pt, key, 'type_scale_pt')) continue;
      const value = Number(theme.type_scale_pt[key]);
      if (!Number.isFinite(value) || value <= 0) {
        problems.push(`type_scale_pt.${key} = "${theme.type_scale_pt[key]}" — нужно число больше нуля`);
      }
    }
    const scale = theme.type_scale_pt;
    const order = ['micro', 'caption', 'secondary', 'body', 'subtitle', 'title', 'hero'];
    for (let i = 1; i < order.length; i += 1) {
      const lo = Number(scale[order[i - 1]]);
      const hi = Number(scale[order[i]]);
      if (Number.isFinite(lo) && Number.isFinite(hi) && hi < lo) {
        problems.push(
          `type_scale_pt: "${order[i]}" (${hi}) меньше "${order[i - 1]}" (${lo}) — ` +
          'шкала должна расти от micro к hero',
        );
      }
    }
  }

  if (req(theme, 'grid_in', 'корень')) {
    for (const key of ['margin', 'title_y', 'title_h', 'subtitle_y', 'subtitle_h',
      'content_y', 'content_bottom', 'gutter']) {
      if (!req(theme.grid_in, key, 'grid_in')) continue;
      const value = Number(theme.grid_in[key]);
      if (!Number.isFinite(value) || value < 0) {
        problems.push(`grid_in.${key} = "${theme.grid_in[key]}" — нужно число не меньше нуля (дюймы)`);
      }
    }
    const g = theme.grid_in;
    const width = Number((theme.slide && theme.slide.width_in) || 13.333);
    if (Number(g.margin) * 2 >= width) {
      problems.push(`grid_in.margin = ${g.margin} — поля съедают всю ширину слайда`);
    }
    if (Number(g.content_bottom) <= Number(g.content_y)) {
      problems.push(
        `grid_in.content_bottom (${g.content_bottom}) должен быть больше content_y (${g.content_y})`,
      );
    }
    const headerBottom = Number(g.subtitle_y) + Number(g.subtitle_h);
    if (Number(g.title_y) + Number(g.title_h) > Number(g.subtitle_y)) {
      problems.push(
        `строка заголовка (до ${Number(g.title_y) + Number(g.title_h)}) налезает ` +
        `на подзаголовок (начинается с ${g.subtitle_y})`,
      );
    }
    if (headerBottom > Number(g.content_y)) {
      problems.push(
        `шапка (до ${headerBottom}) налезает на контент (начинается с ${g.content_y})`,
      );
    }
  }

  if (theme.charts && theme.charts.series !== undefined) {
    if (!Array.isArray(theme.charts.series) || !theme.charts.series.length) {
      problems.push('charts.series должен быть непустым списком цветов');
    } else {
      theme.charts.series.forEach((value, i) => {
        if (!HEX.test(String(value))) {
          problems.push(`charts.series[${i}] = "${value}" — нужен HEX из шести символов`);
        }
      });
    }
  }

  if (theme.limits) {
    const l = theme.limits;
    if (Number(l.blocks_max) < Number(l.blocks_min)) {
      problems.push('limits.blocks_max меньше limits.blocks_min');
    }
    if (Number(l.donut_segments_max) < Number(l.donut_segments_min)) {
      problems.push('limits.donut_segments_max меньше limits.donut_segments_min');
    }
  }

  return problems;
}

function inches(value) {
  return Number(value) / SCALE;
}

function points(value) {
  return Math.round((Number(value) / SCALE) * 10) / 10;
}

/**
 * Anchors mapping the house type scale onto this theme's steps. The renderer
 * sets font sizes as literals in ~170 places, so a single ramp applied in
 * textOpts() is what moves the whole deck onto the theme's scale while keeping
 * relative hierarchy inside a slide.
 */
function typeRamp(scale) {
  return [
    [7, points(scale.micro)],
    [9, points(scale.caption)],
    [12, points(scale.body)],
    [16, points(scale.subtitle)],
    [26, points(scale.title)],
    [40, points(scale.hero)],
  ];
}

function buildPreset(theme) {
  const c = theme.colors;
  const g = theme.grid_in;
  const t = theme.type_scale_pt;
  const charts = theme.charts || {};

  return {
    bg: c.bg,
    // Kept for presets that invert; this theme never does (light_only below).
    bg_dark: c.ink,
    surface: c.surface,
    surface_strong: c.surface_strong || c.surface,
    text: c.ink,
    text_muted: c.ink_muted,
    text_soft: c.ink_soft || c.ink_muted,
    accent_primary: c.accent,
    accent_secondary: c.accent_bright || c.accent,
    line: c.line,
    font_heading: theme.fonts.heading,
    font_body: theme.fonts.body,

    // Not one slide in the source template has a dark or full-bleed
    // background, so panels tint rather than invert.
    light_only: true,
    square_plates: (theme.plates || {}).square_corners !== false,
    plate_shadow: (theme.plates || {}).shadow === true,

    type_ramp: typeRamp(t),
    readability_contract: {
      min_title_pt: points(t.title),
      min_body_pt: points(t.secondary),
      min_caption_pt: points(t.micro),
      min_support_pt: points(t.secondary),
      min_metadata_pt: points(t.micro),
    },

    content_floor: inches(g.content_bottom),

    chart_series: Array.isArray(charts.series) ? charts.series.slice() : undefined,
    chart_show_value: charts.show_value,
    chart_show_legend: charts.show_legend,
    chart_surface: charts.surface,
    chart_frameless: charts.frameless,

    labels: Object.assign({}, theme.labels),

    // Geometry the pulse renderers read directly, already in renderer inches.
    pulse_grid: {
      margin: inches(g.margin),
      titleY: inches(g.title_y),
      titleH: inches(g.title_h),
      subtitleY: inches(g.subtitle_y),
      subtitleH: inches(g.subtitle_h),
      contentY: inches(g.content_y),
      contentBottom: inches(g.content_bottom),
      gutter: inches(g.gutter),
      blockGap: inches(g.block_gap === undefined ? 0.22 : g.block_gap),
      contentW: inches(Number((theme.slide && theme.slide.width_in) || 13.333) - Number(g.margin) * 2),
      footerY: inches((theme.footer_in && theme.footer_in.y) || 6.74),
      footerH: inches((theme.footer_in && theme.footer_in.height) || 0.42),
      pageNumX: inches((theme.footer_in && theme.footer_in.page_number_x) || 10.88),
      pageNumW: inches((theme.footer_in && theme.footer_in.page_number_w) || 1.77),
    },
    pulse_type: {
      title: points(t.title),
      subtitle: points(t.subtitle),
      body: points(t.body),
      secondary: points(t.secondary),
      caption: points(t.caption),
      micro: points(t.micro),
      hero: points(t.hero),
    },
    pulse_limits: Object.assign({}, theme.limits),
  };
}

let cached = null;

function loadPulsePreset(themePath) {
  if (cached && !themePath) return cached;
  const theme = readTheme(themePath);
  const problems = validateTheme(theme);
  if (problems.length) {
    throw new ThemeError(
      'pulse/theme.json содержит ошибки:\n  - ' + problems.join('\n  - ') +
      '\nЗапустите `npm run pulse:check` для подробностей.',
    );
  }
  const preset = buildPreset(theme);
  if (!themePath) cached = preset;
  return preset;
}

module.exports = {
  THEME_PATH,
  SCALE,
  ThemeError,
  readTheme,
  validateTheme,
  buildPreset,
  loadPulsePreset,
};
