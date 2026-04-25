from __future__ import annotations

import json
import math
import re
from typing import Dict, List, Optional, Tuple

from .layout import CARD_WIDTH, COL_HEADER_H
from .types import (
    ArrowRoute,
    CardRect,
    CategoryInput,
    ColumnLayout,
    CourseInput,
    CurriculumFile,
    LayoutData,
    Point,
    RequirementInput,
    RouteData,
)

# ─────────────────────────────────────────────────────────────────────────────
# Paleta de cores para tags
# ─────────────────────────────────────────────────────────────────────────────

TAG_PALETTE: List[Tuple[str, str]] = [
    ("#cce5ff", "#004085"),
    ("#f8d7da", "#721c24"),
    ("#d4edda", "#155724"),
    ("#fff3cd", "#856404"),
    ("#e2d9f3", "#4a235a"),
    ("#fde8d8", "#7d3a0e"),
    ("#d1ecf1", "#0c5460"),
    ("#f5c6cb", "#6b1219"),
    ("#c3e6cb", "#1b4f35"),
    ("#ffeeba", "#533f03"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de string
# ─────────────────────────────────────────────────────────────────────────────


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _css_token(value: str) -> str:
    t = value.strip().lower()
    t = re.sub(r"[^a-z0-9_-]+", "-", t)
    t = t.strip("-")
    t = re.sub(r"--+", "-", t)
    return t


def _to_roman(n: int) -> str:
    vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    result = ""
    for v, s in zip(vals, syms):
        while n >= v:
            result += s
            n -= v
    return result


def _fmt(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.4f}".rstrip("0").rstrip(".")


# ─────────────────────────────────────────────────────────────────────────────
# Gerador HTML — ponto de entrada público
# ─────────────────────────────────────────────────────────────────────────────


def render_html(
    data: CurriculumFile,
    layout: LayoutData,
    routes: RouteData,
    link_style: str = "paths",
) -> str:
    course_map = {c.code: c for c in data.courses}
    category_map = {c.id: c for c in data.categories}
    unique_tags = list(dict.fromkeys(tag for c in data.courses for tag in c.tags))
    credit_req_map: Dict[str, int] = {}
    for req in data.requirements:
        if req.type == "credit_requirement" and req.min_credits is not None:
            credit_req_map[req.to] = req.min_credits

    use_category_fill = data.card_fill_style == "category"

    css_block = _render_css(unique_tags, data.categories)
    header_block = _render_header(data)
    columns_html = "\n".join(
        _render_column(col, course_map, credit_req_map, category_map, use_category_fill)
        for col in layout.columns
    )
    arrow_defs = _render_arrow_defs(link_style)
    arrows_html = "\n".join(
        _render_arrow(arrow, data.requirements, link_style) for arrow in routes.arrows
    )
    popup_html = _render_popup()
    legend_html = _render_legend(unique_tags, link_style, data.categories)
    credits_html = _render_credit_summary(data.courses, unique_tags)
    js_block = _render_js(data)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(data.curriculum.name)}</title>
  <style>
{css_block}
  </style>
</head>
<body>
{header_block}
<div class="matrix-wrapper">
  <div class="matrix-area" style="--matrix-base-w:{layout.canvas_width}px; --matrix-base-h:{layout.canvas_height}px;">
    <div class="matrix-canvas" style="width:{layout.canvas_width}px; height:{layout.canvas_height}px;">
      <svg class="arrows-layer link-style-{link_style}" width="{layout.canvas_width}" height="{layout.canvas_height}" aria-hidden="true">
{arrow_defs}
{arrows_html}
      </svg>
  <div class="columns-row">
{columns_html}
  </div>
    </div>
  </div>
  <aside class="legend-panel">
{legend_html}
{credits_html}
  </aside>
</div>
{popup_html}
<script>
{js_block}
</script>
</body>
</html>"""


# ─── Cabeçalho ───────────────────────────────────────────────────────────────


def _render_header(data: CurriculumFile) -> str:
    return (
        f'<header class="course-header">\n'
        f'  <div class="course-title">{_esc(data.curriculum.name)}</div>\n'
        f'  <div class="course-meta">{_esc(data.curriculum.code)} &bull; desde {_esc(data.curriculum.available_since)}</div>\n'
        f"</header>"
    )


# ─── Colunas e cartões ────────────────────────────────────────────────────────


def _render_column(
    col: ColumnLayout,
    course_map: Dict[str, CourseInput],
    credit_req_map: Dict[str, int],
    category_map: Dict[str, CategoryInput],
    use_category_fill: bool,
) -> str:
    roman = _to_roman(col.level)
    cards_html = "\n".join(
        _render_card(
            card,
            course_map[card.course_code],
            credit_req_map.get(card.course_code),
            category_map,
            use_category_fill,
        )
        for card in col.cards
    )
    return (
        f'      <div class="level-column" data-level="{col.level}">\n'
        f'        <div class="col-header">\n'
        f'          <span class="col-roman">{roman}</span>\n'
        f'          <span class="col-credits">{col.total_credits} créditos</span>\n'
        f"        </div>\n"
        f'        <div class="cards-area">\n'
        f"{cards_html}\n"
        f"        </div>\n"
        f"      </div>"
    )


def _render_card(
    card: CardRect,
    course: CourseInput,
    min_credits: Optional[int],
    category_map: Dict[str, CategoryInput],
    use_category_fill: bool,
) -> str:
    tags = "".join(
        f'<span class="tag tag-{_esc(t)}">{_esc(t)}</span>' for t in course.tags
    )
    fill_class = _resolve_category_fill_class(course, category_map, use_category_fill)
    credit_badge = (
        f'\n          <div class="credit-req-badge">{min_credits} CR</div>'
        if min_credits is not None
        else ""
    )
    return (
        f'          <div class="card-wrapper">{credit_badge}\n'
        f'            <div class="course-card{fill_class}"\n'
        f'               id="card-{_esc(course.code)}"\n'
        f'               data-code="{_esc(course.code)}"\n'
        f'               tabindex="0"\n'
        f'               role="button"\n'
        f'               aria-label="{_esc(course.name)}">\n'
        f'              <div class="card-body">\n'
        f'                <span class="card-name">{_esc(course.name)}</span>\n'
        f'                <span class="card-credits">({course.credits})</span>\n'
        f"              </div>\n"
        f'              <div class="card-footer">{tags}</div>\n'
        f"            </div>\n"
        f"          </div>"
    )


def _resolve_category_fill_class(
    course: CourseInput,
    category_map: Dict[str, CategoryInput],
    use_category_fill: bool,
) -> str:
    if not use_category_fill:
        return ""
    if not course.category:
        return ""
    cat = category_map.get(course.category)
    if not cat or not cat.color:
        return ""
    return f" fill-category fill-{_css_token(cat.id)}"


# ─── Setas SVG ────────────────────────────────────────────────────────────────


def _render_arrow(
    arrow: ArrowRoute,
    requirements: List[RequirementInput],
    link_style: str,
) -> str:
    req = requirements[arrow.requirement_index]
    dash = _arrow_dash(arrow.type)
    width = _arrow_stroke_width(arrow.type, link_style)
    from_code = req.from_code or ""
    to_code = req.to

    label_el = ""
    if arrow.label and len(arrow.points) >= 2:
        mid = arrow.points[len(arrow.points) // 2]
        label_el = f'\n    <text class="arrow-label" x="{mid.x}" y="{mid.y - 4}">{_esc(arrow.label)}</text>'

    if link_style == "arrows":
        pts_str = " ".join(f"{p.x},{p.y}" for p in arrow.points)
        return (
            f'    <g class="arrow-group"\n'
            f'       data-type="{arrow.type}"\n'
            f'       data-from="{_esc(from_code)}"\n'
            f'       data-to="{_esc(to_code)}">\n'
            f'      <polyline points="{pts_str}"\n'
            f'      stroke-dasharray="{dash}"\n'
            f'      stroke-width="{width}"\n'
            f'      class="arrow-line"\n'
            f'      marker-end="url(#arrowhead)"/>\n'
            f"      {label_el}\n"
            f"    </g>"
        )

    path_d = _sankey_path_from_points(arrow.points)
    return (
        f'    <g class="arrow-group"\n'
        f'       data-type="{arrow.type}"\n'
        f'       data-from="{_esc(from_code)}"\n'
        f'       data-to="{_esc(to_code)}">\n'
        f'      <path d="{path_d}"\n'
        f'            stroke-dasharray="{dash}"\n'
        f'            stroke-width="{width}"\n'
        f'            class="arrow-line"/>\n'
        f"      {label_el}\n"
        f"    </g>"
    )


def _arrow_dash(rtype: str) -> str:
    if rtype == "special":
        return "8,4"
    if rtype == "corequisite":
        return "3,3"
    return "none"


def _arrow_stroke_width(rtype: str, link_style: str) -> float:
    if link_style == "arrows":
        return 1.4 if rtype == "corequisite" else 1.6
    if rtype == "special":
        return 5
    if rtype == "corequisite":
        return 4
    return 6


def _render_arrow_defs(link_style: str) -> str:
    if link_style != "arrows":
        return ""
    return (
        "      <defs>\n"
        '        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">\n'
        '          <path d="M0,0 L8,3 L0,6 Z" fill="#333"/>\n'
        "        </marker>\n"
        "      </defs>"
    )


def _sankey_path_from_points(points: List[Point]) -> str:
    if not points:
        return ""
    if len(points) == 1:
        return f"M {_fmt(points[0].x)} {_fmt(points[0].y)}"
    if len(points) == 2:
        return (
            f"M {_fmt(points[0].x)} {_fmt(points[0].y)} "
            f"L {_fmt(points[1].x)} {_fmt(points[1].y)}"
        )

    radius = 12
    d = f"M {_fmt(points[0].x)} {_fmt(points[0].y)}"

    for i in range(1, len(points) - 1):
        prev = points[i - 1]
        curr = points[i]
        nxt = points[i + 1]

        in_dx = curr.x - prev.x
        in_dy = curr.y - prev.y
        out_dx = nxt.x - curr.x
        out_dy = nxt.y - curr.y

        in_len = math.hypot(in_dx, in_dy)
        out_len = math.hypot(out_dx, out_dy)
        if in_len == 0 or out_len == 0:
            continue

        corner = min(radius, in_len * 0.45, out_len * 0.45)
        enter_x = curr.x - (in_dx / in_len) * corner
        enter_y = curr.y - (in_dy / in_len) * corner
        exit_x = curr.x + (out_dx / out_len) * corner
        exit_y = curr.y + (out_dy / out_len) * corner

        d += f" L {_fmt(enter_x)} {_fmt(enter_y)}"
        d += f" Q {_fmt(curr.x)} {_fmt(curr.y)} {_fmt(exit_x)} {_fmt(exit_y)}"

    last = points[-1]
    d += f" L {_fmt(last.x)} {_fmt(last.y)}"
    return d


# ─── Popup ────────────────────────────────────────────────────────────────────


def _render_popup() -> str:
    return """\
<div id="course-popup" class="popup" role="dialog" aria-modal="true" aria-labelledby="popup-name" hidden>
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
          <span class="popup-stat-label">Carga hor&#225;ria</span>
        </div>
        <div class="popup-stat">
          <span class="popup-stat-value" id="popup-credits"></span>
          <span class="popup-stat-label">Cr&#233;ditos</span>
        </div>
      </div>
      <section class="popup-section">
        <h3 class="popup-section-title">Ementa</h3>
        <p id="popup-syllabus" class="popup-syllabus-text"></p>
      </section>
      <section class="popup-section">
        <h3 class="popup-section-title">Pr&#233;-requisitos</h3>
        <div id="popup-prereqs"></div>
      </section>
      <section class="popup-section">
        <h3 class="popup-section-title">Dependentes</h3>
        <div id="popup-dependents"></div>
      </section>
    </div>
  </div>
</div>"""


# ─── Legenda ──────────────────────────────────────────────────────────────────


def _render_legend(
    tags: List[str], link_style: str, categories: List[CategoryInput]
) -> str:
    tag_items = "\n".join(
        f'      <dt><span class="tag tag-{_esc(t)}">{_esc(t)}</span></dt>\n      <dd>Disciplina {_esc(t)}</dd>'
        for t in tags
    )

    category_items = "\n".join(
        (
            (
                f'      <dt><span class="category-chip" style="background:{_esc(cat.color)}; border-color:{_esc(cat.color)};"></span></dt>\n'
                f"      <dd>{_esc(cat.name)}</dd>"
            )
            if cat.color
            else (
                f'      <dt><span class="category-chip"></span></dt>\n'
                f"      <dd>{_esc(cat.name)}</dd>"
            )
        )
        for cat in categories
    )

    category_section = (
        f'\n      <dt class="legend-subtitle">Eixos</dt>\n      <dd class="legend-subtitle-spacer"></dd>\n{category_items}'
        if category_items
        else ""
    )

    if link_style == "arrows":
        prereq_shape = '<svg width="60" height="14"><defs><marker id="arrowhead-legend-1" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#1a3a6b" stroke-width="1.6" marker-end="url(#arrowhead-legend-1)"/></svg>'
        special_shape = '<svg width="60" height="14"><defs><marker id="arrowhead-legend-2" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#b45309" stroke-width="1.6" stroke-dasharray="8,4" marker-end="url(#arrowhead-legend-2)"/></svg>'
        coreq_shape = '<svg width="60" height="14"><defs><marker id="arrowhead-legend-3" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#333"/></marker></defs><line x1="2" y1="7" x2="58" y2="7" stroke="#475569" stroke-width="1.4" stroke-dasharray="3,3" marker-end="url(#arrowhead-legend-3)"/></svg>'
    else:
        prereq_shape = '<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#1a3a6b" stroke-width="6" fill="none" stroke-linecap="round"/></svg>'
        special_shape = '<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#b45309" stroke-width="5" fill="none" stroke-linecap="round" stroke-dasharray="8,4"/></svg>'
        coreq_shape = '<svg width="60" height="14"><path d="M2 7 C 16 7, 20 7, 30 7 S 44 7, 58 7" stroke="#475569" stroke-width="4" fill="none" stroke-linecap="round" stroke-dasharray="3,3"/></svg>'

    return (
        f'    <h2 class="legend-title">Legenda</h2>\n'
        f'    <dl class="legend-list">\n'
        f"      <dt>{prereq_shape}</dt>\n"
        f"      <dd>Pr&#233;-requisito</dd>\n"
        f"      <dt>{special_shape}</dt>\n"
        f"      <dd>Pr&#233;-requisito especial (RE)</dd>\n"
        f"      <dt>{coreq_shape}</dt>\n"
        f"      <dd>Co-requisito</dd>\n"
        f'      <dt><span class="credit-req-badge">XX CR</span></dt>\n'
        f"      <dd>Requisito de cr&#233;ditos m&#237;nimos</dd>\n"
        f"    {category_section}\n"
        f"{tag_items}\n"
        f"    </dl>\n"
        f'    <div class="legend-toggle">\n'
        f"      <label>\n"
        f'        <input type="checkbox" id="toggle-arrows">\n'
        f"        Exibir setas de pr&#233;-requisito\n"
        f"      </label>\n"
        f"    </div>\n"
        f"    "
    )


# ─── Totalizador de créditos ─────────────────────────────────────────────────


def _render_credit_summary(courses: List[CourseInput], unique_tags: List[str]) -> str:
    total_credits = sum(c.credits for c in courses)

    tag_rows = "\n".join(
        (
            f"      <tr>\n"
            f'        <td><span class="tag tag-{_esc(tag)}">{_esc(tag)}</span></td>\n'
            f'        <td class="credits-value">'
            f"{sum(c.credits for c in courses if tag in c.tags)}"
            f"</td>\n"
            f"      </tr>"
        )
        for tag in unique_tags
    )

    return (
        f'    <div class="credits-summary">\n'
        f'    <h2 class="legend-title">Cr&#233;ditos</h2>\n'
        f'    <table class="credits-summary-table">\n'
        f"      <tbody>\n"
        f'        <tr class="credits-total-row">\n'
        f"          <td>Total geral</td>\n"
        f'          <td class="credits-value">{total_credits}</td>\n'
        f"        </tr>\n"
        f'{tag_rows if unique_tags else ""}\n'
        f"      </tbody>\n"
        f"    </table>\n"
        f"    </div>"
    )


# ─── CSS ─────────────────────────────────────────────────────────────────────


def _render_css(tags: List[str], categories: List[CategoryInput]) -> str:
    tag_rules = "\n".join(
        f"    .tag-{_esc(t)} {{ background: {bg}; color: {fg}; }}"
        for i, t in enumerate(tags)
        for bg, fg in [TAG_PALETTE[i % len(TAG_PALETTE)]]
    )

    fill_rules = "\n".join(
        f"    .course-card.fill-{_css_token(cat.id)} {{ background: {cat.color}; border-color: {cat.color}; }}"
        for cat in categories
        if cat.color
    )

    return f"""    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: system-ui, sans-serif;
      background: #f5f5f5;
      color: #222;
    }}

    /* Cabeçalho */
    .course-header {{
      background: #1a3a6b;
      color: #fff;
      padding: 16px 24px;
      text-align: left;
    }}
    .course-title {{ font-size: 1.4rem; font-weight: bold; }}
    .course-meta  {{ font-size: 0.85rem; opacity: 0.8; margin-top: 4px; }}

    /* Layout geral */
    .matrix-wrapper {{
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 16px;
    }}
    .matrix-area {{
      width: var(--matrix-base-w);
      height: var(--matrix-base-h);
      overflow: hidden;
      position: relative;
      flex-shrink: 0;
    }}
    .matrix-canvas {{
      position: relative;
      transform-origin: top left;
      isolation: isolate;
    }}
    @media (max-width: 1200px) {{
      .matrix-wrapper {{
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
        padding: 12px;
      }}
      .legend-panel {{
        width: fit-content;
        max-width: 100%;
      }}
    }}

    /* Colunas */
    .columns-row {{
      display: flex;
      gap: 60px;
      align-items: flex-start;
      position: relative;
      z-index: 1;
    }}
    .level-column {{
      width: {CARD_WIDTH}px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 0;
    }}
    .col-header {{
      display: flex;
      flex-direction: column;
      align-items: center;
      height: {COL_HEADER_H}px;
      justify-content: center;
      background: #e8ecf5;
      border-bottom: 2px solid #1a3a6b;
      border-radius: 4px 4px 0 0;
    }}
    .col-roman   {{ font-size: 1.1rem; font-weight: bold; color: #1a3a6b; }}
    .col-credits {{ font-size: 0.75rem; color: #555; }}

    .cards-area {{
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 24px 0;
    }}

    /* Wrapper do cartão */
    .card-wrapper {{
      position: relative;
      width: 100%;
      height: 60px;
    }}

    /* Badge de requisito de créditos mínimos */
    .credit-req-badge {{
      font-size: 0.65rem;
      font-weight: 700;
      background: #f0f0f0;
      color: #555;
      border: 1px solid #aaa;
      border-radius: 3px;
      padding: 1px 5px;
      white-space: nowrap;
    }}
    .card-wrapper .credit-req-badge {{
      position: absolute;
      top: -18px;
      left: 50%;
      transform: translateX(-50%);
      pointer-events: none;
    }}

    /* Cartões de disciplina */
    .course-card {{
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
    }}
    .course-card:hover,
    .course-card:focus {{
      box-shadow: 0 0 0 3px #1a3a6b55;
      outline: none;
    }}
    .course-card.highlighted {{
      border-color: #1a3a6b;
      box-shadow: 0 0 0 3px #1a3a6b99;
    }}
    .course-card.faded {{
      opacity: 0.25;
    }}
    .card-body {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 6px 8px 4px;
      flex: 1;
    }}
    .card-name    {{ font-size: 0.78rem; line-height: 1.3; }}
    .card-credits {{ font-size: 0.75rem; color: #555; white-space: nowrap; margin-left: 4px; }}
    .card-footer  {{ position: absolute; bottom: 0; left: 0; right: 0; padding: 2px 6px 4px; display: flex; gap: 4px; flex-wrap: wrap; min-height: 16px; }}
    .card-footer:not(:empty) {{ background: rgba(255,255,255,0.85); }}
    .course-card.fill-category .card-name,
    .course-card.fill-category .card-credits {{
      color: #222;
    }}
    .course-card.fill-category .card-footer:not(:empty) {{
      background: rgba(255, 255, 255, 0.45);
    }}
    .course-card.fill-category .tag {{
      background: rgba(0,0,0,0.12);
      color: #222;
      border: 1px solid rgba(0,0,0,0.2);
    }}

    /* Tags */
    .tag {{
      font-size: 0.65rem;
      border-radius: 10px;
      padding: 1px 6px;
      font-weight: 600;
    }}
{tag_rules}
{fill_rules}

    /* Setas SVG */
    .arrows-layer {{
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
      z-index: 0;
    }}
    .arrow-line {{
      fill: none;
      stroke: #1a3a6b;
    }}
    .arrows-layer.link-style-paths .arrow-line {{
      opacity: 0.6;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .arrows-layer.link-style-arrows .arrow-line {{
      opacity: 0.9;
      stroke-linecap: butt;
      stroke-linejoin: miter;
    }}
    .arrow-group[data-type="special"] .arrow-line {{
      stroke: #b45309;
    }}
    .arrow-group[data-type="corequisite"] .arrow-line {{
      stroke: #475569;
    }}
    .arrows-layer.hidden .arrow-group {{ display: none; }}
    .arrow-label {{
      font-size: 0.65rem;
      fill: #555;
    }}

    /* Legenda */
    .legend-panel {{
      min-width: 180px;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 6px;
      padding: 12px;
      flex-shrink: 0;
    }}
    .legend-title {{
      font-size: 0.9rem;
      font-weight: bold;
      margin-bottom: 10px;
      border-bottom: 1px solid #ddd;
      padding-bottom: 6px;
    }}
    .legend-list {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 6px 10px;
      align-items: center;
      font-size: 0.78rem;
    }}
    .legend-list dt {{ display: flex; align-items: center; }}
    .legend-subtitle {{
      grid-column: 1 / -1;
      margin-top: 8px;
      padding-top: 6px;
      border-top: 1px solid #e5e7eb;
      font-weight: 700;
      color: #374151;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .legend-subtitle-spacer {{ display: none; }}
    .category-chip {{
      display: inline-block;
      width: 24px;
      height: 12px;
      border-radius: 999px;
      border: 1px solid #9ca3af;
      background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
    }}
    .legend-toggle {{
      margin-top: 20px;
      padding-top: 12px;
      border-top: 1px solid #ddd;
      font-size: 0.8rem;
    }}
    .legend-toggle label {{
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-weight: 600;
      color: #1a3a6b;
    }}
    .legend-toggle input[type="checkbox"] {{
      width: 15px;
      height: 15px;
      cursor: pointer;
      accent-color: #1a3a6b;
    }}

    /* Popup */
    .popup {{
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 16px;
      animation: popup-backdrop-in 0.18s ease;
    }}
    .popup[hidden] {{ display: none; }}
    @keyframes popup-backdrop-in {{
      from {{ background: rgba(0,0,0,0); }}
      to   {{ background: rgba(0,0,0,0.5); }}
    }}
    .popup-content {{
      background: #fff;
      border-radius: 12px;
      max-width: 500px;
      width: 100%;
      position: relative;
      max-height: 88vh;
      overflow-y: auto;
      box-shadow: 0 24px 64px rgba(0,0,0,0.28);
      animation: popup-slide-in 0.18s ease;
    }}
    @keyframes popup-slide-in {{
      from {{ opacity: 0; transform: translateY(-12px) scale(0.97); }}
      to   {{ opacity: 1; transform: translateY(0)    scale(1); }}
    }}
    .popup-close {{
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
    }}
    .popup-close:hover {{ background: rgba(255,255,255,0.32); }}
    .popup-close svg   {{ width: 15px; height: 15px; }}
    .popup-header {{
      background: #1a3a6b;
      color: #fff;
      padding: 22px 52px 18px 22px;
      border-radius: 12px 12px 0 0;
    }}
    .popup-code {{
      display: block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      opacity: 0.7;
      margin-bottom: 4px;
    }}
    .popup-name {{
      font-size: 1.1rem;
      font-weight: 700;
      line-height: 1.35;
      margin-bottom: 12px;
    }}
    .popup-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .popup-header .tag {{
      border: 1px solid rgba(255,255,255,0.3);
    }}
    .popup-body {{
      padding: 18px 20px 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .popup-stats {{
      display: flex;
      gap: 10px;
    }}
    .popup-stat {{
      flex: 1;
      background: #f2f5fb;
      border: 1px solid #dde3f0;
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}
    .popup-stat-value {{
      font-size: 1.3rem;
      font-weight: 700;
      color: #1a3a6b;
      line-height: 1;
      margin-bottom: 4px;
    }}
    .popup-stat-label {{
      font-size: 0.7rem;
      color: #777;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }}
    .popup-section-title {{
      font-size: 0.7rem;
      font-weight: 700;
      color: #1a3a6b;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      margin-bottom: 8px;
      padding-bottom: 5px;
      border-bottom: 2px solid #e8ecf5;
    }}
    .popup-syllabus-text {{
      font-size: 0.84rem;
      color: #444;
      line-height: 1.65;
    }}
    .popup-req-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }}
    .popup-req-item {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      font-size: 0.82rem;
      color: #333;
    }}
    .popup-req-item::before {{
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #1a3a6b;
      flex-shrink: 0;
      position: relative;
      top: -1px;
    }}
    .popup-req-code {{
      font-weight: 700;
      color: #1a3a6b;
      font-size: 0.77rem;
      white-space: nowrap;
    }}
    .popup-req-name   {{ color: #555; }}
    .popup-empty {{
      font-size: 0.82rem;
      color: #aaa;
      font-style: italic;
    }}

    /* Totalizador de créditos */
    .credits-summary {{
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid #ddd;
    }}
    .credits-summary-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.78rem;
    }}
    .credits-summary-table td {{
      padding: 3px 4px;
      vertical-align: middle;
    }}
    .credits-total-row td {{
      font-weight: 700;
      padding-bottom: 6px;
      border-bottom: 1px solid #eee;
    }}
    .credits-value {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .credits-summary-table tr:not(.credits-total-row) td:first-child {{
      padding-top: 4px;
    }}"""


# ─── JavaScript embutido ─────────────────────────────────────────────────────


def _render_js(data: CurriculumFile) -> str:
    courses_json = json.dumps(
        [
            {
                "code": c.code,
                "name": c.name,
                "hours": c.hours,
                "credits": c.credits,
                "syllabus": c.syllabus,
                "tags": c.tags,
                "category": c.category,
            }
            for c in data.courses
        ],
        ensure_ascii=False,
    )

    requirements_json = json.dumps(
        [
            {
                "type": r.type,
                "from": r.from_code,
                "to": r.to,
                "description": r.description,
                "min_credits": r.min_credits,
            }
            for r in data.requirements
        ],
        ensure_ascii=False,
    )

    categories_json = json.dumps(
        [{"id": c.id, "color": c.color} for c in data.categories], ensure_ascii=False
    )

    return f"""\
(function () {{
  'use strict';

  const COURSES = {courses_json};
  const REQUIREMENTS = {requirements_json};
  const CATEGORIES = {categories_json};

  const courseMap = new Map(COURSES.map(c => [c.code, c]));
  const categoryColorMap = new Map(
    CATEGORIES
      .filter(c => typeof c.color === 'string' && c.color.trim() !== '')
      .map(c => [c.id, c.color])
  );

  // ── Escala responsiva da matriz ──────────────────────────────────────────────
  function applyMatrixScale() {{
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
  }}

  applyMatrixScale();
  window.addEventListener('resize', applyMatrixScale);

  // ── Toggle de setas ─────────────────────────────────────────────────────────
  const toggleArrows = document.getElementById('toggle-arrows');
  const arrowsLayer  = document.querySelector('.arrows-layer');

  arrowsLayer.classList.add('hidden');

  toggleArrows.addEventListener('change', () => {{
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  }});

  // ── Hover sobre cartões ─────────────────────────────────────────────────────
  const allCards  = Array.from(document.querySelectorAll('.course-card'));
  const allArrows = Array.from(document.querySelectorAll('.arrow-group'));

  function getRelated(code) {{
    const prereqs    = new Set();
    const dependents = new Set();
    for (const req of REQUIREMENTS) {{
      if (req.type === 'credit_requirement') continue;
      if (req.to === code && req.from)   prereqs.add(req.from);
      if (req.from === code)             dependents.add(req.to);
    }}
    return {{ prereqs, dependents }};
  }}

  function onCardEnter(code) {{
    const {{ prereqs, dependents }} = getRelated(code);
    const related = new Set([code, ...prereqs, ...dependents]);

    allCards.forEach(card => {{
      const c = card.dataset.code;
      card.classList.toggle('highlighted', related.has(c));
      card.classList.toggle('faded', !related.has(c));
    }});

    arrowsLayer.classList.remove('hidden');

    allArrows.forEach(arrow => {{
      const from = arrow.dataset.from;
      const to   = arrow.dataset.to;
      const active = (from === code || to === code);
      arrow.style.display = active ? '' : 'none';
    }});
  }}

  function onCardLeave() {{
    allCards.forEach(card => {{
      card.classList.remove('highlighted', 'faded');
    }});
    allArrows.forEach(arrow => {{
      arrow.style.display = '';
    }});
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  }}

  allCards.forEach(card => {{
    card.addEventListener('mouseenter', () => onCardEnter(card.dataset.code));
    card.addEventListener('mouseleave', onCardLeave);
    card.addEventListener('focusin',    () => onCardEnter(card.dataset.code));
    card.addEventListener('focusout',   onCardLeave);
  }});

  // ── Popup de detalhes ───────────────────────────────────────────────────────
  const popup       = document.getElementById('course-popup');
  const popupClose  = popup.querySelector('.popup-close');
  const popupHeader = popup.querySelector('.popup-header');
  const defaultPopupHeaderColor = '#1a3a6b';

  function openPopup(code) {{
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

    const tagsEl = document.getElementById('popup-tags');
    tagsEl.innerHTML = '';
    course.tags.forEach(function(tag) {{
      const span = document.createElement('span');
      span.className = 'tag tag-' + tag;
      span.textContent = tag;
      tagsEl.appendChild(span);
    }});

    const prereqs = REQUIREMENTS
      .filter(function(r) {{ return r.to === code && r.from; }})
      .map(function(r) {{
        const c = courseMap.get(r.from);
        return {{ code: r.from, name: c ? c.name : '', desc: r.description }};
      }});
    const creditReq = REQUIREMENTS.find(function(r) {{ return r.type === 'credit_requirement' && r.to === code; }});

    const prereqEl = document.getElementById('popup-prereqs');
    prereqEl.innerHTML = '';
    if (prereqs.length === 0 && !creditReq) {{
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhum pr\u00e9-requisito';
      prereqEl.appendChild(none);
    }} else {{
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      prereqs.forEach(function(p) {{
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
      }});
      if (creditReq) {{
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const span = document.createElement('span');
        span.className = 'popup-req-name';
        span.textContent = 'M\u00edn. ' + creditReq.min_credits + ' cr\u00e9ditos cursados';
        li.appendChild(span);
        ul.appendChild(li);
      }}
      prereqEl.appendChild(ul);
    }}

    const dependents = REQUIREMENTS
      .filter(function(r) {{ return r.from === code && r.to; }})
      .map(function(r) {{
        const c = courseMap.get(r.to);
        return {{ code: r.to, name: c ? c.name : '' }};
      }});

    const depsEl = document.getElementById('popup-dependents');
    depsEl.innerHTML = '';
    if (dependents.length === 0) {{
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhuma depend\u00eancia';
      depsEl.appendChild(none);
    }} else {{
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      dependents.forEach(function(d) {{
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
      }});
      depsEl.appendChild(ul);
    }}

    popup.hidden = false;
    popupClose.focus();
  }}

  function closePopup() {{
    popup.hidden = true;
  }}

  allCards.forEach(card => {{
    card.addEventListener('click', () => openPopup(card.dataset.code));
    card.addEventListener('keydown', e => {{
      if (e.key === 'Enter' || e.key === ' ') {{
        e.preventDefault();
        openPopup(card.dataset.code);
      }}
    }});
  }});

  popupClose.addEventListener('click', closePopup);
  popup.addEventListener('click', e => {{ if (e.target === popup) closePopup(); }});
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePopup(); }});
}})();"""
