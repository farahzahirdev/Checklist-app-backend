"""Schemas for bulk checklist import via Excel/CSV parsing."""
from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID


class ColumnMapping(BaseModel):
    """Defines how columns in the uploaded file map to data fields."""
    # Required columns
    section_name_col: str = Field(description="Column letter or name for section title")
    question_id_col: str = Field(description="Column letter or name for parent question ID")
    child_question_col: str | None = Field(default=None, description="Column for child question ID (optional)")
    grandchild_question_col: str | None = Field(default=None, description="Column for grandchild question ID (optional)")
    legal_requirement_col: str = Field(description="Column for legal requirement text")
    question_text_col: str = Field(description="Column for question text presented to user")
    severity_col: str = Field(description="Column for severity level (Low/Medium/High)")
    explanation_col: str | None = Field(default=None, description="Column for explanation")
    expected_implementation_col: str | None = Field(default=None, description="Column for expected implementation")
    source_ref_col: str | None = Field(default=None, description="Column for source reference")

    # Score guidance columns (optional but recommended)
    guidance_score_4_col: str | None = Field(default=None, description="Column for score 4 guidance")
    guidance_score_3_col: str | None = Field(default=None, description="Column for score 3 guidance")
    guidance_score_2_col: str | None = Field(default=None, description="Column for score 2 guidance")
    guidance_score_1_col: str | None = Field(default=None, description="Column for score 1 guidance")


class ColumnMappingResponse(BaseModel):
    """Template column mapping specification for the API consumer."""
    description: str
    required_columns: list[str]
    optional_columns: list[str]
    column_mapping_template: ColumnMapping
    example_format: dict


class VerifyMappingRequest(BaseModel):
    """Request to verify column mapping against uploaded file."""
    file_content: bytes | str = Field(description="File content (base64 or raw)")
    file_name: str = Field(description="Original file name (for format detection)")
    column_mapping: ColumnMapping
    preview_rows: int = Field(default=10, ge=1, le=100, description="Number of rows to preview")


class ParsedRow(BaseModel):
    """A single parsed row from the file."""
    row_number: int
    section_name: str
    parent_question_id: str
    parent_question_text: str
    child_question_id: str | None = None
    child_question_text: str | None = None
    grandchild_question_id: str | None = None
    grandchild_question_text: str | None = None
    legal_requirement: str
    severity: Literal["low", "medium", "high"]
    explanation: str | None = None
    expected_implementation: str | None = None
    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class VerifyMappingResponse(BaseModel):
    """Response from verification with preview data."""
    is_valid: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    preview_rows: list[ParsedRow]
    column_headers: list[str] = Field(description="Detected column headers")
    warnings: list[str] = Field(default_factory=list)


class BulkChecklistCreateRequest(BaseModel):
    """Request to create checklist from parsed file."""
    file_content: bytes | str = Field(description="File content (base64 or raw)")
    file_name: str
    column_mapping: ColumnMapping
    
    # Checklist metadata
    checklist_title: str = Field(min_length=1, max_length=255)
    checklist_description: str | None = Field(default=None)
    checklist_type_code: str = Field(default="compliance")
    checklist_version: int = Field(default=1, ge=1)


class BulkChecklistCreateResponse(BaseModel):
    """Response after creating checklist from bulk import."""
    checklist_id: UUID
    checklist_title: str
    sections_created: int
    questions_created: int
    sub_questions_created: int
    total_rows_processed: int
    warnings: list[str] = Field(default_factory=list)
    status: Literal["success", "success_with_warnings", "failed"]
    message: str


class TemplateDownloadRequest(BaseModel):
    """Request to download template file."""
    format: Literal["csv", "xlsx"] = Field(default="csv")
    include_sample_data: bool = Field(default=False, description="Include sample data rows")


class SampleDataResponse(BaseModel):
    """Sample data for template download."""
    download_url: str
    file_name: str
    format: Literal["csv", "xlsx"]
    columns: list[str]
    sub_columns: dict[str, list[str]] = Field(description="Hierarchical info about sub-columns")
