import { CurriculumFile, CourseInput, RequirementInput, ArrowRoute, Point, LayoutData, ColumnLayout, CardRect, RouteData, RenderOptions, LinkRenderStyle, CategoryInput } from '../types';
import { CARD_WIDTH, COL_HEADER_H, HEADER_H, PAGE_MARGIN } from '../layout';

// ─── Ponto de entrada ─────────────────────────────────────────────────────────

export function renderHtml(
  data: CurriculumFile,
  layout: LayoutData,
  routes: RouteData,
  options: RenderOptions = { linkStyle: 'paths' }
): string {
  const courseMap    = new Map<string, CourseInput>(data.courses.map(c => [c.code, c]));
  const reqMap       = new Map<number, RequirementInput>(data.requirements.map((r, i) => [i, r]));
  const categories   = data.categories ?? [];
  const categoryMap  = new Map<string, CategoryInput>(categories.map(c => [c.id, c]));
  const uniqueTags   = Array.from(new Set(data.courses.flatMap(c => c.tags)));
  const creditReqMap = new Map<string, number>(
    data.requirements
      .filter(r => r.type === 'credit_requirement' && r.min_credits !== undefined)
      .map(r => [r.to, r.min_credits!])
  );
  const linkStyle = options.linkStyle;
  const useCategoryFill = data.display?.card_fill_style === 'category';

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(data.curriculum.name)}</title>
  <style>
${renderCss(uniqueTags, categories)}
  </style>
</head>
<body>
${renderHeader(data)}
<div class="matrix-wrapper">
  <div class="matrix-area" style="--matrix-base-w:${layout.canvasWidth}px; --matrix-base-h:${layout.canvasHeight}px;">
    <div class="matrix-canvas" style="width:${layout.canvasWidth}px; height:${layout.canvasHeight}px;">
      <div class="columns-row">
${layout.columns.map((col: ColumnLayout) => renderColumn(col, courseMap, creditReqMap, categoryMap, useCategoryFill)).join('\n')}
      </div>
      <svg class="arrows-layer link-style-${linkStyle}" width="${layout.canvasWidth}" height="${layout.canvasHeight}" aria-hidden="true">
${renderArrowDefs(linkStyle)}
${routes.arrows.map(a => renderArrow(a, reqMap, linkStyle)).join('\n')}
      </svg>
    </div>
  </div>
  <aside class="legend-panel">
${renderLegend(uniqueTags, linkStyle, categories)}
${renderCreditSummary(data.courses, uniqueTags)}
  </aside>
</div>
${renderPopup()}
<script>
${renderJs(data, layout, routes)}
</script>
</body>
</html>`;
}

// ─── Cabeçalho ───────────────────────────────────────────────────────────────

function renderHeader(data: CurriculumFile): string {
  return `<header class="course-header">
  <div class="course-title">${esc(data.curriculum.name)}</div>
  <div class="course-meta">${esc(data.curriculum.code)} &bull; desde ${esc(data.curriculum.availableSince)}</div>
</header>`;
}

// ─── Colunas e cartões ────────────────────────────────────────────────────────

function renderColumn(
  col: ColumnLayout,
  courseMap: Map<string, CourseInput>,
  creditReqMap: Map<string, number>,
  categoryMap: Map<string, CategoryInput>,
  useCategoryFill: boolean
): string {
  const roman = toRoman(col.level);
  const cards = col.cards.map((card: CardRect) => {
    const course = courseMap.get(card.courseCode)!;
    const minCredits = creditReqMap.get(card.courseCode);
    return renderCard(card, course, minCredits, categoryMap, useCategoryFill);
  }).join('\n');

  return `      <div class="level-column" data-level="${col.level}">
        <div class="col-header">
          <span class="col-roman">${roman}</span>
          <span class="col-credits">${col.totalCredits} créditos</span>
        </div>
        <div class="cards-area">
