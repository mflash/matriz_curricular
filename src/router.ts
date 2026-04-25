import { CurriculumFile, RequirementInput, Point, ArrowRoute, RouteData, LayoutData, CardRect } from './types';
import { findCard, COL_GAP, ROW_GAP } from './layout';

// ─── Ponto de entrada ─────────────────────────────────────────────────────────

export function computeRoutes(data: CurriculumFile, layout: LayoutData): RouteData {
  const arrows: ArrowRoute[] = [];
  const segmentUsage = new Map<string, number>();

  const outgoingByFrom = new Map<string, number[]>();
  const incomingByTo = new Map<string, number[]>();

  data.requirements.forEach((req, index) => {
    if (req.type === 'credit_requirement') return;
    if (!req.from) return;

    const out = outgoingByFrom.get(req.from) ?? [];
    out.push(index);
    outgoingByFrom.set(req.from, out);

    const incoming = incomingByTo.get(req.to) ?? [];
    incoming.push(index);
    incomingByTo.set(req.to, incoming);
  });

  // Ordena os "irmãos" por posição vertical para reduzir cruzamentos.
  for (const [fromCode, siblings] of outgoingByFrom.entries()) {
    siblings.sort((a, b) => {
      const reqA = data.requirements[a];
      const reqB = data.requirements[b];
      const toYA = courseCenterY(layout, reqA.to);
      const toYB = courseCenterY(layout, reqB.to);
      if (toYA !== toYB) return toYA - toYB;
      return a - b;
    });
    outgoingByFrom.set(fromCode, siblings);
  }

  for (const [toCode, siblings] of incomingByTo.entries()) {
    siblings.sort((a, b) => {
      const reqA = data.requirements[a];
      const reqB = data.requirements[b];
      const fromYA = reqA.from ? courseCenterY(layout, reqA.from) : Number.POSITIVE_INFINITY;
      const fromYB = reqB.from ? courseCenterY(layout, reqB.from) : Number.POSITIVE_INFINITY;
      if (fromYA !== fromYB) return fromYA - fromYB;
      return a - b;
    });
    incomingByTo.set(toCode, siblings);
  }

  data.requirements.forEach((req, index) => {
    if (req.type === 'credit_requirement') return;
    if (!req.from) return;

    const fromCard = findCard(layout, req.from);
    const toCard   = findCard(layout, req.to);
    if (!fromCard || !toCard) return;

    const laneOffsets = {
      source: laneOffset(index, outgoingByFrom.get(req.from) ?? []),
      target: laneOffset(index, incomingByTo.get(req.to) ?? []),
    };

    const points = routeArrow(fromCard, toCard, req, layout, laneOffsets, segmentUsage);
    registerSegmentUsage(points, segmentUsage);
    arrows.push({
      requirementIndex: index,
      type: req.type,
      points,
      label: req.type === 'special' ? (req.description ?? 'RE') : undefined,
    });
  });

  return { arrows };
}

// ─── Roteamento ortogonal ────────────────────────────────────────────────────
//
// Estratégia:
//   1. Sair pela borda direita do cartão de origem.
//   2. Percorrer o canal horizontal entre as colunas envolvidas.
//   3. Ajustar verticalmente no canal entre os cartões, se necessário.
//   4. Entrar pela borda esquerda do cartão de destino.
//
// Para co-requisitos (mesmo nível), sair pela borda inferior da origem
// e entrar pela borda superior do destino, usando o canal vertical entre eles.

function routeArrow(
  from: CardRect,
  to: CardRect,
  req: RequirementInput,
  layout: LayoutData,
  laneOffsets: { source: number; target: number },
  segmentUsage: Map<string, number>
): Point[] {
  if (req.type === 'corequisite') {
    return routeCorequisite(from, to, laneOffsets);
  }
  return routeForwardArrow(from, to, layout, laneOffsets, segmentUsage);
}

