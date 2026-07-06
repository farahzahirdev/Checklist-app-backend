#!/usr/bin/env python3
"""Backfill missing Czech (cs) checklist translations from English rows.

Use on production when published checklists only have EN translations and Czech
users cannot see purchased audits.

Default is dry-run. Re-run with --execute to apply changes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.checklist import (
    ChecklistQuestionTranslation,
    ChecklistSectionTranslation,
    ChecklistTranslation,
)
from app.models.reference import Language


def _language_ids(session) -> tuple[Language, Language]:
    english = session.scalar(select(Language).where(Language.code == "en"))
    czech = session.scalar(select(Language).where(Language.code == "cs"))
    if english is None or czech is None:
        raise RuntimeError("Both English (en) and Czech (cs) languages must exist in the database.")
    return english, czech


def _backfill_checklist_translations(session, *, english: Language, czech: Language, execute: bool) -> int:
    english_rows = session.scalars(
        select(ChecklistTranslation).where(ChecklistTranslation.language_id == english.id)
    ).all()
    created = 0

    for english_row in english_rows:
        existing_cs = session.scalar(
            select(ChecklistTranslation).where(
                ChecklistTranslation.checklist_id == english_row.checklist_id,
                ChecklistTranslation.language_id == czech.id,
            )
        )
        if existing_cs is not None:
            continue

        created += 1
        print(
            f"  checklist {english_row.checklist_id}: "
            f"title={english_row.title!r} -> cs"
        )
        if execute:
            session.add(
                ChecklistTranslation(
                    checklist_id=english_row.checklist_id,
                    language_id=czech.id,
                    title=english_row.title,
                    description=english_row.description,
                )
            )

    return created


def _backfill_section_translations(session, *, english: Language, czech: Language, execute: bool) -> int:
    english_rows = session.scalars(
        select(ChecklistSectionTranslation).where(ChecklistSectionTranslation.language_id == english.id)
    ).all()
    created = 0

    for english_row in english_rows:
        existing_cs = session.scalar(
            select(ChecklistSectionTranslation).where(
                ChecklistSectionTranslation.section_id == english_row.section_id,
                ChecklistSectionTranslation.language_id == czech.id,
            )
        )
        if existing_cs is not None:
            continue

        created += 1
        if execute:
            session.add(
                ChecklistSectionTranslation(
                    section_id=english_row.section_id,
                    language_id=czech.id,
                    title=english_row.title,
                )
            )

    return created


def _backfill_question_translations(session, *, english: Language, czech: Language, execute: bool) -> int:
    english_rows = session.scalars(
        select(ChecklistQuestionTranslation).where(ChecklistQuestionTranslation.language_id == english.id)
    ).all()
    created = 0

    for english_row in english_rows:
        existing_cs = session.scalar(
            select(ChecklistQuestionTranslation).where(
                ChecklistQuestionTranslation.question_id == english_row.question_id,
                ChecklistQuestionTranslation.language_id == czech.id,
            )
        )
        if existing_cs is not None:
            continue

        created += 1
        if execute:
            session.add(
                ChecklistQuestionTranslation(
                    question_id=english_row.question_id,
                    language_id=czech.id,
                    question_text=english_row.question_text,
                    legal_requirement_title=english_row.legal_requirement_title,
                    legal_requirement_description=english_row.legal_requirement_description,
                )
            )

    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply updates (default is dry-run)")
    args = parser.parse_args()

    with SessionLocal() as session:
        english, czech = _language_ids(session)
        print(f"Languages: en={english.id}, cs={czech.id}")

        checklist_created = _backfill_checklist_translations(
            session, english=english, czech=czech, execute=args.execute
        )
        section_created = _backfill_section_translations(
            session, english=english, czech=czech, execute=args.execute
        )
        question_created = _backfill_question_translations(
            session, english=english, czech=czech, execute=args.execute
        )

        print(
            f"\nMissing Czech translations to create: "
            f"checklists={checklist_created}, sections={section_created}, questions={question_created}"
        )

        if not args.execute:
            print("\nDry run only. Re-run with --execute to apply.")
            return 0

        session.commit()
        print("\nBackfill complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
