"""
Company and Organization Schemas

Schemas for managing companies and user-company associations.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Company Creation and Management

class CreateCompanyRequest(BaseModel):
    """Request to create a new company."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    slug: str = Field(..., min_length=1, max_length=255, pattern="^[a-z0-9-]+$", description="URL-friendly slug (lowercase, hyphens)")
    email: str | None = Field(None, description="Company contact email")
    website: str | None = Field(None, max_length=255, description="Company website URL")
    region: str | None = Field(None, max_length=100, description="Geographic region (e.g., EU, US, APAC)")
    country: str | None = Field(None, max_length=100, description="Country")
    industry: str | None = Field(None, max_length=50, description="Industry classification")
    size: str | None = Field(None, max_length=50, description="Company size (startup, small, medium, large, enterprise)")
    description: str | None = Field(None, description="Company description")
    compliance_framework: str | None = Field(None, max_length=100, description="Primary compliance framework (ISO 27001, HIPAA, SOC 2, etc.)")


class UpdateCompanyRequest(BaseModel):
    """Request to update company information."""
    
    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None)
    website: str | None = Field(None, max_length=255)
    region: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=50)
    size: str | None = Field(None, max_length=50)
    description: str | None = Field(None)
    compliance_framework: str | None = Field(None, max_length=100)
    is_active: bool | None = Field(None)


class CompanyResponse(BaseModel):
    """Response model for company information."""
    
    id: UUID
    name: str
    slug: str
    email: str | None
    website: str | None
    region: str | None
    country: str | None
    industry: str | None
    size: str | None
    description: str | None
    compliance_framework: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CompanyDetailResponse(CompanyResponse):
    """Detailed company response with user count."""
    
    user_count: int = Field(default=0, description="Number of users assigned to this company")


# User-Company Association

class AssignUserToCompanyRequest(BaseModel):
    """Request to assign a user to a company with a specific role."""
    
    user_id: UUID = Field(..., description="User ID to assign")
    company_id: UUID = Field(..., description="Company ID to assign to")
    role: str = Field(..., description="User's role in company (owner, manager, staff, auditor, etc.)")
    job_title: str | None = Field(None, max_length=255, description="User's job title at this company")
    department: str | None = Field(None, max_length=255, description="User's department at this company")


class UpdateUserCompanyRoleRequest(BaseModel):
    """Request to update user's role and details in a company."""
    
    role: str | None = Field(None, description="New role in company")
    job_title: str | None = Field(None, max_length=255, description="Updated job title")
    department: str | None = Field(None, max_length=255, description="Updated department")
    is_active: bool | None = Field(None, description="Activate/deactivate association")


class UserCompanyAssignmentResponse(BaseModel):
    """Response model for user-company assignment."""
    
    id: UUID
    user_id: UUID
    company_id: UUID
    role: str
    job_title: str | None
    department: str | None
    is_active: bool
    assigned_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserCompanyDetailResponse(UserCompanyAssignmentResponse):
    """Detailed user-company assignment with related info."""
    
    user_email: str = Field(default="", description="User's email")
    company_name: str = Field(default="", description="Company name")
    company_slug: str = Field(default="", description="Company slug")


# Batch operations

class AssignUserToMultipleCompaniesRequest(BaseModel):
    """Request to assign a user to multiple companies at once."""
    
    user_id: UUID = Field(..., description="User ID")
    companies: list[AssignUserToCompanyRequest] = Field(..., description="List of companies to assign to")


class GetUserCompaniesRequest(BaseModel):
    """Request to get all companies for a user."""
    
    user_id: UUID = Field(..., description="User ID")
    include_inactive: bool = Field(default=False, description="Include inactive assignments")


class GetCompanyUsersRequest(BaseModel):
    """Request to get all users in a company."""
    
    company_id: UUID = Field(..., description="Company ID")
    include_inactive: bool = Field(default=False, description="Include inactive assignments")


# List responses

class CompanyListResponse(BaseModel):
    """Paginated list of companies."""
    
    total: int
    companies: list[CompanyResponse]
    skip: int
    limit: int


class UserCompanyListResponse(BaseModel):
    """Paginated list of user-company assignments."""
    
    total: int
    assignments: list[UserCompanyDetailResponse]
    skip: int
    limit: int