function routeForwardArrow(
  from: CardRect,
  to: CardRect,
  layout: LayoutData,
  laneOffsets: { source: number; target: number },
  segmentUsage: Map<string, number>
): Point[] {
  const startX = from.x + from.width;
  const startY = clamp(
    from.y + from.height / 2 + laneOffsets.source,
    from.y + 8,
    from.y + from.height - 8
  );

  const endX = to.x;
  const endY = clamp(
    to.y + to.height / 2 + laneOffsets.target,
    to.y + 8,
    to.y + to.height - 8
  );

  const fromColIndex = findColumnIndexByX(layout, from.x);
  const toColIndex = findColumnIndexByX(layout, to.x);
  const isAdjacentForward =
    fromColIndex !== -1 &&
    toColIndex !== -1 &&
    toColIndex === fromColIndex + 1;

  const fromCenterY = from.y + from.height / 2;
  const toCenterY = to.y + to.height / 2;
  const isRowAligned = Math.abs(fromCenterY - toCenterY) <= 1;
  const overlapLow = Math.max(from.y + 8, to.y + 8);
  const overlapHigh = Math.min(from.y + from.height - 8, to.y + to.height - 8);

  if (isAdjacentForward && isRowAligned && overlapLow <= overlapHigh) {
    const sharedY = clamp((fromCenterY + toCenterY) / 2, overlapLow, overlapHigh);
    return [
      { x: startX, y: sharedY },
      { x: endX, y: sharedY },
    ];
  }

  if (to.x <= from.x + from.width) {
    return legacyForwardRoute(startX, startY, endX, endY, from, to, layout);
  }

  const laneInset = Math.max(10, COL_GAP * 0.35);
  const sourceLaneX = startX + laneInset;
  const targetLaneX = endX - laneInset;

  if (targetLaneX <= sourceLaneX) {
    return legacyForwardRoute(startX, startY, endX, endY, from, to, layout);
  }

  const laneXs = buildLaneXs(layout, from, to, sourceLaneX, targetLaneX);
  const corridorYs = buildHorizontalCorridors(layout);
  const graphPath = findBestCorridorPath({
    laneXs,
    corridorYs,
    sourceLaneX,
    targetLaneX,
    startY,
    endY,
    from,
    to,
    segmentUsage,
  });

  if (!graphPath || graphPath.length === 0) {
    return legacyForwardRoute(startX, startY, endX, endY, from, to, layout);
  }

  const basePath = simplifyOrthogonalPath([
    { x: startX, y: startY },
    { x: sourceLaneX, y: startY },
    ...graphPath,
    { x: targetLaneX, y: endY },
    { x: endX, y: endY },
  ]);

  return applySegmentLaneOffsets(basePath, segmentUsage);
}

function legacyForwardRoute(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  from: CardRect,
  to: CardRect,
  layout: LayoutData
): Point[] {

  // Canal horizontal: meio do espaço entre as duas colunas
  const midX = findMidChannel(from, to, layout);

  if (startY === endY) {
    // Mesma altura: linha reta
    return [
      { x: startX, y: startY },
      { x: endX,   y: endY   },
    ];
  }

  // Rota em formato Z: saída → canal vertical → canal horizontal → entrada
  return [
    { x: startX, y: startY },
    { x: midX,   y: startY },
    { x: midX,   y: endY   },
    { x: endX,   y: endY   },
  ];
}

function buildHorizontalCorridors(layout: LayoutData): number[] {
  const allCards = layout.columns.flatMap(col => col.cards);
  if (allCards.length === 0) return [];

  const firstY = Math.min(...allCards.map(card => card.y));
  const cardH = allCards[0].height;
  const maxRows = Math.max(...layout.columns.map(col => col.cards.length));

  const corridors: number[] = [];
  for (let row = 0; row <= maxRows; row++) {
    corridors.push(firstY - ROW_GAP / 2 + row * (cardH + ROW_GAP));
  }
  return corridors;
}

interface CorridorPathArgs {
  laneXs: number[];
  corridorYs: number[];
  sourceLaneX: number;
  targetLaneX: number;
  startY: number;
  endY: number;
  from: CardRect;
  to: CardRect;
  segmentUsage: Map<string, number>;
}

interface SearchState {
  xi: number;
  yi: number;
  dir: 'S' | 'H' | 'V';
}

const TURN_PENALTY = 14;
const CONGESTION_PENALTY = 18;

function buildLaneXs(
  layout: LayoutData,
  from: CardRect,
  to: CardRect,
  sourceLaneX: number,
  targetLaneX: number
): number[] {
  const fromColIndex = findColumnIndexByX(layout, from.x);
  const toColIndex = findColumnIndexByX(layout, to.x);
  if (fromColIndex === -1 || toColIndex === -1) {
    return [sourceLaneX, targetLaneX].sort((a, b) => a - b);
  }

  const laneXs = new Set<number>([sourceLaneX, targetLaneX]);
  const minCol = Math.min(fromColIndex, toColIndex);
  const maxCol = Math.max(fromColIndex, toColIndex);

  for (let leftCol = minCol + 1; leftCol <= maxCol - 2; leftCol++) {
    const leftX = layout.columns[leftCol].x;
    const cardW = layout.columns[leftCol].cards[0]?.width ?? from.width;
    laneXs.add(leftX + cardW + COL_GAP / 2);
  }

  return Array.from(laneXs).sort((a, b) => a - b);
}

