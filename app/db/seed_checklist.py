"""
Seed script for checklist, sections, translations, and questions.
Run with: `python -m app.db.seed_checklist`
"""
import uuid
from datetime import datetime, date

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.reference import Language, ChecklistStatusCode, SeverityCode
from app.models.checklist import (
    ChecklistType, Checklist, ChecklistSection, ChecklistQuestion,
    ChecklistTranslation, ChecklistSectionTranslation, ChecklistQuestionTranslation,
    ChecklistStatus, SeverityLevel
)

def seed_checklist():
    db: Session = SessionLocal()
    try:
        # 1. Ensure at least one language exists
        language = db.query(Language).filter_by(code="en").first()
        if not language:
            language = Language(code="en", name="English", is_default=True, is_active=True)
            db.add(language)
            db.commit()
            db.refresh(language)

        # 2. Ensure at least one user exists
        user = db.query(User).first()
        if not user:
            user = User(email="seed@example.com", password_hash="notahash", role="admin", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)

        # 3. ChecklistType
        checklist_type = ChecklistType(code="demo", name="Demo Checklist Type", description="Demo type", is_active=True)
        db.add(checklist_type)
        db.commit()
        db.refresh(checklist_type)

        # 4. Checklist
        checklist = Checklist(
            checklist_type_id=checklist_type.id,
            version=1,
            status_code_id=ChecklistStatus.to_id(ChecklistStatus.published),
            effective_from=date.today(),
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(checklist)
        db.commit()
        db.refresh(checklist)

        # 5. ChecklistTranslation
        checklist_translation = ChecklistTranslation(
            checklist_id=checklist.id,
            language_id=language.id,
            title="Demo Checklist",
            description="A demo checklist for seeding."
        )
        db.add(checklist_translation)
        db.commit()

        # 6. ChecklistSections (2-3)
        sections = []
        for i, section_name in enumerate(["General", "Security", "Compliance"]):
            section = ChecklistSection(
                checklist_id=checklist.id,
                section_code=f"section_{i+1}",
                source_ref=None,
                display_order=i+1
            )
            db.add(section)
            db.commit()
            db.refresh(section)
            # Section translation
            section_translation = ChecklistSectionTranslation(
                section_id=section.id,
                language_id=language.id,
                title=f"{section_name} Section"
            )
            db.add(section_translation)
            db.commit()
            sections.append(section)

        # 7. ChecklistQuestions (3-4 for first section)
        questions = [
            ("Is the system up to date?", "general_1"),
            ("Are backups configured?", "general_2"),
            ("Is access control enforced?", "general_3"),
            ("Is there a disaster recovery plan?", "general_4"),
        ]
        for idx, (text, code) in enumerate(questions):
            question = ChecklistQuestion(
                checklist_id=checklist.id,
                section_id=sections[0].id,
                question_code=code,
                display_order=idx+1,
                note_enabled=True,
                evidence_enabled=True,
                is_active=True
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            # Question translation
            question_translation = ChecklistQuestionTranslation(
                question_id=question.id,
                language_id=language.id,
                title=text
            )
            db.add(question_translation)
            db.commit()

        print("Seeded checklist, sections, translations, and questions.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_checklist()
