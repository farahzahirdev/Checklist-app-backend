from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.models.assessment import Assessment, AssessmentAnswer, AssessmentStatus
from app.models.checklist import ChecklistQuestion


def test_report_endpoints_include_section_overviews(db, client, admin_token, admin_user, customer_user, sample_checklist):
    assessment = Assessment(
        user_id=customer_user.id,
        checklist_id=sample_checklist.id,
        access_window_id=uuid4(),
        status=AssessmentStatus.submitted,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(assessment)
    db.flush()

    question = db.query(ChecklistQuestion).filter(ChecklistQuestion.section_id.isnot(None)).first()
    assert question is not None

    answer = AssessmentAnswer(
        assessment_id=assessment.id,
        question_id=question.id,
        answer_score=3,
    )
    db.add(answer)
    db.commit()

    draft_response = client.post(
        "/api/v1/reports/draft",
        json={"assessment_id": str(assessment.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert draft_response.status_code == 201
    report_id = draft_response.json()["id"]

    summaries_response = client.get(
        f"/api/v1/reports/{report_id}/summaries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert summaries_response.status_code == 200
    summaries = summaries_response.json()
    assert len(summaries) == 1
    assert summaries[0]["score"] == 3
    assert summaries[0]["max_score"] == 4
    assert summaries[0]["percentage"] == 75.0
    assert summaries[0]["summary_text"] is None

    report_response = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert "section_overviews" in report
    assert len(report["section_overviews"]) == 1
    assert report["section_overviews"][0]["score"] == 3
    assert report["section_overviews"][0]["percentage"] == 75.0