${cards}
        </div>
      </div>`;
}

function renderCard(
  card: CardRect,
  course: CourseInput,
  minCredits: number | undefined,
  categoryMap: Map<string, CategoryInput>,
  useCategoryFill: boolean
): string {
  const tags = course.tags.map(t => `<span class="tag tag-${esc(t)}">${esc(t)}</span>`).join('');
  const fillClass = resolveCategoryFillClass(course, categoryMap, useCategoryFill);
  const creditBadge = minCredits !== undefined
    ? `\n          <div class="credit-req-badge">${minCredits} CR</div>`
    : '';
  return `          <div class="card-wrapper">${creditBadge}
            <div class="course-card${fillClass}"
               id="card-${esc(course.code)}"
               data-code="${esc(course.code)}"
               tabindex="0"
               role="button"
               aria-label="${esc(course.name)}">
              <div class="card-body">
                <span class="card-name">${esc(course.name)}</span>
                <span class="card-credits">(${course.credits})</span>
              </div>
              <div class="card-footer">${tags}</div>
            </div>
          </div>`;
}

function resolveCategoryFillClass(
  course: CourseInput,
  categoryMap: Map<string, CategoryInput>,
  useCategoryFill: boolean
): string {
  if (!useCategoryFill) return '';
  if (!course.category) return '';
  const category = categoryMap.get(course.category);
  if (!category || !category.color) return '';
  return ` fill-category fill-${cssToken(category.id)}`;
}

// ─── Setas SVG ────────────────────────────────────────────────────────────────

function renderArrow(arrow: ArrowRoute, reqMap: Map<number, RequirementInput>, linkStyle: LinkRenderStyle): string {
  const req = reqMap.get(arrow.requirementIndex);
  const dashArray = arrowDash(arrow.type);
  const width = arrowStrokeWidth(arrow.type, linkStyle);
  const from = req?.from ?? '';
  const to   = req?.to   ?? '';

  let labelEl = '';
  if (arrow.label && arrow.points.length >= 2) {
    const mid = arrow.points[Math.floor(arrow.points.length / 2)];
    labelEl = `\n    <text class="arrow-label" x="${mid.x}" y="${mid.y - 4}">${esc(arrow.label)}</text>`;
  }

  if (linkStyle === 'arrows') {
    const pointsStr = arrow.points.map((p: Point) => `${p.x},${p.y}`).join(' ');
    return `    <g class="arrow-group"
       data-type="${arrow.type}"
       data-from="${esc(from)}"
       data-to="${esc(to)}">
      <polyline points="${pointsStr}"
      stroke-dasharray="${dashArray}"
      stroke-width="${width}"
      class="arrow-line"
      marker-end="url(#arrowhead)"/>
      ${labelEl}
    </g>`;
  }

  const pathD = sankeyPathFromPoints(arrow.points);
  return `    <g class="arrow-group"
       data-type="${arrow.type}"
       data-from="${esc(from)}"
       data-to="${esc(to)}">
      <path d="${pathD}"
            stroke-dasharray="${dashArray}"
            stroke-width="${width}"
            class="arrow-line"/>
      ${labelEl}
    </g>`;
}

function arrowDash(type: string): string {
  if (type === 'special')     return '8,4';
  if (type === 'corequisite') return '3,3';
  return 'none';
}

function arrowStrokeWidth(type: string, linkStyle: LinkRenderStyle): number {
  if (linkStyle === 'arrows') {
    if (type === 'corequisite') return 1.4;
    return 1.6;
  }
  if (type === 'special') return 5;
  if (type === 'corequisite') return 4;
  return 6;
}

function renderArrowDefs(linkStyle: LinkRenderStyle): string {
  if (linkStyle !== 'arrows') return '';
  return `      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6 Z" fill="#333"/>
        </marker>
      </defs>`;
}

function sankeyPathFromPoints(points: Point[]): string {
  if (points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  if (points.length === 2) return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;

  const radius = 12;
  let d = `M ${points[0].x} ${points[0].y}`;

  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const next = points[i + 1];

    const inDx = curr.x - prev.x;
    const inDy = curr.y - prev.y;
    const outDx = next.x - curr.x;
    const outDy = next.y - curr.y;

    const inLen = Math.hypot(inDx, inDy);
    const outLen = Math.hypot(outDx, outDy);
    if (inLen === 0 || outLen === 0) continue;

    const corner = Math.min(radius, inLen * 0.45, outLen * 0.45);

    const enterX = curr.x - (inDx / inLen) * corner;
    const enterY = curr.y - (inDy / inLen) * corner;
    const exitX = curr.x + (outDx / outLen) * corner;
    const exitY = curr.y + (outDy / outLen) * corner;

    d += ` L ${enterX} ${enterY}`;
    d += ` Q ${curr.x} ${curr.y} ${exitX} ${exitY}`;
  }

  const last = points[points.length - 1];
  d += ` L ${last.x} ${last.y}`;
  return d;
}

// ─── Popup de detalhes ────────────────────────────────────────────────────────

function renderPopup(): string {
  return `<div id="course-popup" class="popup" role="dialog" aria-modal="true" aria-labelledby="popup-name" hidden>
  <div class="popup-content">
    <button class="popup-close" aria-label="Fechar">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
    <div class="popup-header">
      <span id="popup-code" class="popup-code"></span>
      <h2 id="popup-name" class="popup-name"></h2>
      <div id="popup-tags" class="popup-tags"></div>
    </div>
    <div class="popup-body">
      <div class="popup-stats">
        <div class="popup-stat">
          <span class="popup-stat-value" id="popup-hours"></span>
          <span class="popup-stat-label">Carga horária</span>
        </div>
        <div class="popup-stat">
          <span class="popup-stat-value" id="popup-credits"></span>
          <span class="popup-stat-label">Créditos</span>
        </div>
      </div>
      <section class="popup-section">
        <h3 class="popup-section-title">Ementa</h3>
        <p id="popup-syllabus" class="popup-syllabus-text"></p>
      </section>
      <section class="popup-section">
        <h3 class="popup-section-title">Pré-requisitos</h3>
        <div id="popup-prereqs"></div>
      </section>
      <section class="popup-section">
        <h3 class="popup-section-title">Dependentes</h3>
        <div id="popup-dependents"></div>
      </section>
    </div>
  </div>