function findColumnIndexByX(layout: LayoutData, x: number): number {
  let idx = -1;
  let bestDist = Number.POSITIVE_INFINITY;
  for (let i = 0; i < layout.columns.length; i++) {
    const dist = Math.abs(layout.columns[i].x - x);
    if (dist < bestDist) {
      bestDist = dist;
      idx = i;
    }
  }
  return idx;
}

function findBestCorridorPath(args: CorridorPathArgs): Point[] | null {
  const {
    laneXs,
    corridorYs,
    sourceLaneX,
    targetLaneX,
    startY,
    endY,
    from,
    to,
    segmentUsage,
  } = args;

  if (laneXs.length < 2 || corridorYs.length === 0) return null;

  const filteredYs = corridorYs.filter(y => !isInsideCardBand(y, from) && !isInsideCardBand(y, to));
  const ys = filteredYs.length > 0 ? filteredYs : corridorYs;
  const xs = laneXs;

  const sxi = xs.indexOf(sourceLaneX);
  const txi = xs.indexOf(targetLaneX);
  if (sxi === -1 || txi === -1) return null;

  const dist = new Map<string, number>();
  const prev = new Map<string, string>();
  const stateByKey = new Map<string, SearchState>();
  const visited = new Set<string>();

  function stateKey(state: SearchState): string {
    return `${state.xi}|${state.yi}|${state.dir}`;
  }

  function relax(next: SearchState, nextDist: number, prevKey: string): void {
    const key = stateKey(next);
    const curr = dist.get(key);
    if (curr === undefined || nextDist < curr) {
      dist.set(key, nextDist);
      prev.set(key, prevKey);
      stateByKey.set(key, next);
    }
  }

  for (let yi = 0; yi < ys.length; yi++) {
    const y = ys[yi];
    const state: SearchState = { xi: sxi, yi, dir: 'S' };
    const key = stateKey(state);
    const anchorA = { x: sourceLaneX, y: startY };
    const anchorB = { x: sourceLaneX, y };
    const initCost = Math.abs(startY - y) + segmentCongestionCost(anchorA, anchorB, segmentUsage);
    dist.set(key, initCost);
    prev.set(key, '__START__');
    stateByKey.set(key, state);
  }

  while (true) {
    let currentKey: string | null = null;
    let best = Number.POSITIVE_INFINITY;
    for (const [key, value] of dist.entries()) {
      if (visited.has(key)) continue;
      if (value < best) {
        best = value;
        currentKey = key;
      }
    }

    if (!currentKey) break;
    visited.add(currentKey);

    const current = stateByKey.get(currentKey)!;
    const currDist = dist.get(currentKey)!;

    const neighbors: Array<{ xi: number; yi: number; dir: 'H' | 'V' }> = [];
    if (current.xi > 0) neighbors.push({ xi: current.xi - 1, yi: current.yi, dir: 'H' });
    if (current.xi < xs.length - 1) neighbors.push({ xi: current.xi + 1, yi: current.yi, dir: 'H' });
    if (current.yi > 0) neighbors.push({ xi: current.xi, yi: current.yi - 1, dir: 'V' });
    if (current.yi < ys.length - 1) neighbors.push({ xi: current.xi, yi: current.yi + 1, dir: 'V' });

    for (const next of neighbors) {
      const a = { x: xs[current.xi], y: ys[current.yi] };
      const b = { x: xs[next.xi], y: ys[next.yi] };
      const base = Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
      const turn = current.dir !== 'S' && current.dir !== next.dir ? TURN_PENALTY : 0;
      const congestion = segmentCongestionCost(a, b, segmentUsage);
      const nextState: SearchState = { xi: next.xi, yi: next.yi, dir: next.dir };
      relax(nextState, currDist + base + turn + congestion, currentKey);
    }
  }

  let bestGoalKey: string | null = null;
  let bestGoalDist = Number.POSITIVE_INFINITY;

  for (const [key, value] of dist.entries()) {
    const state = stateByKey.get(key)!;
    if (state.xi !== txi) continue;

    const anchorA = { x: targetLaneX, y: ys[state.yi] };
    const anchorB = { x: targetLaneX, y: endY };
    const tail = Math.abs(ys[state.yi] - endY) + segmentCongestionCost(anchorA, anchorB, segmentUsage);
    const turn = state.dir === 'H' ? TURN_PENALTY : 0;
    const total = value + tail + turn;

    if (total < bestGoalDist) {
      bestGoalDist = total;
      bestGoalKey = key;
    }
  }

  if (!bestGoalKey) return null;

  const reversed: Point[] = [];
  let key: string | undefined = bestGoalKey;
  while (key && key !== '__START__') {
    const state = stateByKey.get(key);
    if (!state) break;
    reversed.push({ x: xs[state.xi], y: ys[state.yi] });
    key = prev.get(key);
  }

  return reversed.reverse();
}

