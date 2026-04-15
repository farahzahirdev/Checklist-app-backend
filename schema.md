# Backend Schema

This document reflects the current backend models in `apps/api/app/models` and the auth request/response shapes in `apps/api/app/schemas/auth.py`.

## 1. Identity, Auth, Access, Payment

### users
- id: uuid pk
- email: varchar(320) unique not null
- password_hash: varchar(255) not null
- role: user_role not null default `customer`
- is_active: boolean not null default true
- created_at: timestamptz not null
- updated_at: timestamptz not null

### mfa_totp
- id: uuid pk
- user_id: uuid fk -> users.id unique not null
- secret_encrypted: text not null
- is_verified: boolean not null default false
- backup_codes_hash: jsonb null
- created_at: timestamptz not null
- updated_at: timestamptz not null

### payments
- id: uuid pk
- user_id: uuid fk -> users.id not null
- stripe_payment_intent_id: varchar(100) unique not null
- amount_cents: integer not null
- currency: varchar(3) not null default `USD`
- status: payment_status not null default `pending`
- paid_at: timestamptz null
- created_at: timestamptz not null

### access_windows
- id: uuid pk
- user_id: uuid fk -> users.id not null
- payment_id: uuid fk -> payments.id null
- activated_at: timestamptz not null
- expires_at: timestamptz not null
- created_at: timestamptz not null

### access_events
- id: uuid pk
- user_id: uuid fk -> users.id not null
- access_window_id: uuid fk -> access_windows.id not null
- event_type: access_event_type not null
- event_metadata: jsonb null
- request_id: varchar(100) null
- created_at: timestamptz not null

## 2. Checklist Content

### checklist_types
- id: uuid pk
- code: varchar(80) unique not null
- name: varchar(255) not null
- description: text null
- is_active: boolean not null default true
- created_at: timestamptz not null
- updated_at: timestamptz not null

### checklists
- id: uuid pk
- checklist_type_id: uuid fk -> checklist_types.id not null
- version: integer not null
- title: varchar(255) not null
- description: text null
- status: checklist_status not null default `draft`
- effective_from: date null
- effective_to: date null
- created_by: uuid fk -> users.id not null
- updated_by: uuid fk -> users.id not null
- created_at: timestamptz not null
- updated_at: timestamptz not null

Unique constraint:
- unique(checklist_type_id, version)

### checklist_sections
- id: uuid pk
- checklist_id: uuid fk -> checklists.id not null
- section_code: varchar(100) not null
- title: varchar(255) not null
- source_ref: varchar(255) null
- display_order: integer not null
- created_at: timestamptz not null
- updated_at: timestamptz not null

Unique constraints:
- unique(checklist_id, section_code)
- unique(checklist_id, display_order)

### checklist_questions
- id: uuid pk
- checklist_id: uuid fk -> checklists.id not null
- section_id: uuid fk -> checklist_sections.id not null
- question_code: varchar(120) not null
- paragraph_title: varchar(255) null
- legal_requirement: text not null
- question_text: text not null
- explanation: text null
- expected_implementation: text null
- guidance_score_4: text null
- guidance_score_3: text null
- guidance_score_2: text null
- guidance_score_1: text null
- recommendation_template: text null
- severity: severity_level not null
- report_domain: varchar(120) null
- report_chapter: varchar(120) null
- illustrative_image_url: text null
- note_enabled: boolean not null default true
- evidence_enabled: boolean not null default true
- final_score_mode: question_score_mode not null default `answer_only`
- display_order: integer not null
- is_active: boolean not null default true
- created_at: timestamptz not null
- updated_at: timestamptz not null

Unique constraints:
- unique(checklist_id, question_code)
- unique(section_id, display_order)

### checklist_translations
- id: uuid pk
- checklist_id: uuid fk -> checklists.id not null
- lang_code: varchar(10) not null
- title: varchar(255) not null
- description: text null
- created_at: timestamptz not null

Unique constraint:
- unique(checklist_id, lang_code)

### checklist_section_translations
- id: uuid pk
- section_id: uuid fk -> checklist_sections.id not null
- lang_code: varchar(10) not null
- title: varchar(255) not null
- created_at: timestamptz not null

Unique constraint:
- unique(section_id, lang_code)

### checklist_question_translations
- id: uuid pk
- question_id: uuid fk -> checklist_questions.id not null
- lang_code: varchar(10) not null
- question_text: text not null
- explanation: text null
- expected_implementation: text null
- guidance_score_4: text null
- guidance_score_3: text null
- guidance_score_2: text null
- guidance_score_1: text null
- recommendation_template: text null
- created_at: timestamptz not null

Unique constraint:
- unique(question_id, lang_code)

## 3. Assessments

### assessments
- id: uuid pk
- user_id: uuid fk -> users.id not null
- checklist_id: uuid fk -> checklists.id not null
- access_window_id: uuid fk -> access_windows.id not null
- started_at: timestamptz null
- submitted_at: timestamptz null
- status: assessment_status not null default `not_started`
- expires_at: timestamptz not null
- completion_percent: numeric(5,2) not null default 0
- retention_expires_at: timestamptz null
- purged_at: timestamptz null
- created_at: timestamptz not null
- updated_at: timestamptz not null

### assessment_answers
- id: uuid pk
- assessment_id: uuid fk -> assessments.id not null
- question_id: uuid fk -> checklist_questions.id not null
- answer: answer_choice not null
- answer_score: integer not null
- weighted_priority: priority_level null
- note_text: text null
- answered_at: timestamptz not null
- updated_at: timestamptz not null
- purged_at: timestamptz null