</div>`;
}

// ─── Legenda ──────────────────────────────────────────────────────────────────

function renderLegend(tags: string[], linkStyle: LinkRenderStyle, categories: CategoryInput[]): string {
  const tagItems = tags.map(t =>
    `      <dt><span class="tag tag-${esc(t)}">${esc(t)}</span></dt>\n      <dd>Disciplina ${esc(t)}</dd>`
  ).join('\n');

  const categoryItems = categories.map(category => {
    const styleAttr = category.color
      ? ` style="background:${escAttr(category.color)}; border-color:${escAttr(category.color)};"`
      : '';
    return `      <dt><span class="category-chip"${styleAttr}></span></dt>\n      <dd>${esc(category.name)}</dd>`;
  }).join('\n');

  const categorySection = categoryItems
    ? `\n      <dt class="legend-subtitle">Eixos</dt>\n      <dd class="legend-subtitle-spacer"></dd>\n${categoryItems}`
    : '';

  const prereqShape = linkStyle === 'arrows'
    ? `<svg width="60" height="14"><defs><marker id="arrowhead-legend-1" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#1a3a6b" stroke-width="1.6" marker-end="url(#arrowhead-legend-1)"/></svg>`
    : `<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#1a3a6b" stroke-width="6" fill="none" stroke-linecap="round"/></svg>`;

  const specialShape = linkStyle === 'arrows'
    ? `<svg width="60" height="14"><defs><marker id="arrowhead-legend-2" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#b45309" stroke-width="1.6" stroke-dasharray="8,4" marker-end="url(#arrowhead-legend-2)"/></svg>`
    : `<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#b45309" stroke-width="5" fill="none" stroke-linecap="round" stroke-dasharray="8,4"/></svg>`;

  const coreqShape = linkStyle === 'arrows'
    ? `<svg width="60" height="14"><defs><marker id="arrowhead-legend-3" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#475569" stroke-width="1.4" stroke-dasharray="3,3" marker-end="url(#arrowhead-legend-3)"/></svg>`
    : `<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#475569" stroke-width="4" fill="none" stroke-linecap="round" stroke-dasharray="3,3"/></svg>`;

  return `    <h2 class="legend-title">Legenda</h2>
    <dl class="legend-list">
      <dt>${prereqShape}</dt>
      <dd>Pré-requisito</dd>
      <dt>${specialShape}</dt>
      <dd>Pré-requisito especial (RE)</dd>
      <dt>${coreqShape}</dt>
      <dd>Co-requisito</dd>
      <dt><span class="credit-req-badge">XX CR</span></dt>
      <dd>Requisito de créditos mínimos</dd>
    ${categorySection}
${tagItems}
    </dl>
    <div class="legend-toggle">
      <label>
        <input type="checkbox" id="toggle-arrows">
        Exibir setas de pré-requisito
      </label>
    </div>
    `;
}

