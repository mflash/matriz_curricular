from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .layout import COL_GAP, ROW_GAP, find_card
from .types import (
    ArrowRoute,
    CardRect,
    CurriculumFile,
    LayoutData,
    Point,
    RequirementInput,
    RouteData,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de roteamento
# ─────────────────────────────────────────────────────────────────────────────

TURN_PENALTY = 14
CONGESTION_PENALTY = 18

# ─────────────────────────────────────────────────────────────────────────────
# Roteamento ortogonal com busca em grafo de corredores
# ─────────────────────────────────────────────────────────────────────────────


def compute_routes(data: CurriculumFile, layout: LayoutData) -> RouteData:
    arrows: List[ArrowRoute] = []
    segment_usage: Dict[str, int] = {}

    outgoing_by_from: Dict[str, List[int]] = {}
    incoming_by_to: Dict[str, List[int]] = {}

    for index, req in enumerate(data.requirements):
        if req.type == "credit_requirement":
            continue
        if not req.from_code:
            continue
        outgoing_by_from.setdefault(req.from_code, []).append(index)
        incoming_by_to.setdefault(req.to, []).append(index)

    # Ordena irmãos por posição vertical para reduzir cruzamentos
    for from_code, siblings in outgoing_by_from.items():
        siblings.sort(
            key=lambda idx: (_course_center_y(layout, data.requirements[idx].to), idx)
        )

    for to_code, siblings in incoming_by_to.items():

        def _key_incoming(idx):
            fc = data.requirements[idx].from_code
            return (_course_center_y(layout, fc) if fc else math.inf, idx)

        siblings.sort(key=_key_incoming)

    for index, req in enumerate(data.requirements):
        if req.type == "credit_requirement":
            continue
        if not req.from_code:
            continue

        from_card = find_card(layout, req.from_code)
        to_card = find_card(layout, req.to)
        if not from_card or not to_card:
            continue

        sibs_out = outgoing_by_from.get(req.from_code, [])
        sibs_in = incoming_by_to.get(req.to, [])
        lane_offsets = {
            "source": _lane_offset(index, sibs_out),
            "target": _lane_offset(index, sibs_in),
        }

        points = _route_arrow(
            from_card, to_card, req, layout, lane_offsets, segment_usage
        )
        _register_segment_usage(points, segment_usage)
        arrows.append(
            ArrowRoute(
                requirement_index=index,
                type=req.type,
                points=points,
                label=req.description if req.type == "special" else None,
            )
        )

    return RouteData(arrows=arrows)


def _route_arrow(
    from_card: CardRect,
    to_card: CardRect,
    req: RequirementInput,
    layout: LayoutData,
    lane_offsets: dict,
    segment_usage: Dict[str, int],
) -> List[Point]:
    if req.type == "corequisite":
        return _route_corequisite(from_card, to_card, lane_offsets)
    return _route_forward_arrow(from_card, to_card, layout, lane_offsets, segment_usage)


def _route_forward_arrow(
    from_card: CardRect,
    to_card: CardRect,
    layout: LayoutData,
    lane_offsets: dict,
    segment_usage: Dict[str, int],
) -> List[Point]:
    start_x = from_card.x + from_card.width
    start_y = _clamp(
        from_card.y + from_card.height / 2 + lane_offsets["source"],
        from_card.y + 8,
        from_card.y + from_card.height - 8,
    )
    end_x = to_card.x
    end_y = _clamp(
        to_card.y + to_card.height / 2 + lane_offsets["target"],
        to_card.y + 8,
        to_card.y + to_card.height - 8,
    )

    from_col_idx = _find_col_index_by_x(layout, from_card.x)
    to_col_idx = _find_col_index_by_x(layout, to_card.x)
    is_adjacent = (
        from_col_idx != -1 and to_col_idx != -1 and to_col_idx == from_col_idx + 1
    )

    from_center_y = from_card.y + from_card.height / 2
    to_center_y = to_card.y + to_card.height / 2
    is_row_aligned = abs(from_center_y - to_center_y) <= 1
    overlap_low = max(from_card.y + 8, to_card.y + 8)
    overlap_high = min(
        from_card.y + from_card.height - 8, to_card.y + to_card.height - 8
    )

    if is_adjacent and is_row_aligned and overlap_low <= overlap_high:
        shared_y = _clamp((from_center_y + to_center_y) / 2, overlap_low, overlap_high)
        return [Point(start_x, shared_y), Point(end_x, shared_y)]

    if to_card.x <= from_card.x + from_card.width:
        return _legacy_forward_route(
            start_x, start_y, end_x, end_y, from_card, to_card, layout
        )

    lane_inset = max(10, COL_GAP * 0.35)
    source_lane_x = start_x + lane_inset
    target_lane_x = end_x - lane_inset

    if target_lane_x <= source_lane_x:
        return _legacy_forward_route(
            start_x, start_y, end_x, end_y, from_card, to_card, layout
        )

    lane_xs = _build_lane_xs(layout, from_card, to_card, source_lane_x, target_lane_x)
    corridor_ys = _build_horizontal_corridors(layout)

    graph_path = _find_best_corridor_path(
        lane_xs=lane_xs,
        corridor_ys=corridor_ys,
        source_lane_x=source_lane_x,
        target_lane_x=target_lane_x,
        start_y=start_y,
        end_y=end_y,
        from_card=from_card,
        to_card=to_card,
        segment_usage=segment_usage,
    )

    if not graph_path:
        return _legacy_forward_route(
            start_x, start_y, end_x, end_y, from_card, to_card, layout
        )

    base_path = _simplify_orthogonal_path(
        [
            Point(start_x, start_y),
            Point(source_lane_x, start_y),
            *graph_path,
            Point(target_lane_x, end_y),
            Point(end_x, end_y),
        ]
    )

    return _apply_segment_lane_offsets(base_path, segment_usage)


def _legacy_forward_route(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    from_card: CardRect,
    to_card: CardRect,
    layout: LayoutData,
) -> List[Point]:
    mid_x = _find_mid_channel(from_card, to_card, layout)
    if start_y == end_y:
        return [Point(start_x, start_y), Point(end_x, end_y)]
    return [
        Point(start_x, start_y),
        Point(mid_x, start_y),
        Point(mid_x, end_y),
        Point(end_x, end_y),
    ]


def _build_horizontal_corridors(layout: LayoutData) -> List[float]:
    all_cards = [card for col in layout.columns for card in col.cards]
    if not all_cards:
        return []
    first_y = min(card.y for card in all_cards)
    card_h = all_cards[0].height
    max_rows = max(len(col.cards) for col in layout.columns)
    return [
        first_y - ROW_GAP / 2 + row * (card_h + ROW_GAP) for row in range(max_rows + 1)
    ]


def _build_lane_xs(
    layout: LayoutData,
    from_card: CardRect,
    to_card: CardRect,
    source_lane_x: float,
    target_lane_x: float,
) -> List[float]:
    from_col_idx = _find_col_index_by_x(layout, from_card.x)
    to_col_idx = _find_col_index_by_x(layout, to_card.x)
    if from_col_idx == -1 or to_col_idx == -1:
        return sorted({source_lane_x, target_lane_x})

    lane_xs: set = {source_lane_x, target_lane_x}
    min_col = min(from_col_idx, to_col_idx)
    max_col = max(from_col_idx, to_col_idx)

    for left_col in range(min_col + 1, max_col - 1):
        lx = layout.columns[left_col].x
        card_w = (
            layout.columns[left_col].cards[0].width
            if layout.columns[left_col].cards
            else from_card.width
        )
        lane_xs.add(lx + card_w + COL_GAP / 2)

    return sorted(lane_xs)


def _find_col_index_by_x(layout: LayoutData, x: float) -> int:
    best_idx = -1
    best_dist = math.inf
    for i, col in enumerate(layout.columns):
        dist = abs(col.x - x)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx


def _find_best_corridor_path(
    lane_xs: List[float],
    corridor_ys: List[float],
    source_lane_x: float,
    target_lane_x: float,
    start_y: float,
    end_y: float,
    from_card: CardRect,
    to_card: CardRect,
    segment_usage: Dict[str, int],
) -> Optional[List[Point]]:
    if len(lane_xs) < 2 or not corridor_ys:
        return None

    filtered_ys = [
        y
        for y in corridor_ys
        if not _is_inside_card_band(y, from_card)
        and not _is_inside_card_band(y, to_card)
    ]
    ys = filtered_ys if filtered_ys else corridor_ys
    xs = lane_xs

    try:
        sxi = xs.index(source_lane_x)
        txi = xs.index(target_lane_x)
    except ValueError:
        return None

    INF = math.inf
    dist: Dict[Tuple, float] = {}
    prev: Dict[Tuple, Optional[Tuple]] = {}

    # Initialise source column
    for yi, y in enumerate(ys):
        state = (sxi, yi, "S")
        anchor_a = Point(source_lane_x, start_y)
        anchor_b = Point(source_lane_x, y)
        init_cost = abs(start_y - y) + _segment_congestion_cost(
            anchor_a, anchor_b, segment_usage
        )
        dist[state] = init_cost
        prev[state] = None

    # Dijkstra (no heuristic — grid is small)
    visited: set = set()

    while True:
        # Find minimum unvisited
        current = None
        best = INF
        for state, cost in dist.items():
            if state not in visited and cost < best:
                best = cost
                current = state
        if current is None:
            break

        visited.add(current)
        xi, yi, d = current
        curr_dist = dist[current]

        neighbors: List[Tuple[int, int, str]] = []
        if xi > 0:
            neighbors.append((xi - 1, yi, "H"))
        if xi < len(xs) - 1:
            neighbors.append((xi + 1, yi, "H"))
        if yi > 0:
            neighbors.append((xi, yi - 1, "V"))
        if yi < len(ys) - 1:
            neighbors.append((xi, yi + 1, "V"))

        for nxi, nyi, nd in neighbors:
            a = Point(xs[xi], ys[yi])
            b = Point(xs[nxi], ys[nyi])
            base = abs(a.x - b.x) + abs(a.y - b.y)
            turn = TURN_PENALTY if d != "S" and d != nd else 0
            congestion = _segment_congestion_cost(a, b, segment_usage)
            next_state = (nxi, nyi, nd)
            new_dist = curr_dist + base + turn + congestion
            if dist.get(next_state, INF) > new_dist:
                dist[next_state] = new_dist
                prev[next_state] = current

    # Find best goal on target column
    best_goal: Optional[Tuple] = None
    best_goal_dist = INF

    for state, cost in dist.items():
        nxi, nyi, nd = state
        if nxi != txi:
            continue
        anchor_a = Point(target_lane_x, ys[nyi])
        anchor_b = Point(target_lane_x, end_y)
        tail = abs(ys[nyi] - end_y) + _segment_congestion_cost(
            anchor_a, anchor_b, segment_usage
        )
        turn = TURN_PENALTY if nd == "H" else 0
        total = cost + tail + turn
        if total < best_goal_dist:
            best_goal_dist = total
            best_goal = state

    if best_goal is None:
        return None

    # Reconstruct path
    reversed_pts: List[Point] = []
    state = best_goal
    while state is not None:
        xi, yi, _ = state
        reversed_pts.append(Point(xs[xi], ys[yi]))
        state = prev.get(state)

    return list(reversed(reversed_pts))


def _segment_congestion_cost(
    a: Point, b: Point, segment_usage: Dict[str, int]
) -> float:
    if a.x == b.x and a.y == b.y:
        return 0.0
    used = segment_usage.get(_segment_key(a, b), 0)
    return used * CONGESTION_PENALTY


def _is_inside_card_band(y: float, card: CardRect) -> bool:
    return card.y + 2 < y < card.y + card.height - 2


def _register_segment_usage(points: List[Point], segment_usage: Dict[str, int]) -> None:
    for i in range(1, len(points)):
        a, b = points[i - 1], points[i]
        if a.x == b.x and a.y == b.y:
            continue
        key = _segment_key(a, b)
        segment_usage[key] = segment_usage.get(key, 0) + 1


def _segment_key(a: Point, b: Point) -> str:
    if a.x == b.x:
        y1, y2 = (a.y, b.y) if a.y <= b.y else (b.y, a.y)
        return f"V|{a.x}|{y1}|{y2}"
    if a.y == b.y:
        x1, x2 = (a.x, b.x) if a.x <= b.x else (b.x, a.x)
        return f"H|{a.y}|{x1}|{x2}"
    left = a if a.x < b.x else b
    right = b if a.x < b.x else a
    return f"D|{left.x}|{left.y}|{right.x}|{right.y}"


def _simplify_orthogonal_path(points: List[Point]) -> List[Point]:
    if len(points) <= 2:
        return points

    deduped: List[Point] = []
    for p in points:
        if not deduped or deduped[-1].x != p.x or deduped[-1].y != p.y:
            deduped.append(p)

    if len(deduped) <= 2:
        return deduped

    simplified: List[Point] = [deduped[0]]
    for i in range(1, len(deduped) - 1):
        a = simplified[-1]
        b = deduped[i]
        c = deduped[i + 1]
        collinear = (a.x == b.x == c.x) or (a.y == b.y == c.y)
        if not collinear:
            simplified.append(b)
    simplified.append(deduped[-1])
    return simplified


def _apply_segment_lane_offsets(
    points: List[Point], segment_usage: Dict[str, int]
) -> List[Point]:
    if len(points) < 5:
        return points

    first_seg = 1
    last_seg = len(points) - 3
    if last_seg < first_seg:
        return points

    seg_offset: Dict[int, float] = {}
    for i in range(first_seg, last_seg + 1):
        a, b = points[i], points[i + 1]
        if not _is_orthogonal_segment(a, b):
            continue
        usage = segment_usage.get(_segment_key(a, b), 0)
        seg_offset[i] = _alternating_lane_offset(usage, 3.5)

    shifted = [Point(p.x, p.y) for p in points]

    for i in range(2, len(shifted) - 2):
        left_idx = i - 1
        right_idx = i

        left_off = seg_offset.get(left_idx, 0.0)
        right_off = seg_offset.get(right_idx, 0.0)

        left_seg_a = points[left_idx]
        left_seg_b = points[left_idx + 1]
        right_seg_a = points[right_idx]
        right_seg_b = points[right_idx + 1]

        left_vertical = _is_vertical_segment(left_seg_a, left_seg_b)
        right_vertical = _is_vertical_segment(right_seg_a, right_seg_b)
        left_horizontal = _is_horizontal_segment(left_seg_a, left_seg_b)
        right_horizontal = _is_horizontal_segment(right_seg_a, right_seg_b)

        x_shift = right_off if right_vertical else (left_off if left_vertical else 0.0)
        y_shift = (
            right_off if right_horizontal else (left_off if left_horizontal else 0.0)
        )

        shifted[i].x += x_shift
        shifted[i].y += y_shift

    return _ensure_orthogonal(shifted)


def _alternating_lane_offset(usage: int, spacing: float) -> float:
    if usage <= 0:
        return 0.0
    step = math.ceil(usage / 2)
    return (1 if usage % 2 == 1 else -1) * step * spacing


def _ensure_orthogonal(points: List[Point]) -> List[Point]:
    if len(points) <= 2:
        return points
    out: List[Point] = [points[0]]
    for i in range(1, len(points)):
        prev = out[-1]
        curr = points[i]
        if prev.x != curr.x and prev.y != curr.y:
            out.append(Point(curr.x, prev.y))
        out.append(curr)
    return _simplify_orthogonal_path(out)


def _is_orthogonal_segment(a: Point, b: Point) -> bool:
    return _is_vertical_segment(a, b) or _is_horizontal_segment(a, b)


def _is_vertical_segment(a: Point, b: Point) -> bool:
    return a.x == b.x and a.y != b.y


def _is_horizontal_segment(a: Point, b: Point) -> bool:
    return a.y == b.y and a.x != b.x


def _route_corequisite(
    from_card: CardRect,
    to_card: CardRect,
    lane_offsets: dict,
) -> List[Point]:
    from_center_x = from_card.x + from_card.width / 2
    to_center_x = to_card.x + to_card.width / 2
    is_col_aligned = abs(from_center_x - to_center_x) <= 1

    gap_down = abs(to_card.y - (from_card.y + from_card.height))
    gap_up = abs(from_card.y - (to_card.y + to_card.height))
    is_adjacent_vertical = abs(gap_down - ROW_GAP) <= 1 or abs(gap_up - ROW_GAP) <= 1

    overlap_left = max(from_card.x + 8, to_card.x + 8)
    overlap_right = min(
        from_card.x + from_card.width - 8, to_card.x + to_card.width - 8
    )

    if is_col_aligned and is_adjacent_vertical and overlap_left <= overlap_right:
        shared_x = _clamp(
            (from_center_x + to_center_x) / 2, overlap_left, overlap_right
        )
        downward = to_card.y >= from_card.y
        start_y = (from_card.y + from_card.height) if downward else from_card.y
        end_y = to_card.y if downward else (to_card.y + to_card.height)
        return [Point(shared_x, start_y), Point(shared_x, end_y)]

    start_x = _clamp(
        from_card.x + from_card.width / 2 + lane_offsets["source"],
        from_card.x + 8,
        from_card.x + from_card.width - 8,
    )
    start_y = from_card.y + from_card.height

    end_x = _clamp(
        to_card.x + to_card.width / 2 + lane_offsets["target"],
        to_card.x + 8,
        to_card.x + to_card.width - 8,
    )
    end_y = to_card.y

    mid_y = (
        start_y + ROW_GAP / 2 + (lane_offsets["source"] - lane_offsets["target"]) * 0.35
    )

    return [
        Point(start_x, start_y),
        Point(start_x, mid_y),
        Point(end_x, mid_y),
        Point(end_x, end_y),
    ]


def _lane_offset(index: int, siblings: List[int]) -> float:
    if len(siblings) <= 1:
        return 0.0
    pos = siblings.index(index) if index in siblings else -1
    if pos == -1:
        return 0.0
    spacing = 8
    center = (len(siblings) - 1) / 2
    return (pos - center) * spacing


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _course_center_y(layout: LayoutData, course_code: str) -> float:
    card = find_card(layout, course_code)
    if card is None:
        return math.inf
    return card.y + card.height / 2


def _find_mid_channel(
    from_card: CardRect, to_card: CardRect, layout: LayoutData
) -> float:
    right_edge_from = from_card.x + from_card.width
    left_edge_to = to_card.x
    return (right_edge_from + left_edge_to) / 2