Unique constraint:
- unique(assessment_id, question_id)

### assessment_evidence_files
- id: uuid pk
- assessment_id: uuid fk -> assessments.id not null
- answer_id: uuid fk -> assessment_answers.id null
- question_id: uuid fk -> checklist_questions.id not null
- storage_key: varchar(512) not null
- original_filename: varchar(255) not null
- mime_type: varchar(120) not null
- file_size_bytes: integer not null
- sha256: varchar(64) not null
- scan_status: malware_scan_status not null default `pending`
- uploaded_by: uuid fk -> users.id not null
- uploaded_at: timestamptz not null
- deleted_at: timestamptz null
- purged_at: timestamptz null

### assessment_section_scores
- id: uuid pk
- assessment_id: uuid fk -> assessments.id not null
- section_id: uuid fk -> checklist_sections.id not null
- avg_score: numeric(4,2) not null
- answered_count: integer not null
- total_count: integer not null
- computed_at: timestamptz not null

Unique constraint:
- unique(assessment_id, section_id)

## 4. Reporting and Review

### reports
- id: uuid pk
- assessment_id: uuid fk -> assessments.id unique not null
- status: report_status not null default `draft_generated`
- draft_generated_at: timestamptz null
- reviewed_by: uuid fk -> users.id null
- reviewed_at: timestamptz null
- approved_by: uuid fk -> users.id null
- approved_at: timestamptz null
- final_pdf_storage_key: varchar(512) null
- final_pdf_published_at: timestamptz null
- draft_deleted_at: timestamptz null
- final_deleted_at: timestamptz null
- created_at: timestamptz not null
- updated_at: timestamptz not null

### report_section_summaries
- id: uuid pk
- report_id: uuid fk -> reports.id not null
- section_id: uuid fk -> checklist_sections.id null
- chapter_code: varchar(120) null
- summary_text: text not null
- created_by: uuid fk -> users.id not null
- updated_by: uuid fk -> users.id not null
- created_at: timestamptz not null
- updated_at: timestamptz not null

### report_findings
- id: uuid pk
- report_id: uuid fk -> reports.id not null
- question_id: uuid fk -> checklist_questions.id not null
- answer_id: uuid fk -> assessment_answers.id not null
- priority: priority_level not null
- finding_text: text not null
- recommendation_text: text null
- created_at: timestamptz not null

### report_review_events
- id: uuid pk
- report_id: uuid fk -> reports.id not null
- actor_user_id: uuid fk -> users.id not null
- event_type: report_event_type not null
- event_note: text null
- created_at: timestamptz not null

## 5. Audit and Operational Logging

### audit_logs
- id: uuid pk
- actor_user_id: uuid fk -> users.id null
- actor_role: user_role null
- action: audit_action not null
- target_entity: varchar(120) not null
- target_id: uuid null
- request_id: varchar(100) null
- ip_address: inet null
- user_agent: text null
- before_json: jsonb null
- after_json: jsonb null
- created_at: timestamptz not null

### operational_events
- id: uuid pk
- event_type: operational_event_type not null
- severity: operational_severity not null
- source: varchar(120) not null
- request_id: varchar(100) null
- payload_json: jsonb null
- created_at: timestamptz not null

## 6. Auth API Schemas

### LoginRequest
- email: email
- password: string
- mfa_code: string | null

Current behavior:
- `/auth/login` accepts email/password and optionally `mfa_code`.
- `/auth/mfa/setup` starts MFA enrollment.
- `/auth/mfa/verify` confirms MFA enrollment.

### RegistrationRequest
- email: email
- password: string

### MfaVerifyRequest
- code: string

### MfaSetupDetailsResponse
- secret: string
- provisioning_uri: string
- verified: boolean

### AuthUserResponse
- id: uuid
- email: email
- role: user_role
- is_active: boolean

### AuthResponse
- user: AuthUserResponse
- access_token: string | null
- token_type: string
- mfa_required: boolean
- mfa_enabled: boolean

### RoleAssignment
- role: user_role

## 7. Enums

### user_role
- admin
- auditor
- customer

### payment_status
- pending
- succeeded
- failed

### access_event_type
- unlocked_after_payment
- assessment_started
- access_expired
- manually_extended
- manually_revoked

### checklist_status
- draft
- published
- archived

### severity_level
- low
- medium
- high

### question_score_mode
- answer_only
- answer_with_adjustment

### answer_choice
- yes
- partially
- dont_know
- no

### priority_level
- low
- medium
- high

### assessment_status
- not_started
- in_progress
- submitted
- expired
- closed

### malware_scan_status
- pending
- clean
- infected
- failed

### report_status
- draft_generated
- under_review
- changes_requested
- approved
- published

### report_event_type
- draft_generated
- review_started
- summary_updated
- changes_requested
- approved
- published

### audit_action
- auth_login
- auth_logout
- auth_mfa_verify
- checklist_create
- checklist_update
- checklist_publish
- assessment_submit
- report_approve
- report_publish
- user_role_change

### operational_event_type
- payment_webhook_received
- payment_webhook_processed
- report_generation_started
- report_generation_finished
- retention_job_started
- retention_job_finished
- file_scan_completed

### operational_severity
- info
- warning
- error

## 8. Notes

- The current codebase models auth as a single login endpoint with optional MFA code plus separate MFA setup and verify endpoints.
- Authorization is currently handled through `users.role`; there are no RBAC join tables in this branch.
- Retention fields are present directly on assessment, answer, evidence, and report tables.