// ─── Totalizador de créditos ────────────────────────────────────────────────

function renderCreditSummary(courses: CourseInput[], uniqueTags: string[]): string {
  const totalCredits = courses.reduce((sum, c) => sum + c.credits, 0);

  const tagRows = uniqueTags.map(tag => {
    const credits = courses
      .filter(c => c.tags.includes(tag))
      .reduce((sum, c) => sum + c.credits, 0);
    return `      <tr>
        <td><span class="tag tag-${esc(tag)}">${esc(tag)}</span></td>
        <td class="credits-value">${credits}</td>
      </tr>`;
  }).join('\n');

  return `    <div class="credits-summary">
    <h2 class="legend-title">Créditos</h2>
    <table class="credits-summary-table">
      <tbody>
        <tr class="credits-total-row">
          <td>Total geral</td>
          <td class="credits-value">${totalCredits}</td>
        </tr>
${uniqueTags.length > 0 ? tagRows : ''}
      </tbody>
    </table>
    </div>`;
}

// ─── CSS ──────────────────────────────────────────────────────────────────────

const TAG_PALETTE: Array<[string, string]> = [
  ['#cce5ff', '#004085'],
  ['#f8d7da', '#721c24'],
  ['#d4edda', '#155724'],
  ['#fff3cd', '#856404'],
  ['#e2d9f3', '#4a235a'],
  ['#fde8d8', '#7d3a0e'],
  ['#d1ecf1', '#0c5460'],
  ['#f5c6cb', '#6b1219'],
  ['#c3e6cb', '#1b4f35'],
  ['#ffeeba', '#533f03'],
];

