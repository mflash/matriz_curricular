from __future__ import annotations

import json
from typing import Dict, List, Optional

from .types import (
    CategoryInput,
    CourseInput,
    CurriculumFile,
    CurriculumInput,
    RequirementInput,
)

# ─────────────────────────────────────────────────────────────────────────────
# Parser / validação
# ─────────────────────────────────────────────────────────────────────────────


class ParseError(Exception):
    pass


def parse(raw_json: str) -> CurriculumFile:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ParseError(f"O arquivo não contém um JSON válido: {e}")

    if not isinstance(data, dict):
        raise ParseError("O JSON de entrada deve ser um objeto.")

    curriculum = _parse_curriculum(data.get("curriculum"))
    courses = _parse_courses(data.get("courses"))
    requirements = _parse_requirements(data.get("requirements"))
    categories = _parse_categories(data.get("categories"))
    card_fill_style = _parse_display(data.get("display"))

    _check_course_category_references(courses, categories)

    return CurriculumFile(
        curriculum=curriculum,
        courses=courses,
        requirements=requirements,
        categories=categories,
        card_fill_style=card_fill_style,
    )


def _parse_curriculum(value) -> CurriculumInput:
    if not isinstance(value, dict):
        raise ParseError('Campo "curriculum" ausente ou inválido.')
    for f in ("code", "name", "availableSince", "description"):
        if not isinstance(value.get(f), str) or not value[f].strip():
            raise ParseError(f'Campo "curriculum.{f}" ausente ou vazio.')
    if not isinstance(value.get("levels"), (int, float)) or value["levels"] < 1:
        raise ParseError('Campo "curriculum.levels" deve ser um número positivo.')
    return CurriculumInput(
        code=value["code"],
        name=value["name"],
        available_since=value["availableSince"],
        description=value["description"],
        levels=int(value["levels"]),
    )


def _parse_courses(value) -> List[CourseInput]:
    if not isinstance(value, list):
        raise ParseError('Campo "courses" deve ser um array.')
    courses = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ParseError(f"courses[{i}]: item inválido.")
        for f in ("code", "name", "syllabus"):
            if not isinstance(item.get(f), str) or not item[f].strip():
                raise ParseError(f"courses[{i}].{f}: ausente ou vazio.")
        for f in ("hours", "credits", "level"):
            if not isinstance(item.get(f), (int, float)) or item[f] < 1:
                raise ParseError(f"courses[{i}].{f}: deve ser um número positivo.")
        if not isinstance(item.get("tags"), list):
            raise ParseError(f"courses[{i}].tags: deve ser um array.")
        for j, tag in enumerate(item["tags"]):
            if not isinstance(tag, str) or not tag.strip():
                raise ParseError(f"courses[{i}].tags[{j}]: deve ser string não vazia.")
        cat = item.get("category")
        if cat is not None and (not isinstance(cat, str) or not cat.strip()):
            raise ParseError(
                f"courses[{i}].category: deve ser string não vazia, quando informado."
            )
        courses.append(
            CourseInput(
                code=item["code"],
                name=item["name"],
                hours=int(item["hours"]),
                credits=int(item["credits"]),
                level=int(item["level"]),
                syllabus=item["syllabus"],
                tags=list(item["tags"]),
                category=cat,
            )
        )
    return courses


def _parse_categories(value) -> List[CategoryInput]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ParseError('Campo "categories" deve ser um array, quando informado.')
    categories = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ParseError(f"categories[{i}]: item inválido.")
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ParseError(f"categories[{i}].id: ausente ou vazio.")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ParseError(f"categories[{i}].name: ausente ou vazio.")
        color = item.get("color")
        if color is not None and (not isinstance(color, str) or not color.strip()):
            raise ParseError(
                f"categories[{i}].color: deve ser string não vazia, quando informado."
            )
        categories.append(CategoryInput(id=item["id"], name=item["name"], color=color))
    return categories


def _parse_display(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ParseError('Campo "display" deve ser um objeto, quando informado.')
    fill_style = value.get("card_fill_style")
    if fill_style is not None and fill_style != "category":
        raise ParseError(
            'Campo "display.card_fill_style" deve ser "category" quando informado.'
        )
    return fill_style


def _parse_requirements(value) -> List[RequirementInput]:
    if not isinstance(value, list):
        raise ParseError('Campo "requirements" deve ser um array.')
    valid_types = {"prerequisite", "special", "corequisite", "credit_requirement"}
    reqs = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ParseError(f"requirements[{i}]: item inválido.")
        rtype = item.get("type")
        if rtype not in valid_types:
            raise ParseError(f'requirements[{i}].type: valor inválido "{rtype}".')
        to = item.get("to")
        if not isinstance(to, str) or not to.strip():
            raise ParseError(f"requirements[{i}].to: ausente ou vazio.")
        from_code = item.get("from")
        if rtype != "credit_requirement":
            if not isinstance(from_code, str) or not from_code.strip():
                raise ParseError(f"requirements[{i}].from: ausente ou vazio.")
        if rtype == "credit_requirement":
            mc = item.get("min_credits")
            if not isinstance(mc, (int, float)) or mc < 1:
                raise ParseError(
                    f"requirements[{i}].min_credits: deve ser um número positivo."
                )
        reqs.append(
            RequirementInput(
                type=rtype,
                to=to,
                from_code=from_code if isinstance(from_code, str) else None,
                description=item.get("description"),
                min_credits=(
                    int(item["min_credits"])
                    if item.get("min_credits") is not None
                    else None
                ),
            )
        )
    return reqs


def _check_course_category_references(
    courses: List[CourseInput], categories: List[CategoryInput]
) -> None:
    cat_ids = {c.id for c in categories}
    for course in courses:
        if course.category and course.category not in cat_ids:
            raise ParseError(
                f'courses[{course.code}].category refere-se a categoria inexistente: "{course.category}".'
            )
