'use strict';
/*
 * Outline slot-alias canonicalizer.
 *
 * The renderer reads a fixed set of payload keys. Anything else is dropped
 * silently, which is exactly what "slide has a title but no body" looks like:
 *
 *   {"content": [...]}  -> title + page number only
 *   {"points":  [...]}  -> title + page number only
 *   {"items":   [...]}  -> title + page number only
 *   {"text":    "..."}  -> title + page number only
 *   {"body":    [...]}  -> one comma-joined paragraph
 *   cards[].description -> card headings render, card bodies vanish
 *   {"stats":   [...]}  -> "No facts provided."
 *
 * This maps every common alias an LLM emits onto the key the renderer reads.
 * It only fills keys that are missing or empty -- a correct outline passes
 * through untouched.
 */

function firstText(source, keys) {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
    if (typeof value === 'number') return String(value);
  }
  return '';
}

function toLine(item) {
  if (item === null || item === undefined) return '';
  if (typeof item === 'string') return item.trim();
  if (typeof item === 'number') return String(item);
  if (typeof item === 'object') {
    return firstText(item, ['text', 'title', 'label', 'body', 'name', 'value']);
  }
  return '';
}

function firstList(source, keys) {
  for (const key of keys) {
    const value = source[key];
    if (Array.isArray(value)) {
      const lines = value.map(toLine).filter(Boolean);
      if (lines.length) return lines;
    }
  }
  return null;
}

function hasItems(value) {
  return Array.isArray(value) && value.length > 0;
}

const BULLET_ALIASES = ['bullets', 'content', 'points', 'items', 'body', 'text',
  'key_points', 'keyPoints', 'takeaways', 'details', 'lines'];
const FACT_ALIASES = ['facts', 'stats', 'metrics', 'kpis', 'numbers', 'figures'];
const HIGHLIGHT_ALIASES = ['highlights', 'callouts', 'callout', 'key_takeaways'];
const SOURCE_ALIASES = ['sources', 'refs', 'references', 'citations'];

function normalizeFact(raw) {
  if (!raw || typeof raw !== 'object') {
    const line = toLine(raw);
    return line ? { value: line, label: '' } : null;
  }
  const value = firstText(raw, ['value', 'number', 'figure', 'metric', 'stat', 'amount']);
  const label = firstText(raw, ['label', 'name', 'title', 'caption', 'description', 'text']);
  if (!value && !label) return null;
  return Object.assign({}, raw, { value: value || label, label: value ? label : '' });
}

function normalizeCard(raw) {
  if (!raw || typeof raw !== 'object') {
    const line = toLine(raw);
    return line ? { title: line, body: '' } : null;
  }
  const title = firstText(raw, ['title', 'heading', 'name', 'label']);
  const body = firstText(raw, ['body', 'description', 'text', 'detail', 'summary', 'subtitle', 'content']);
  if (!title && !body) return null;
  return Object.assign({}, raw, { title: title || body, body: title ? body : '' });
}

function normalizeMilestone(raw) {
  if (!raw || typeof raw !== 'object') {
    const line = toLine(raw);
    return line ? { label: '', title: line, body: '' } : null;
  }
  return Object.assign({}, raw, {
    label: firstText(raw, ['label', 'date', 'period', 'when', 'phase', 'step']),
    title: firstText(raw, ['title', 'heading', 'name', 'milestone']),
    body: firstText(raw, ['body', 'description', 'text', 'detail', 'summary']),
  });
}

function normalizeQuadrant(raw) {
  if (!raw || typeof raw !== 'object') {
    const line = toLine(raw);
    return line ? { title: line, body: '' } : null;
  }
  return Object.assign({}, raw, {
    title: firstText(raw, ['title', 'heading', 'name', 'label']),
    body: firstText(raw, ['body', 'description', 'text', 'detail', 'summary']),
  });
}

function normalizeSide(raw) {
  if (!raw || typeof raw !== 'object') return raw;
  const out = Object.assign({}, raw);
  out.title = firstText(raw, ['title', 'heading', 'name', 'label']);
  if (!hasItems(out.body)) {
    const lines = firstList(raw, ['body', 'bullets', 'points', 'items', 'content', 'lines']);
    if (lines) {
      out.body = lines;
    } else {
      const single = firstText(raw, ['body', 'text', 'description']);
      if (single) out.body = [single];
    }
  } else {
    out.body = out.body.map(toLine).filter(Boolean);
  }
  return out;
}