function renderCss(tags: string[], categories: CategoryInput[]): string {
  const tagRules = tags.map((t, i) => {
    const [bg, fg] = TAG_PALETTE[i % TAG_PALETTE.length];
    return `    .tag-${esc(t)} { background: ${bg}; color: ${fg}; }`;
  }).join('\n');

  const fillRules = categories
    .filter(category => !!category.color)
    .map(category =>
      `    .course-card.fill-${cssToken(category.id)} { background: ${category.color}; border-color: ${category.color}; }`
    ).join('\n');

  return `    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: system-ui, sans-serif;
      background: #f5f5f5;
      color: #222;
    }

    /* Cabeçalho */
    .course-header {
      background: #1a3a6b;
      color: #fff;
      padding: 16px 24px;
      text-align: left;
    }
    .course-title { font-size: 1.4rem; font-weight: bold; }
    .course-meta  { font-size: 0.85rem; opacity: 0.8; margin-top: 4px; }

    /* Layout geral */
    .matrix-wrapper {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 16px;
    }
    .matrix-area {
      width: var(--matrix-base-w);
      height: var(--matrix-base-h);
      overflow: hidden;
      position: relative;
      flex-shrink: 0;
    }
    .matrix-canvas {
      position: relative;
      transform-origin: top left;
    }
    @media (max-width: 1200px) {
      .matrix-wrapper {
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
        padding: 12px;
      }
      .legend-panel {
        width: fit-content;
        max-width: 100%;
      }
    }

    /* Colunas */
    .columns-row {
      display: flex;
      gap: 60px;
      align-items: flex-start;
    }
    .level-column {
      width: ${CARD_WIDTH}px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 0;
    }
    .col-header {
      display: flex;
      flex-direction: column;
      align-items: center;
      height: ${COL_HEADER_H}px;
      justify-content: center;
      background: #e8ecf5;
      border-bottom: 2px solid #1a3a6b;
      border-radius: 4px 4px 0 0;
    }
    .col-roman   { font-size: 1.1rem; font-weight: bold; color: #1a3a6b; }
    .col-credits { font-size: 0.75rem; color: #555; }

    .cards-area {
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 24px 0;
    }

    /* Wrapper do cartão (para badge de créditos mínimos) */
    .card-wrapper {
      position: relative;
      width: 100%;
      height: 60px;
    }

    /* Badge de requisito de créditos mínimos */
    .credit-req-badge {
      font-size: 0.65rem;
      font-weight: 700;
      background: #f0f0f0;
      color: #555;
      border: 1px solid #aaa;
      border-radius: 3px;
      padding: 1px 5px;
      white-space: nowrap;
    }
    .card-wrapper .credit-req-badge {
      position: absolute;
      top: -18px;
      left: 50%;
      transform: translateX(-50%);
      pointer-events: none;
    }

    /* Cartões de disciplina */
    .course-card {
      width: 100%;
      height: 60px;
      background: #fff;
      border: 1.5px solid #aaa;
      border-radius: 4px;
      cursor: pointer;
      transition: box-shadow 0.15s, opacity 0.15s;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
    }
    .course-card:hover,
    .course-card:focus {
      box-shadow: 0 0 0 3px #1a3a6b55;
      outline: none;
    }
    .course-card.highlighted {
      border-color: #1a3a6b;
      box-shadow: 0 0 0 3px #1a3a6b99;
    }
    .course-card.faded {
      opacity: 0.25;
    }
    .card-body {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 6px 8px 4px;
      flex: 1;
    }
    .card-name    { font-size: 0.78rem; line-height: 1.3; }
    .card-credits { font-size: 0.75rem; color: #555; white-space: nowrap; margin-left: 4px; }
    .card-footer  { position: absolute; bottom: 0; left: 0; right: 0; padding: 2px 6px 4px; display: flex; gap: 4px; flex-wrap: wrap; min-height: 16px; }
    .card-footer:not(:empty) { background: rgba(255,255,255,0.85); }
    .course-card.fill-category .card-name,
    .course-card.fill-category .card-credits {
      color: #222;
    }
    .course-card.fill-category .card-footer:not(:empty) {
      background: rgba(255, 255, 255, 0.45);
    }
    .course-card.fill-category .tag {
      background: rgba(0,0,0,0.12);
      color: #222;
      border: 1px solid rgba(0,0,0,0.2);
    }

    /* Tags */
    .tag {
      font-size: 0.65rem;
      border-radius: 10px;
      padding: 1px 6px;
      font-weight: 600;
    }
${tagRules}
${fillRules}

    /* Setas SVG */
    .arrows-layer {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
    }
    .arrow-line {
      fill: none;
      stroke: #1a3a6b;
    }
    .arrows-layer.link-style-paths .arrow-line {
      opacity: 0.6;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .arrows-layer.link-style-arrows .arrow-line {
      opacity: 0.9;
      stroke-linecap: butt;
      stroke-linejoin: miter;
    }
    .arrow-group[data-type="special"] .arrow-line {
      stroke: #b45309;
    }
    .arrow-group[data-type="corequisite"] .arrow-line {
      stroke: #475569;
    }
    .arrows-layer.hidden .arrow-group { display: none; }
    .arrow-label {
      font-size: 0.65rem;
      fill: #555;
    }

    /* Legenda */
    .legend-panel {
      min-width: 180px;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 6px;
      padding: 12px;
      flex-shrink: 0;
    }
    .legend-title {
      font-size: 0.9rem;
      font-weight: bold;
      margin-bottom: 10px;
      border-bottom: 1px solid #ddd;
      padding-bottom: 6px;
    }
    .legend-list {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 6px 10px;
      align-items: center;
      font-size: 0.78rem;
    }
    .legend-list dt { display: flex; align-items: center; }
    .legend-subtitle {
      grid-column: 1 / -1;
      margin-top: 8px;
      padding-top: 6px;
      border-top: 1px solid #e5e7eb;
      font-weight: 700;
      color: #374151;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .legend-subtitle-spacer { display: none; }
    .category-chip {
      display: inline-block;
      width: 24px;
      height: 12px;
      border-radius: 999px;
      border: 1px solid #9ca3af;
      background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
    }
    .legend-toggle {
      margin-top: 20px;
      padding-top: 12px;
      border-top: 1px solid #ddd;
      font-size: 0.8rem;
    }
    .legend-toggle label {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-weight: 600;
      color: #1a3a6b;
    }
    .legend-toggle input[type="checkbox"] {
      width: 15px;
      height: 15px;
      cursor: pointer;
      accent-color: #1a3a6b;
    }

    /* Popup */
    .popup {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 16px;
      animation: popup-backdrop-in 0.18s ease;
    }
    .popup[hidden] { display: none; }
    @keyframes popup-backdrop-in {
      from { background: rgba(0,0,0,0); }
      to   { background: rgba(0,0,0,0.5); }
    }
    .popup-content {
      background: #fff;
      border-radius: 12px;
      max-width: 500px;
      width: 100%;
      position: relative;
      max-height: 88vh;
      overflow-y: auto;
      box-shadow: 0 24px 64px rgba(0,0,0,0.28);
      animation: popup-slide-in 0.18s ease;
    }
    @keyframes popup-slide-in {
      from { opacity: 0; transform: translateY(-12px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0)    scale(1); }
    }
    .popup-close {
      position: absolute;
      top: 12px; right: 12px;
      width: 32px; height: 32px;
      background: rgba(255,255,255,0.18);
      border: none;
      border-radius: 50%;
      cursor: pointer;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1;
      transition: background 0.15s;
    }
    .popup-close:hover { background: rgba(255,255,255,0.32); }
    .popup-close svg   { width: 15px; height: 15px; }
    .popup-header {
      background: #1a3a6b;
      color: #fff;
      padding: 22px 52px 18px 22px;
      border-radius: 12px 12px 0 0;
    }
    .popup-code {
      display: block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      opacity: 0.7;
      margin-bottom: 4px;
    }
    .popup-name {
      font-size: 1.1rem;
      font-weight: 700;
      line-height: 1.35;
      margin-bottom: 12px;
    }
    .popup-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .popup-header .tag {
      border: 1px solid rgba(255,255,255,0.3);
    }
    .popup-body {
      padding: 18px 20px 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .popup-stats {
      display: flex;
      gap: 10px;
    }
    .popup-stat {
      flex: 1;
      background: #f2f5fb;
      border: 1px solid #dde3f0;
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .popup-stat-value {
      font-size: 1.3rem;
      font-weight: 700;
      color: #1a3a6b;
      line-height: 1;
      margin-bottom: 4px;
    }
    .popup-stat-label {
      font-size: 0.7rem;
      color: #777;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    .popup-section-title {
      font-size: 0.7rem;
      font-weight: 700;
      color: #1a3a6b;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      margin-bottom: 8px;
      padding-bottom: 5px;
      border-bottom: 2px solid #e8ecf5;
    }
    .popup-syllabus-text {
      font-size: 0.84rem;
      color: #444;
      line-height: 1.65;
    }
    .popup-req-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .popup-req-item {
      display: flex;
      align-items: baseline;
      gap: 8px;
      font-size: 0.82rem;
      color: #333;
    }
    .popup-req-item::before {
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #1a3a6b;
      flex-shrink: 0;
      position: relative;
      top: -1px;
    }
    .popup-req-code {
      font-weight: 700;
      color: #1a3a6b;
      font-size: 0.77rem;
      white-space: nowrap;
    }
    .popup-req-name   { color: #555; }
    .popup-empty {
      font-size: 0.82rem;
      color: #aaa;
      font-style: italic;
    }

    /* Totalizador de créditos */
    .credits-summary {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid #ddd;
    }
    .credits-summary-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.78rem;
    }
    .credits-summary-table td {
      padding: 3px 4px;
      vertical-align: middle;
    }
    .credits-total-row td {
      font-weight: 700;
      padding-bottom: 6px;
      border-bottom: 1px solid #eee;
    }
    .credits-value {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .credits-summary-table tr:not(.credits-total-row) td:first-child {
      padding-top: 4px;
    }`;  
}

