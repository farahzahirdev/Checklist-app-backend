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
        language = db.query(Language).filter_by(code="cs").first()
        if not language:
            language = Language(code="cs", name="Czech", is_default=True, is_active=True)
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


        # 3. Ensure at least one severity code exists (required for ChecklistQuestion)
        severity = db.query(SeverityCode).filter_by(code="low").first()
        if not severity:
            severity = SeverityCode(id=1, code="low", name="Low", is_active=True)
            db.add(severity)
            db.commit()
            db.refresh(severity)

        # 4. ChecklistType (get or create)
        checklist_type = db.query(ChecklistType).filter_by(code="demo").first()
        if not checklist_type:
            checklist_type = ChecklistType(code="demo", name="Demo Checklist Type", description="Demo type", is_active=True)
            db.add(checklist_type)
            db.commit()
            db.refresh(checklist_type)

        # 5. Checklist (get or create)
        checklist = db.query(Checklist).filter_by(checklist_type_id=checklist_type.id, version=1).first()
        if not checklist:
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

        # 6. ChecklistTranslation (get or create)
        checklist_translation = db.query(ChecklistTranslation).filter_by(checklist_id=checklist.id, language_id=language.id).first()
        if not checklist_translation:
            checklist_translation = ChecklistTranslation(
                checklist_id=checklist.id,
                language_id=language.id,
                title="Demo Checklist",
                description="A demo checklist for seeding."
            )
            db.add(checklist_translation)
            db.commit()

        # 7. ChecklistSections (2-3, get or create)
        sections = []
        for i, section_name in enumerate(["General", "Security", "Compliance"]):
            section = db.query(ChecklistSection).filter_by(checklist_id=checklist.id, display_order=i+1).first()
            if not section:
                section = ChecklistSection(
                    checklist_id=checklist.id,
                    section_code=f"section_{i+1}",
                    source_ref=None,
                    display_order=i+1
                )
                db.add(section)
                db.commit()
                db.refresh(section)
            # Section translation (get or create)
            section_translation = db.query(ChecklistSectionTranslation).filter_by(section_id=section.id, language_id=language.id).first()
            if not section_translation:
                section_translation = ChecklistSectionTranslation(
                    section_id=section.id,
                    language_id=language.id,
                    title=f"{section_name} Section"
                )
                db.add(section_translation)
                db.commit()
            sections.append(section)

        # 8. ChecklistQuestions (3-4 for first section)
        questions = [
            ("Is the system up to date?", "general_1"),
            ("Are backups configured?", "general_2"),
            ("Is access control enforced?", "general_3"),
            ("Is there a disaster recovery plan?", "general_4"),
        ]
        for idx, (text, code) in enumerate(questions):
            question = db.query(ChecklistQuestion).filter_by(checklist_id=checklist.id, question_code=code).first()
            if not question:
                question = ChecklistQuestion(
                    checklist_id=checklist.id,
                    section_id=sections[0].id,
                    question_code=code,
                    severity_code_id=severity.id,
                    display_order=idx+1,
                    note_enabled=True,
                    evidence_enabled=True,
                    is_active=True
                )
                db.add(question)
                db.commit()
                db.refresh(question)
            # Question translation (get or create)
            question_translation = db.query(ChecklistQuestionTranslation).filter_by(question_id=question.id, language_id=language.id).first()
            if not question_translation:
                question_translation = ChecklistQuestionTranslation(
                    question_id=question.id,
                    language_id=language.id,
                    question_text=text
                )
                db.add(question_translation)
                db.commit()

        print("Seeded checklist, sections, translations, and questions.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_checklist()
