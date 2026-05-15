#!/usr/bin/env python3
"""Replace English template answer labels/descriptions on primary (CS) rows with Czech text."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.checklist import ChecklistQuestionAnswerOption

EN_DESCRIPTION_TO_CS = {
    "Control is fully implemented.": "Kontrola je plně implementována.",
    "Control is partially implemented or uncertain.": "Kontrola je částečně implementována nebo je nejistá.",
    "Control is confidently implemented.": "Kontrola je spolehlivě implementována.",
    "Control is not implemented.": "Kontrola není implementována.",
}

EN_LABEL_TO_CS = {
    "Yes": "Ano",
    "Maybe": "Možná",
    "Sure": "Jistě",
    "No": "Ne",
}

# choice_code -> Czech label when label still matches English template
CHOICE_CODE_TO_CS_LABEL = {
    "YES": "Ano",
    "MAYBE": "Možná",
    "SURE": "Jistě",
    "NO": "Ne",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply updates (default is dry-run)")
    parser.add_argument("--labels-only", action="store_true", help="Only update labels")
    parser.add_argument("--descriptions-only", action="store_true", help="Only update descriptions")
    args = parser.parse_args()

    update_labels = not args.descriptions_only
    update_descriptions = not args.labels_only

    with SessionLocal() as session:
        options = session.scalars(select(ChecklistQuestionAnswerOption)).all()
        label_updates: list[tuple[ChecklistQuestionAnswerOption, str, str]] = []
        description_updates: list[tuple[ChecklistQuestionAnswerOption, str, str]] = []

        for option in options:
            if update_labels and option.label is not None:
                normalized_label = option.label.strip()
                czech_label = EN_LABEL_TO_CS.get(normalized_label)
                if not czech_label and option.choice_code:
                    code = option.choice_code.strip().upper()
                    if normalized_label in EN_LABEL_TO_CS or normalized_label == "":
                        czech_label = CHOICE_CODE_TO_CS_LABEL.get(code)
                if czech_label and czech_label != normalized_label:
                    label_updates.append((option, normalized_label, czech_label))

            if update_descriptions and option.description is not None:
                normalized_description = option.description.strip()
                czech_description = EN_DESCRIPTION_TO_CS.get(normalized_description)
                if czech_description and czech_description != normalized_description:
                    description_updates.append((option, normalized_description, czech_description))

        print(f"Found {len(label_updates)} answer option(s) with English template labels.")
        for option, before, after in label_updates[:10]:
            print(f"  - {option.id}: label {before!r} -> {after!r}")
        if len(label_updates) > 10:
            print(f"  ... and {len(label_updates) - 10} more")

        print(f"Found {len(description_updates)} answer option(s) with English template descriptions.")
        for option, before, after in description_updates[:10]:
            print(f"  - {option.id}: description {before!r} -> {after!r}")
        if len(description_updates) > 10:
            print(f"  ... and {len(description_updates) - 10} more")

        if not args.execute:
            print("\nDry run only. Re-run with --execute to apply.")
            return 0

        for option, _, czech_label in label_updates:
            option.label = czech_label
        for option, _, czech_description in description_updates:
            option.description = czech_description

        session.commit()
        print(f"\nUpdated {len(label_updates)} label(s) and {len(description_updates)} description(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
