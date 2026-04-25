import { CurriculumFile, CourseInput, RequirementInput } from './types';

// ─── Erros de validação ───────────────────────────────────────────────────────

export class ParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ParseError';
  }
}

// ─── Ponto de entrada ─────────────────────────────────────────────────────────

export function parse(rawJson: string): CurriculumFile {
  let data: unknown;
  try {
    data = JSON.parse(rawJson);
  } catch {
    throw new ParseError('O arquivo não contém um JSON válido.');
  }

  assertCurriculumFile(data);
  validate(data);
  return data;
}

// ─── Asserções de estrutura ──────────────────────────────────────────────────

function assertCurriculumFile(data: unknown): asserts data is CurriculumFile {
  if (typeof data !== 'object' || data === null) {
    throw new ParseError('O JSON de entrada deve ser um objeto.');
  }

  const d = data as Record<string, unknown>;

  assertCurriculum(d['curriculum']);
  assertCourses(d['courses']);
  assertRequirements(d['requirements']);
  assertCategories(d['categories']);
  assertDisplay(d['display']);
}

function assertCurriculum(value: unknown): void {
  if (typeof value !== 'object' || value === null) {
    throw new ParseError('Campo "curriculum" ausente ou inválido.');
  }
  const c = value as Record<string, unknown>;
  for (const field of ['code', 'name', 'availableSince', 'description']) {
    if (typeof c[field] !== 'string' || (c[field] as string).trim() === '') {
      throw new ParseError(`Campo "curriculum.${field}" ausente ou vazio.`);
    }
  }
  if (typeof c['levels'] !== 'number' || c['levels'] < 1) {
    throw new ParseError('Campo "curriculum.levels" deve ser um número positivo.');
  }
}

function assertCourses(value: unknown): void {
  if (!Array.isArray(value)) {
    throw new ParseError('Campo "courses" deve ser um array.');
  }
  value.forEach((item, i) => {
    const c = item as Record<string, unknown>;
    for (const field of ['code', 'name', 'syllabus']) {
      if (typeof c[field] !== 'string' || (c[field] as string).trim() === '') {
        throw new ParseError(`courses[${i}].${field}: ausente ou vazio.`);
      }
    }
    for (const field of ['hours', 'credits', 'level']) {
      if (typeof c[field] !== 'number' || (c[field] as number) < 1) {
        throw new ParseError(`courses[${i}].${field}: deve ser um número positivo.`);
      }
    }
    if (!Array.isArray(c['tags'])) {
      throw new ParseError(`courses[${i}].tags: deve ser um array.`);
    }
    (c['tags'] as unknown[]).forEach((tag, j) => {
      if (typeof tag !== 'string' || tag.trim() === '') {
        throw new ParseError(`courses[${i}].tags[${j}]: deve ser string não vazia.`);
      }
    });

    if (c['category'] !== undefined) {
      if (typeof c['category'] !== 'string' || (c['category'] as string).trim() === '') {
        throw new ParseError(`courses[${i}].category: deve ser string não vazia, quando informado.`);
      }
    }
  });
}

function assertCategories(value: unknown): void {
  if (value === undefined) return;
  if (!Array.isArray(value)) {
    throw new ParseError('Campo "categories" deve ser um array, quando informado.');
  }

  value.forEach((item, i) => {
    if (typeof item !== 'object' || item === null) {
      throw new ParseError(`categories[${i}]: item inválido.`);
    }
    const c = item as Record<string, unknown>;
    if (typeof c['id'] !== 'string' || (c['id'] as string).trim() === '') {
      throw new ParseError(`categories[${i}].id: ausente ou vazio.`);
    }
    if (typeof c['name'] !== 'string' || (c['name'] as string).trim() === '') {
      throw new ParseError(`categories[${i}].name: ausente ou vazio.`);
    }
    if (c['color'] !== undefined && (typeof c['color'] !== 'string' || (c['color'] as string).trim() === '')) {
      throw new ParseError(`categories[${i}].color: deve ser string não vazia, quando informado.`);
    }
  });
}

function assertDisplay(value: unknown): void {
  if (value === undefined) return;
  if (typeof value !== 'object' || value === null) {
    throw new ParseError('Campo "display" deve ser um objeto, quando informado.');
  }

  const d = value as Record<string, unknown>;
  const fillStyle = d['card_fill_style'];
  if (fillStyle !== undefined && fillStyle !== 'category') {
    throw new ParseError('Campo "display.card_fill_style" deve ser "category" quando informado.');
  }
}