// ─── JavaScript embutido ──────────────────────────────────────────────────────

function renderJs(data: CurriculumFile, _layout: LayoutData, _routes: RouteData): string {
  // Serializa apenas os dados necessários para o JS de interatividade
  const courses = JSON.stringify(
    data.courses.map(c => ({
      code: c.code,
      name: c.name,
      hours: c.hours,
      credits: c.credits,
      syllabus: c.syllabus,
      tags: c.tags,
      category: c.category ?? null,
    }))
  );

  const requirements = JSON.stringify(
    data.requirements.map(r => ({
      type: r.type,
      from: r.from ?? null,
      to: r.to,
      description: r.description ?? null,
      min_credits: r.min_credits ?? null,
    }))
  );

  const categories = JSON.stringify(
    (data.categories ?? []).map(c => ({
      id: c.id,
      color: c.color ?? null,
    }))
  );

  return `(function () {
  'use strict';

  const COURSES = ${courses};
  const REQUIREMENTS = ${requirements};
  const CATEGORIES = ${categories};

  const courseMap = new Map(COURSES.map(c => [c.code, c]));
  const categoryColorMap = new Map(
    CATEGORIES
      .filter(c => typeof c.color === 'string' && c.color.trim() !== '')
      .map(c => [c.id, c.color])
  );

  // ── Escala responsiva da matriz ──────────────────────────────────────────────
  function applyMatrixScale() {
    var matrixArea   = document.querySelector('.matrix-area');
    var matrixCanvas = document.querySelector('.matrix-canvas');
    var legendPanel  = document.querySelector('.legend-panel');
    if (!matrixArea || !matrixCanvas) return;

    var baseWidth  = parseFloat(matrixArea.style.getPropertyValue('--matrix-base-w'));
    var baseHeight = parseFloat(matrixArea.style.getPropertyValue('--matrix-base-h'));
    if (!baseWidth || !baseHeight) return;

    var padding    = 24;
    var isStacked  = window.innerWidth <= 1200;
    var legendW    = (!isStacked && legendPanel) ? (legendPanel.offsetWidth + 16) : 0;
    var availWidth = window.innerWidth - padding * 2 - legendW;
    var scale      = Math.min(1, availWidth / baseWidth);
    var scaledW    = baseWidth  * scale;
    var scaledH    = baseHeight * scale;

    matrixArea.style.width  = scaledW + 'px';
    matrixArea.style.height = scaledH + 'px';
    matrixCanvas.style.transform = scale < 1 ? 'scale(' + scale + ')' : '';

    if (legendPanel) legendPanel.style.width = isStacked ? scaledW + 'px' : '';
  }

  applyMatrixScale();
  window.addEventListener('resize', applyMatrixScale);

  // ── Toggle de setas ─────────────────────────────────────────────────────────
  const toggleArrows = document.getElementById('toggle-arrows');
  const arrowsLayer  = document.querySelector('.arrows-layer');

  // Estado inicial: setas ocultas (checkbox desmarcado)
  arrowsLayer.classList.add('hidden');

  toggleArrows.addEventListener('change', () => {
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  });

  // ── Hover sobre cartões ─────────────────────────────────────────────────────
  const allCards = Array.from(document.querySelectorAll('.course-card'));
  const allArrows = Array.from(document.querySelectorAll('.arrow-group'));

  function getRelated(code) {
    const prereqs = new Set();
    const dependents = new Set();
    for (const req of REQUIREMENTS) {
      if (req.type === 'credit_requirement') continue;
      if (req.to === code && req.from)   prereqs.add(req.from);
      if (req.from === code)             dependents.add(req.to);
    }
    return { prereqs, dependents };
  }

  function onCardEnter(code) {
    const { prereqs, dependents } = getRelated(code);
    const related = new Set([code, ...prereqs, ...dependents]);

    allCards.forEach(card => {
      const c = card.dataset.code;
      card.classList.toggle('highlighted', related.has(c));
      card.classList.toggle('faded', !related.has(c));
    });

    // Remove hidden class so active arrows are always visible during hover
    arrowsLayer.classList.remove('hidden');

    allArrows.forEach(arrow => {
      const from = arrow.dataset.from;
      const to   = arrow.dataset.to;
      const active = (from === code || to === code);
      arrow.style.display = active ? '' : 'none';
    });
  }

  function onCardLeave() {
    allCards.forEach(card => {
      card.classList.remove('highlighted', 'faded');
    });
    allArrows.forEach(arrow => {
      arrow.style.display = '';
    });
    // Restore hidden state based on checkbox
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  }

  allCards.forEach(card => {
    card.addEventListener('mouseenter', () => onCardEnter(card.dataset.code));
    card.addEventListener('mouseleave', onCardLeave);
    card.addEventListener('focusin',    () => onCardEnter(card.dataset.code));
    card.addEventListener('focusout',   onCardLeave);
  });

  // ── Popup de detalhes ───────────────────────────────────────────────────────
  const popup       = document.getElementById('course-popup');
  const popupClose  = popup.querySelector('.popup-close');
  const popupHeader = popup.querySelector('.popup-header');
  const defaultPopupHeaderColor = '#1a3a6b';

  function openPopup(code) {
    const course = courseMap.get(code);
    if (!course) return;

    const popupHeaderColor = course.category
      ? categoryColorMap.get(course.category)
      : null;
    popupHeader.style.background = popupHeaderColor || defaultPopupHeaderColor;

    document.getElementById('popup-code').textContent     = course.code;
    document.getElementById('popup-name').textContent     = course.name;
    document.getElementById('popup-hours').textContent    = course.hours + ' h';
    document.getElementById('popup-credits').textContent  = course.credits + ' cr';
    document.getElementById('popup-syllabus').textContent = course.syllabus || '—';

    // Tags como badges
    const tagsEl = document.getElementById('popup-tags');
    tagsEl.innerHTML = '';
    course.tags.forEach(function(tag) {
      const span = document.createElement('span');
      span.className = 'tag tag-' + tag;
      span.textContent = tag;
      tagsEl.appendChild(span);
    });

    // Pré-requisitos
    const prereqs = REQUIREMENTS
      .filter(function(r) { return r.to === code && r.from; })
      .map(function(r) {
        const c = courseMap.get(r.from);
        return { code: r.from, name: c ? c.name : '', desc: r.description };
      });
    const creditReq = REQUIREMENTS.find(function(r) { return r.type === 'credit_requirement' && r.to === code; });

    const prereqEl = document.getElementById('popup-prereqs');
    prereqEl.innerHTML = '';
    if (prereqs.length === 0 && !creditReq) {
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhum pré-requisito';
      prereqEl.appendChild(none);
    } else {
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      prereqs.forEach(function(p) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const codeSpan = document.createElement('span');
        codeSpan.className = 'popup-req-code';
        codeSpan.textContent = p.code;
        const nameSpan = document.createElement('span');
        nameSpan.className = 'popup-req-name';
        nameSpan.textContent = p.name + (p.desc ? ' (' + p.desc + ')' : '');
        li.appendChild(codeSpan);
        li.appendChild(nameSpan);
        ul.appendChild(li);
      });
      if (creditReq) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const span = document.createElement('span');
        span.className = 'popup-req-name';
        span.textContent = 'Mín. ' + creditReq.min_credits + ' créditos cursados';
        li.appendChild(span);
        ul.appendChild(li);
      }
      prereqEl.appendChild(ul);
    }

    // Dependentes (cursos que têm esta disciplina como pré-requisito)
    const dependents = REQUIREMENTS
      .filter(function(r) { return r.from === code && r.to; })
      .map(function(r) {
        const c = courseMap.get(r.to);
        return { code: r.to, name: c ? c.name : '' };
      });

    const depsEl = document.getElementById('popup-dependents');
    depsEl.innerHTML = '';
    if (dependents.length === 0) {
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhuma dependência';
      depsEl.appendChild(none);
    } else {
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      dependents.forEach(function(d) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const codeSpan = document.createElement('span');
        codeSpan.className = 'popup-req-code';
        codeSpan.textContent = d.code;
        const nameSpan = document.createElement('span');
        nameSpan.className = 'popup-req-name';
        nameSpan.textContent = d.name;
        li.appendChild(codeSpan);
        li.appendChild(nameSpan);
        ul.appendChild(li);
      });
      depsEl.appendChild(ul);
    }

    popup.hidden = false;
    popupClose.focus();
  }

  function closePopup() {
    popup.hidden = true;
  }

  allCards.forEach(card => {
    card.addEventListener('click', () => openPopup(card.dataset.code));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openPopup(card.dataset.code);
      }
    });
  });

  popupClose.addEventListener('click', closePopup);
  popup.addEventListener('click', e => { if (e.target === popup) closePopup(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePopup(); });
})();`;
}

// ─── Utilitários ─────────────────────────────────────────────────────────────

function esc(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str: string): string {
  return esc(str);
}

function cssToken(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/--+/g, '-');
}

function toRoman(n: number): string {
  const vals = [1000,900,500,400,100,90,50,40,10,9,5,4,1];
  const syms = ['M','CM','D','CD','C','XC','L','XL','X','IX','V','IV','I'];
  let result = '';
  for (let i = 0; i < vals.length; i++) {
    while (n >= vals[i]) { result += syms[i]; n -= vals[i]; }
  }
  return result;
}
