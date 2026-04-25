from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Tipos de dados — espelham a estrutura do JSON de entrada e as estruturas
# internas de layout, roteamento e renderização.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CurriculumInput:
    code: str
    name: str
    available_since: str
    description: str
    levels: int


@dataclass
class CourseInput:
    code: str
    name: str
    hours: int
    credits: int
    level: int
    syllabus: str
    tags: List[str]
    category: Optional[str] = None


@dataclass
class CategoryInput:
    id: str
    name: str
    color: Optional[str] = None


@dataclass
class RequirementInput:
    type: str  # 'prerequisite' | 'special' | 'corequisite' | 'credit_requirement'
    to: str
    from_code: Optional[str] = None
    description: Optional[str] = None
    min_credits: Optional[int] = None


@dataclass
class CurriculumFile:
    curriculum: CurriculumInput
    courses: List[CourseInput]
    requirements: List[RequirementInput]
    categories: List[CategoryInput] = field(default_factory=list)
    card_fill_style: Optional[str] = None  # 'category' or None


@dataclass
class Point:
    x: float
    y: float


@dataclass
class CardRect:
    course_code: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class ColumnLayout:
    level: int
    x: float
    total_credits: int
    cards: List[CardRect]


@dataclass
class LayoutData:
    canvas_width: float
    canvas_height: float
    columns: List[ColumnLayout]


@dataclass
class ArrowRoute:
    requirement_index: int
    type: str
    points: List[Point]
    label: Optional[str] = None


@dataclass
class RouteData:
    arrows: List[ArrowRoute]