function assertRequirements(value: unknown): void {
  if (!Array.isArray(value)) {
    throw new ParseError('Campo "requirements" deve ser um array.');
  }
  const validTypes = ['prerequisite', 'special', 'corequisite', 'credit_requirement'];
  value.forEach((item, i) => {
    const r = item as Record<string, unknown>;
    if (!validTypes.includes(r['type'] as string)) {
      throw new ParseError(`requirements[${i}].type: valor inválido "${r['type']}".`);
    }
    if (typeof r['to'] !== 'string' || (r['to'] as string).trim() === '') {
      throw new ParseError(`requirements[${i}].to: ausente ou vazio.`);
    }
    if (r['type'] !== 'credit_requirement') {
      if (typeof r['from'] !== 'string' || (r['from'] as string).trim() === '') {
        throw new ParseError(`requirements[${i}].from: ausente ou vazio.`);
      }
    }
    if (r['type'] === 'credit_requirement') {
      if (typeof r['min_credits'] !== 'number' || (r['min_credits'] as number) < 1) {
        throw new ParseError(`requirements[${i}].min_credits: deve ser um número positivo.`);
      }
    }
  });
}

// ─── Regras de negócio ────────────────────────────────────────────────────────

function validate(data: CurriculumFile): void {
  const courseMap = buildCourseMap(data.courses);
  const categoryIdSet = new Set((data.categories ?? []).map(c => c.id));

  checkDuplicateCodes(data.courses);
  checkDuplicateCategoryIds(data.categories ?? []);
  checkCourseCategoryReferences(data.courses, categoryIdSet);
  checkRequirementReferences(data.requirements, courseMap);
  checkPrerequisiteLevels(data.requirements, courseMap);
}

function buildCourseMap(courses: CourseInput[]): Map<string, CourseInput> {
  const map = new Map<string, CourseInput>();
  for (const course of courses) {
    map.set(course.code, course);
  }
  return map;
}

function checkDuplicateCodes(courses: CourseInput[]): void {
  const seen = new Set<string>();
  for (const course of courses) {
    if (seen.has(course.code)) {
      throw new ParseError(`Código de disciplina duplicado: "${course.code}".`);
    }
    seen.add(course.code);
  }
}

function checkDuplicateCategoryIds(categories: Array<{ id: string }>): void {
  const seen = new Set<string>();
  for (const category of categories) {
    if (seen.has(category.id)) {
      throw new ParseError(`Categoria duplicada em "categories": "${category.id}".`);
    }
    seen.add(category.id);
  }
}

function checkCourseCategoryReferences(courses: CourseInput[], categoryIds: Set<string>): void {
  for (const course of courses) {
    if (!course.category) continue;
    if (!categoryIds.has(course.category)) {
      throw new ParseError(
        `Disciplina "${course.code}": category "${course.category}" não existe em "categories".`
      );
    }
  }
}

function checkRequirementReferences(
  requirements: RequirementInput[],
  courseMap: Map<string, CourseInput>
): void {
  for (const req of requirements) {
    if (!courseMap.has(req.to)) {
      throw new ParseError(`Requisito: código de disciplina desconhecido em "to": "${req.to}".`);
    }
    if (req.from !== undefined && !courseMap.has(req.from)) {
      throw new ParseError(`Requisito: código de disciplina desconhecido em "from": "${req.from}".`);
    }
  }
}

function checkPrerequisiteLevels(
  requirements: RequirementInput[],
  courseMap: Map<string, CourseInput>
): void {
  for (const req of requirements) {
    if (req.from === undefined) continue;

    const from = courseMap.get(req.from)!;
    const to = courseMap.get(req.to)!;

    if (req.type === 'corequisite') {
      if (from.level !== to.level) {
        throw new ParseError(
          `Co-requisito inválido: "${req.from}" (nível ${from.level}) e "${req.to}" (nível ${to.level}) devem estar no mesmo nível.`
        );
      }
    }

    if (req.type === 'prerequisite' || req.type === 'special') {
      if (from.level >= to.level) {
        throw new ParseError(
          `Pré-requisito inválido: "${req.from}" (nível ${from.level}) deve ser de nível anterior a "${req.to}" (nível ${to.level}).`
        );
      }
    }
  }
}
