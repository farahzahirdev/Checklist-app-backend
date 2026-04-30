"""Test suite for bulk checklist import functionality."""
import pytest
import io
import csv
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.checklist import ChecklistStatus, SeverityLevel
from app.schemas.bulk_checklist import ColumnMapping, ParsedRow, BulkChecklistCreateResponse, BulkChecklistTaskResponse, BulkChecklistTaskStatusResponse
from app.services.bulk_checklist import (
    verify_mapping,
    create_checklist_from_file,
    _normalize_severity,
)
from app.services.file_parser import get_column_value, parse_file, parse_csv


class TestSeverityNormalization:
    """Test severity level normalization."""
    
    def test_high_variations(self):
        assert _normalize_severity("high") == SeverityLevel.high
        assert _normalize_severity("High") == SeverityLevel.high
        assert _normalize_severity("H") == SeverityLevel.high
        assert _normalize_severity("3") == SeverityLevel.high
    
    def test_medium_variations(self):
        assert _normalize_severity("medium") == SeverityLevel.medium
        assert _normalize_severity("med") == SeverityLevel.medium
        assert _normalize_severity("M") == SeverityLevel.medium
        assert _normalize_severity("2") == SeverityLevel.medium
    
    def test_low_variations(self):
        assert _normalize_severity("low") == SeverityLevel.low
        assert _normalize_severity("L") == SeverityLevel.low
        assert _normalize_severity("1") == SeverityLevel.low
    
    def test_invalid_severity(self):
        assert _normalize_severity("invalid") is None
        assert _normalize_severity("") is None
        assert _normalize_severity(None) is None


class TestCSVParsing:
    """Test CSV file parsing."""
    
    def test_parse_csv_basic(self):
        csv_content = "Section,Question ID,Question Text,Severity\nGovernance,Q001,Are roles defined?,High\nGovernance,Q002,Is governance documented?,Medium"
        
        rows = parse_csv(csv_content)
        assert len(rows) == 2
        assert rows[0]["Question ID"] == "Q001"
        assert rows[1]["Question ID"] == "Q002"
    
    def test_parse_csv_with_quotes(self):
        csv_content = '''Section,Question Text
"Governance, Risks & Controls","Does the organization have a ""complete"" governance structure?"'''
        
        rows = parse_csv(csv_content)
        assert len(rows) == 1
        assert "complete" in rows[0]["Question Text"]
    
    def test_parse_csv_empty_rows_skipped(self):
        csv_content = "Section,Question ID\nGovernance,Q001\n\nGovernance,Q002\n\n"
        rows = parse_csv(csv_content)
        assert len(rows) == 2  # Empty rows should be skipped
    
    def test_parse_csv_bytes(self):
        csv_content = b"Section,Question ID\nGovernance,Q001"
        rows = parse_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["Question ID"] == "Q001"


class TestParserUtilities:
    def test_get_column_value_by_letter(self):
        row = {"Section": "Governance", "Question ID": "Q001", "_row_number": 2}
        headers = ["Section", "Question ID"]

        assert get_column_value(row, "A", headers) == "Governance"
        assert get_column_value(row, "B", headers) == "Q001"

    import pytest

    @pytest.mark.skip(reason="pandas MultiIndex to_excel limitation")
    def test_parse_xlsx_multilevel_header(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas is required for XLSX parsing tests")

        from io import BytesIO

        columns = pd.MultiIndex.from_tuples([
            ("#", ""),
            ("", "section"),
            ("Source", ""),
            ("Paragraph Title", ""),
            ("Question id", "1"),
            ("Question id", "2"),
            ("Question id", "3"),
            ("Legal Requirement", ""),
            ("Severity", ""),
            ("Explaination", ""),
            ("Expected Implementation", ""),
            ("Answers yes / 4 points", ""),
            ("Answers yes / 3 points", ""),
            ("Answers yes / 2 points", ""),
            ("Answers yes / 1 points", ""),
            ("Final score", ""),
            ("Add a note (for user)", ""),
            ("Upload evidence", ""),
        ])

        data = [
            [
                "1",
                "Governance & Management",
                "ISO 27001",
                "Does the organization have a documented governance structure?",
                "GOV-001",
                "GOV-001.1",
                "GOV-001.1.1",
                "Article 5 of Regulation X",
                "High",
                "Explanation text",
                "Implement a formal governance framework.",
                "Complete governance framework with clear roles",
                "Documented but incomplete governance",
                "Partial documentation of governance",
                "No formal governance structure",
                "4",
                "Note",
                "Evidence",
            ]
        ]

        df = pd.DataFrame(data, columns=columns)
        output = BytesIO()
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, sheet_name="Template", index=False)
        output.seek(0)

        headers, rows = parse_file(output.getvalue(), "test.xlsx")
        assert headers[1] == "section"
        assert headers[4] == "1"
        assert rows[0]["section"] == "Governance & Management"
        assert rows[0]["1"] == "GOV-001"


class TestColumnMapping:
    """Test column mapping verification."""
    
    def test_mapping_spec_has_required_fields(self):
        mapping = ColumnMapping(
            section_name_col="B",
            question_id_col="C",
            legal_requirement_col="F",
            question_text_col="H",
            severity_col="I",
        )
        assert mapping.section_name_col == "B"
        assert mapping.question_id_col == "C"
    
    def test_mapping_with_optional_fields(self):
        mapping = ColumnMapping(
            section_name_col="B",
            question_id_col="C",
            legal_requirement_col="F",
            question_text_col="H",
            severity_col="I",
            child_question_col="D",
            explanation_col="O",
        )
        assert mapping.child_question_col == "D"
        assert mapping.explanation_col == "O"