function segmentCongestionCost(a: Point, b: Point, segmentUsage: Map<string, number>): number {
  if (a.x === b.x && a.y === b.y) return 0;
  const used = segmentUsage.get(segmentKey(a, b)) ?? 0;
  return used * CONGESTION_PENALTY;
}

function isInsideCardBand(y: number, card: CardRect): boolean {
  return y > card.y + 2 && y < card.y + card.height - 2;
}

function registerSegmentUsage(points: Point[], segmentUsage: Map<string, number>): void {
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (a.x === b.x && a.y === b.y) continue;
    const key = segmentKey(a, b);
    segmentUsage.set(key, (segmentUsage.get(key) ?? 0) + 1);
  }
}

function segmentKey(a: Point, b: Point): string {
  if (a.x === b.x) {
    const y1 = Math.min(a.y, b.y);
    const y2 = Math.max(a.y, b.y);
    return `V|${a.x}|${y1}|${y2}`;
  }
  if (a.y === b.y) {
    const x1 = Math.min(a.x, b.x);
    const x2 = Math.max(a.x, b.x);
    return `H|${a.y}|${x1}|${x2}`;
  }

  const left = a.x < b.x ? a : b;
  const right = a.x < b.x ? b : a;
  return `D|${left.x}|${left.y}|${right.x}|${right.y}`;
}

function simplifyOrthogonalPath(points: Point[]): Point[] {
  if (points.length <= 2) return points;

  const deduped: Point[] = [];
  for (const p of points) {
    const prev = deduped[deduped.length - 1];
    if (!prev || prev.x !== p.x || prev.y !== p.y) deduped.push(p);
  }

  if (deduped.length <= 2) return deduped;

  const simplified: Point[] = [deduped[0]];
  for (let i = 1; i < deduped.length - 1; i++) {
    const a = simplified[simplified.length - 1];
    const b = deduped[i];
    const c = deduped[i + 1];
    const collinear = (a.x === b.x && b.x === c.x) || (a.y === b.y && b.y === c.y);
    if (!collinear) simplified.push(b);
  }
  simplified.push(deduped[deduped.length - 1]);

  return simplified;
}

function applySegmentLaneOffsets(points: Point[], segmentUsage: Map<string, number>): Point[] {
  if (points.length < 5) return points;

  const firstCorridorSeg = 1;
  const lastCorridorSeg = points.length - 3;
  if (lastCorridorSeg < firstCorridorSeg) return points;

  const segOffset = new Map<number, number>();

  for (let i = firstCorridorSeg; i <= lastCorridorSeg; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (!isOrthogonalSegment(a, b)) continue;

    const usage = segmentUsage.get(segmentKey(a, b)) ?? 0;
    segOffset.set(i, alternatingLaneOffset(usage, 3.5));
  }

  const shifted = points.map(p => ({ ...p }));

  // Não desloca conectores imediatamente junto aos cartões (índices 0,1,n-2,n-1).
  for (let i = 2; i <= shifted.length - 3; i++) {
    const leftIdx = i - 1;
    const rightIdx = i;

    const leftOff = segOffset.get(leftIdx) ?? 0;
    const rightOff = segOffset.get(rightIdx) ?? 0;

    const leftSegA = points[leftIdx];
    const leftSegB = points[leftIdx + 1];
    const rightSegA = points[rightIdx];
    const rightSegB = points[rightIdx + 1];

    const leftVertical = isVerticalSegment(leftSegA, leftSegB);
    const rightVertical = isVerticalSegment(rightSegA, rightSegB);
    const leftHorizontal = isHorizontalSegment(leftSegA, leftSegB);
    const rightHorizontal = isHorizontalSegment(rightSegA, rightSegB);

    const xShift = rightVertical ? rightOff : (leftVertical ? leftOff : 0);
    const yShift = rightHorizontal ? rightOff : (leftHorizontal ? leftOff : 0);

    shifted[i].x += xShift;
    shifted[i].y += yShift;
  }

  return ensureOrthogonal(shifted);
}

