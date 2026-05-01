from __future__ import annotations

from typing import List, Optional

from .types import CardRect, ColumnLayout, CurriculumFile, LayoutData

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de dimensionamento
# ─────────────────────────────────────────────────────────────────────────────

CARD_WIDTH = 140
CARD_HEIGHT = 72
COL_GAP = 60  # espaço horizontal entre colunas (canal para setas)
ROW_GAP = 24  # espaço vertical entre cartões (canal para setas)
COL_PADDING = 10  # margem interna horizontal da coluna
PAGE_MARGIN = 20  # margem externa da grade
HEADER_H = 80  # altura do cabeçalho do curso
COL_HEADER_H = 48  # altura do cabeçalho de cada coluna (nível)
COL_FOOTER_H = 32  # altura do rodapé de cada coluna (total créditos)

# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────


def compute_layout(data: CurriculumFile, row_gap: int = ROW_GAP) -> LayoutData:
    columns: List[ColumnLayout] = []

    for level in range(1, data.curriculum.levels + 1):
        level_courses = [c for c in data.courses if c.level == level]
        total_credits = sum(c.credits for c in level_courses)
        col_x = (level - 1) * (CARD_WIDTH + COL_GAP)
        cards_start_y = COL_HEADER_H + row_gap

        cards = [
            CardRect(
                course_code=course.code,
                x=col_x,
                y=cards_start_y + i * (CARD_HEIGHT + row_gap),
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
            )
            for i, course in enumerate(level_courses)
        ]

        columns.append(
            ColumnLayout(level=level, x=col_x, total_credits=total_credits, cards=cards)
        )

    canvas_width = (
        data.curriculum.levels * CARD_WIDTH + (data.curriculum.levels - 1) * COL_GAP
    )

    max_cards = max((len(col.cards) for col in columns), default=0)
    canvas_height = (
        COL_HEADER_H
        + row_gap
        + max_cards * (CARD_HEIGHT + row_gap)
        + COL_FOOTER_H
        + PAGE_MARGIN
    )

    return LayoutData(
        canvas_width=canvas_width, canvas_height=canvas_height, columns=columns
    )


def find_card(layout: LayoutData, course_code: str) -> Optional[CardRect]:
    for col in layout.columns:
        for card in col.cards:
            if card.course_code == course_code:
                return card
    return None