class TestChecklistCreationFromCSV:
    """Test creating checklist from CSV data (integration test)."""
    
    def test_create_from_csv_with_hierarchy(self, db: Session, admin_user: User):
        """Test creating a checklist with parent-child question hierarchy."""
        csv_content = "Section,Parent Q,Child Q,Grandchild Q,Legal Requirement,Question Text,Severity,Explanation\nGovernance,GOV-001,,Are roles defined?,Does org have governance?,High,\"Define roles\"\nGovernance,GOV-001,GOV-001.1,,Sub-question,Is governance documented?,High,\"Document it\"\nGovernance,GOV-001,GOV-001.1,GOV-001.1.1,Sub-sub requirement,Who approves?,High,\"Board approval required\""
        
        mapping = ColumnMapping(
            section_name_col="Section",
            question_id_col="Parent Q",
            child_question_col="Child Q",
            grandchild_question_col="Grandchild Q",
            legal_requirement_col="Legal Requirement",
            question_text_col="Question Text",
            severity_col="Severity",
            explanation_col="Explanation",
        )
        
        response = create_checklist_from_file(
            db=db,
            actor=admin_user,
            file_content=csv_content,
            file_name="test.csv",
            column_mapping=mapping,
            checklist_title="Test Checklist",
            checklist_description="Test Description",
        )
        
        assert response.status in ("success", "success_with_warnings")
        assert response.checklist_id is not None
        assert response.sections_created >= 1
        assert response.questions_created >= 1


class TestVerifyMapping:
    """Test mapping verification endpoint."""
    
    def test_verify_valid_mapping(self):
        csv_content = "Section,Question ID,Legal Requirement,Question Text,Severity\nGovernance,Q001,Requirement 1,What is governance?,High"
        
        mapping = ColumnMapping(
            section_name_col="Section",
            question_id_col="Question ID",
            legal_requirement_col="Legal Requirement",
            question_text_col="Question Text",
            severity_col="Severity",
        )
        
        response = verify_mapping(
            file_content=csv_content,
            file_name="test.csv",
            column_mapping=mapping,
            preview_rows=10,
        )
        
        assert response.is_valid is True
        assert response.valid_rows == 1
        assert response.invalid_rows == 0
        assert len(response.preview_rows) == 1
    
    def test_verify_missing_required_fields(self):
        csv_content = "Section,Question ID,Legal Requirement\nGovernance,Q001,"  # Missing Question Text and Severity
        
        mapping = ColumnMapping(
            section_name_col="Section",
            question_id_col="Question ID",
            legal_requirement_col="Legal Requirement",
            question_text_col="Non-existent",  # Column doesn't exist
            severity_col="Severity",  # Column doesn't exist
        )
        
        response = verify_mapping(
            file_content=csv_content,
            file_name="test.csv",
            column_mapping=mapping,
            preview_rows=10,
        )
        
        assert response.valid_rows < response.total_rows or not response.is_valid
    
    def test_verify_invalid_severity(self):
        csv_content = "Section,Question ID,Legal Requirement,Question Text,Severity\nGovernance,Q001,Req,What is it?,CRITICAL"  # Invalid severity
        
        mapping = ColumnMapping(
            section_name_col="Section",
            question_id_col="Question ID",
            legal_requirement_col="Legal Requirement",
            question_text_col="Question Text",
            severity_col="Severity",
        )
        
        response = verify_mapping(
            file_content=csv_content,
            file_name="test.csv",
            column_mapping=mapping,
            preview_rows=10,
        )
        
        # Should have warning about invalid severity
        assert not response.preview_rows[0].is_valid or "Invalid severity" in str(response.preview_rows[0].errors)
    
    def test_verify_empty_file(self):
        csv_content = ""
        
        mapping = ColumnMapping(
            section_name_col="Section",
            question_id_col="Question ID",
            legal_requirement_col="Legal Requirement",
            question_text_col="Question Text",
            severity_col="Severity",
        )
        
        response = verify_mapping(
            file_content=csv_content,
            file_name="test.csv",
            column_mapping=mapping,
            preview_rows=10,
        )
        
        assert response.is_valid is False
        assert response.total_rows == 0


class TestBulkChecklistTaskSchemas:
    def test_task_response_schema(self):
        response = BulkChecklistTaskResponse(
            task_id="1234",
            status="pending",
            detail="Queued for background import.",
        )
        assert response.task_id == "1234"
        assert response.status == "pending"

    def test_task_status_response_schema_with_result(self):
        result = BulkChecklistCreateResponse(
            checklist_id=uuid4(),
            checklist_title="Import Checklist",
            sections_created=1,
            questions_created=1,
            sub_questions_created=0,
            total_rows_processed=1,
            warnings=[],
            status="success",
            message="Created checklist.",
        )
        status_response = BulkChecklistTaskStatusResponse(
            task_id="1234",
            celery_state="SUCCESS",
            status="success",
            detail="Completed.",
            result=result,
            error=None,
        )
        assert status_response.result.checklist_title == "Import Checklist"


# Example usage for documentation
if __name__ == "__main__":
    print("Run tests with: pytest apps/api/tests/test_bulk_checklist.py")