function alternatingLaneOffset(usage: number, spacing: number): number {
  if (usage <= 0) return 0;
  const step = Math.ceil(usage / 2);
  return (usage % 2 === 1 ? 1 : -1) * step * spacing;
}

function ensureOrthogonal(points: Point[]): Point[] {
  if (points.length <= 2) return points;

  const out: Point[] = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const prev = out[out.length - 1];
    const curr = points[i];
    if (prev.x !== curr.x && prev.y !== curr.y) {
      out.push({ x: curr.x, y: prev.y });
    }
    out.push(curr);
  }

  return simplifyOrthogonalPath(out);
}

function isOrthogonalSegment(a: Point, b: Point): boolean {
  return isVerticalSegment(a, b) || isHorizontalSegment(a, b);
}

function isVerticalSegment(a: Point, b: Point): boolean {
  return a.x === b.x && a.y !== b.y;
}

function isHorizontalSegment(a: Point, b: Point): boolean {
  return a.y === b.y && a.x !== b.x;
}

function routeCorequisite(
  from: CardRect,
  to: CardRect,
  laneOffsets: { source: number; target: number }
): Point[] {
  const fromCenterX = from.x + from.width / 2;
  const toCenterX = to.x + to.width / 2;
  const isColumnAligned = Math.abs(fromCenterX - toCenterX) <= 1;

  const gapDown = Math.abs(to.y - (from.y + from.height));
  const gapUp = Math.abs(from.y - (to.y + to.height));
  const isAdjacentVertical =
    Math.abs(gapDown - ROW_GAP) <= 1 || Math.abs(gapUp - ROW_GAP) <= 1;

  const overlapLeft = Math.max(from.x + 8, to.x + 8);
  const overlapRight = Math.min(from.x + from.width - 8, to.x + to.width - 8);

  if (isColumnAligned && isAdjacentVertical && overlapLeft <= overlapRight) {
    const sharedX = clamp((fromCenterX + toCenterX) / 2, overlapLeft, overlapRight);
    const downward = to.y >= from.y;
    const startY = downward ? from.y + from.height : from.y;
    const endY = downward ? to.y : to.y + to.height;
    return [
      { x: sharedX, y: startY },
      { x: sharedX, y: endY },
    ];
  }

  // Seta vertical: da borda inferior da origem até a borda superior do destino
  const startX = clamp(
    from.x + from.width / 2 + laneOffsets.source,
    from.x + 8,
    from.x + from.width - 8
  );
  const startY = from.y + from.height;

  const endX = clamp(
    to.x + to.width / 2 + laneOffsets.target,
    to.x + 8,
    to.x + to.width - 8
  );
  const endY = to.y;

  const midY = startY + ROW_GAP / 2 + (laneOffsets.source - laneOffsets.target) * 0.35;

  return [
    { x: startX, y: startY },
    { x: startX, y: midY   },
    { x: endX,   y: midY   },
    { x: endX,   y: endY   },
  ];
}

function laneOffset(index: number, siblings: number[]): number {
  if (siblings.length <= 1) return 0;

  const pos = siblings.indexOf(index);
  if (pos === -1) return 0;

  const spacing = 8;
  const center = (siblings.length - 1) / 2;
  return (pos - center) * spacing;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function courseCenterY(layout: LayoutData, courseCode: string): number {
  const card = findCard(layout, courseCode);
  if (!card) return Number.POSITIVE_INFINITY;
  return card.y + card.height / 2;
}

// Encontra o centro do canal horizontal entre a coluna de 'from' e a de 'to'.
function findMidChannel(from: CardRect, to: CardRect, layout: LayoutData): number {
  // Borda direita da coluna de origem
  const fromRight = from.x + from.width;
  // Borda esquerda da coluna de destino
  const toLeft = to.x;

  // O canal fica entre as duas borders; usamos o ponto médio.
  // Se houver colunas intermediárias, o ponto médio ainda é válido para uma
  // rota simples; roteamento mais sofisticado pode ser implementado aqui.
  const _ = layout; // referência mantida para uso futuro
  return fromRight + (toLeft - fromRight) / 2;
}
