from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .layout import CARD_HEIGHT, CARD_WIDTH, COL_HEADER_H, ROW_GAP
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

_ASSETS_DIR = Path(__file__).with_name("assets")
_ASSET_CACHE: Dict[str, str] = {}


def _load_asset_template(name: str) -> str:
    if name not in _ASSET_CACHE:
        _ASSET_CACHE[name] = (_ASSETS_DIR / name).read_text(encoding="utf-8")
    return _ASSET_CACHE[name]


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
    row_gap: int = ROW_GAP,
) -> str:
    course_map = {c.code: c for c in data.courses}
    category_map = {c.id: c for c in data.categories}
    unique_tags = list(dict.fromkeys(tag for c in data.courses for tag in c.tags))
    credit_req_map: Dict[str, int] = {}
    for req in data.requirements:
        if req.type == "credit_requirement" and req.min_credits is not None:
            credit_req_map[req.to] = req.min_credits

    use_category_fill = data.card_fill_style == "category"

    css_block = _render_css(unique_tags, data.categories, row_gap)
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
        f'      <dt><span class="tag tag-{_esc(t)}">{_esc(t)}</span></dt>\n      <dd>Disciplinas {_esc(t)}</dd>'
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


def _render_css(tags: List[str], categories: List[CategoryInput], row_gap: int) -> str:
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

    css_template = _load_asset_template("template.css")
    return (
        css_template.replace("{{CARD_WIDTH}}", str(CARD_WIDTH))
        .replace("{{CARD_HEIGHT}}", str(CARD_HEIGHT))
        .replace("{{COL_HEADER_H}}", str(COL_HEADER_H))
        .replace("{{ROW_GAP}}", str(row_gap))
        .replace("{{TAG_RULES}}", tag_rules)
        .replace("{{FILL_RULES}}", fill_rules)
    )


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

    js_template = _load_asset_template("template.js")
    return (
        js_template.replace("{{COURSES_JSON}}", courses_json)
        .replace("{{REQUIREMENTS_JSON}}", requirements_json)
        .replace("{{CATEGORIES_JSON}}", categories_json)
    )
