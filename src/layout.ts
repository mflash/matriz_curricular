import { CurriculumFile } from './types';
import { CardRect, ColumnLayout, LayoutData } from './types';

// ─── Constantes de dimensionamento ───────────────────────────────────────────

export const CARD_WIDTH   = 140;
export const CARD_HEIGHT  = 84;
export const COL_GAP      = 60;   // espaço horizontal entre colunas (canal para setas)
export const ROW_GAP      = 24;   // espaço vertical entre cartões (canal para setas)
export const COL_PADDING  = 10;   // margem interna horizontal da coluna
export const PAGE_MARGIN  = 20;   // margem externa da grade
export const HEADER_H     = 80;   // altura do cabeçalho do curso
export const COL_HEADER_H = 48;   // altura do cabeçalho de cada coluna (nível)
export const COL_FOOTER_H = 32;   // altura do rodapé de cada coluna (total créditos)

// ─── Ponto de entrada ─────────────────────────────────────────────────────────

export function computeLayout(data: CurriculumFile): LayoutData {
  const { curriculum, courses } = data;

  const columns: ColumnLayout[] = [];

  for (let level = 1; level <= curriculum.levels; level++) {
    const levelCourses = courses
      .filter(c => c.level === level);

    const totalCredits = levelCourses.reduce((sum, c) => sum + c.credits, 0);

    const colX = (level - 1) * (CARD_WIDTH + COL_GAP);
    const cardsStartY = COL_HEADER_H + ROW_GAP;

    const cards: CardRect[] = levelCourses.map((course, i) => ({
      courseCode: course.code,
      x: colX,
      y: cardsStartY + i * (CARD_HEIGHT + ROW_GAP),
      width: CARD_WIDTH,
      height: CARD_HEIGHT,
    }));

    columns.push({ level, x: colX, totalCredits, cards });
  }

  const canvasWidth =
    curriculum.levels * CARD_WIDTH +
    (curriculum.levels - 1) * COL_GAP;

  const maxCards = Math.max(...columns.map(col => col.cards.length));
  const canvasHeight =
    COL_HEADER_H +
    ROW_GAP +
    maxCards * (CARD_HEIGHT + ROW_GAP) +
    COL_FOOTER_H +
    PAGE_MARGIN;

  return { canvasWidth, canvasHeight, columns };
}

// ─── Utilitários exportados ───────────────────────────────────────────────────

export function findCard(layout: LayoutData, courseCode: string): CardRect | undefined {
  for (const col of layout.columns) {
    const card = col.cards.find(c => c.courseCode === courseCode);
    if (card) return card;
  }
  return undefined;
}