/** Mutates `slide` in place. Returns a list of human-readable repairs. */
function applySlotAliases(slide) {
  if (!slide || typeof slide !== 'object') return [];
  const repairs = [];
  const note = (msg) => repairs.push(msg);

  if (!slide.subtitle) {
    const sub = firstText(slide, ['subtitle', 'sub_title', 'kicker', 'eyebrow']);
    if (sub) slide.subtitle = sub;
  }

  // bullets -- the single biggest source of blank slides.
  if (!hasItems(slide.bullets)) {
    for (const key of BULLET_ALIASES) {
      const value = slide[key];
      if (!Array.isArray(value)) continue;
      const lines = value.map(toLine).filter(Boolean);
      if (!lines.length) continue;
      slide.bullets = lines;
      // `body` is also read on its own as a prose paragraph; leaving the array
      // in place renders it a second time as one comma-joined line.
      if (key === 'body') delete slide.body;
      if (key !== 'bullets') note(key + '[] -> bullets[]');
      break;
    }
  } else {
    slide.bullets = slide.bullets.map(toLine).filter(Boolean);
  }
  // Prose with no bullets still deserves to render.
  if (!hasItems(slide.bullets) && !slide.body) {
    const prose = firstText(slide, ['text', 'summary', 'narrative', 'description']);
    if (prose) {
      slide.body = prose;
      note('text -> body');
    }
  }

  if (!hasItems(slide.facts)) {
    for (const key of FACT_ALIASES) {
      if (!hasItems(slide[key])) continue;
      const facts = slide[key].map(normalizeFact).filter(Boolean);
      if (!facts.length) continue;
      slide.facts = facts;
      if (key !== 'facts') note(key + '[] -> facts[]');
      break;
    }
  } else {
    slide.facts = slide.facts.map(normalizeFact).filter(Boolean);
  }

  if (hasItems(slide.cards)) {
    const before = JSON.stringify(slide.cards);
    slide.cards = slide.cards.map(normalizeCard).filter(Boolean);
    if (JSON.stringify(slide.cards) !== before) note('cards[] slot names repaired');
  }
  if (hasItems(slide.milestones)) {
    const before = JSON.stringify(slide.milestones);
    slide.milestones = slide.milestones.map(normalizeMilestone).filter(Boolean);
    if (JSON.stringify(slide.milestones) !== before) note('milestones[] slot names repaired');
  }
  if (hasItems(slide.quadrants)) {
    const before = JSON.stringify(slide.quadrants);
    slide.quadrants = slide.quadrants.map(normalizeQuadrant).filter(Boolean);
    if (JSON.stringify(slide.quadrants) !== before) note('quadrants[] slot names repaired');
  }
  for (const side of ['left', 'right']) {
    if (slide[side] && typeof slide[side] === 'object') {
      const before = JSON.stringify(slide[side]);
      slide[side] = normalizeSide(slide[side]);
      if (JSON.stringify(slide[side]) !== before) note(side + '{} slot names repaired');
    }
  }

  if (!hasItems(slide.headers) && hasItems(slide.columns)) {
    slide.headers = slide.columns.map(toLine).filter(Boolean);
    note('columns[] -> headers[]');
  }
  if (!hasItems(slide.rows) && hasItems(slide.data) && Array.isArray(slide.data[0])) {
    slide.rows = slide.data;
    note('data[] -> rows[]');
  }

  if (!hasItems(slide.highlights)) {
    const lines = firstList(slide, HIGHLIGHT_ALIASES);
    if (lines) {
      slide.highlights = lines;
      note('callouts -> highlights[]');
    }
  }
  if (!hasItems(slide.sources)) {
    const lines = firstList(slide, SOURCE_ALIASES);
    if (lines) slide.sources = lines;
  }
  // kpi-hero reads flat value/label/context, not facts[], so the natural way
  // to write a hero metric -- one entry in facts[], the same shape every other
  // stat variant takes -- rendered as a bare "?" with no label.
  if (String(slide.variant || '').trim().toLowerCase() === 'kpi-hero'
      && !slide.value && hasItems(slide.facts)) {
    const first = slide.facts[0];
    if (first && typeof first === 'object') {
      if (first.value !== undefined) slide.value = String(first.value);
      if (!slide.label && first.label) slide.label = String(first.label);
      if (!slide.context && (first.caption || first.context)) {
        slide.context = String(first.caption || first.context);
      }
      repairs.push('facts[0] -> value/label (kpi-hero)');
    }
  }
  if (!slide.verdict) {
    const verdict = firstText(slide, ['verdict', 'conclusion', 'takeaway', 'so_what']);
    if (verdict) slide.verdict = verdict;
  }
  return repairs;
}

/** True when nothing on this slide would reach the canvas below the header. */
function isPayloadEmpty(slide) {
  if (!slide || typeof slide !== 'object') return true;
  const type = String(slide.type || 'content').trim().toLowerCase();
  if (type === 'title' || type === 'section') return false;
  const listKeys = ['bullets', 'facts', 'cards', 'milestones', 'quadrants', 'rows',
    'headers', 'tables', 'sources', 'refs', 'highlights', 'figures'];
  if (listKeys.some((key) => hasItems(slide[key]))) return false;
  if (slide.left || slide.right || slide.table || slide.chart || slide.chart_data) return false;
  if (slide.assets && typeof slide.assets === 'object' && Object.keys(slide.assets).length) return false;
  return !firstText(slide, ['body', 'message', 'summary_callout', 'verdict', 'text']);
}

module.exports = { applySlotAliases, isPayloadEmpty };
