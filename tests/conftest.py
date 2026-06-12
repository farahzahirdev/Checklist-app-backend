import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session as SQLASession
from app.models import Base, User, UserRole
from app.models.checklist import Checklist, ChecklistSection, ChecklistQuestion
from app.models.assessment import Assessment, AssessmentStatus
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import os
import dotenv
from jose import jwt

# Map PostgreSQL INET type to VARCHAR for SQLite tests
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import INET

@compiles(INET, "sqlite")
def compile_inet_sqlite(element, compiler, **kw):
    return "VARCHAR(45)"

dotenv.load_dotenv(dotenv.find_dotenv(".env", usecwd=True))
# Use sqlite for fast local testing
DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db():
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(bind=connection)
    Session = sessionmaker(bind=connection)
    session: SQLASession = Session()
    yield session
    transaction.rollback()
    session.close()
    connection.close()

# Admin user fixture for tests
@pytest.fixture(scope="function")
def admin_user(db):
    # Upsert admin user to avoid unique and foreign key errors
    user = db.query(User).filter_by(email="admin@example.com").first()
    if user:
        user.password_hash = "test"
        user.is_active = True
        user.role = UserRole.admin
    else:
        user = User(
            email="admin@example.com",
            password_hash="test",
            is_active=True,
            role=UserRole.admin,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Customer user fixture for tests
@pytest.fixture(scope="function")
def customer_user(db):
    user = db.query(User).filter_by(email="customer@example.com").first()
    if user:
        user.password_hash = "test"
        user.is_active = True
        user.role = UserRole.customer
    else:
        user = User(
            email="customer@example.com",
            password_hash="test",
            is_active=True,
            role=UserRole.customer,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Sample checklist fixture for tests
@pytest.fixture(scope="function")
def sample_checklist(db, admin_user):
    from app.models.checklist import ChecklistType
    
    # Create a checklist type first
    checklist_type = ChecklistType(
        code="TEST_TYPE",
        name="Test Type",
        description="A test checklist type",
        is_active=True,
    )
    db.add(checklist_type)
    db.flush()
    
    # Create a simple checklist for testing
    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version="1.0",
        created_by=admin_user.id,
        updated_by=admin_user.id,
    )
    db.add(checklist)
    db.flush()
    
    # Create a section
    section = ChecklistSection(
        checklist_id=checklist.id,
        section_code="TEST_SECTION",
        display_order=1,
    )
    db.add(section)
    db.flush()
    
    # Create a question
    question = ChecklistQuestion(
        checklist_id=checklist.id,
        section_id=section.id,
        question_code="TEST_QUESTION_1",
        audit_type="compliance",
        points=1,
        display_order=1,
    )
    db.add(question)
    db.commit()
    
    # Refresh to populate relationships
    db.refresh(checklist)
    db.refresh(section)
    db.refresh(question)
    
    # Store related objects for test access
    checklist.sections = [section]
    checklist.questions = [question]
    section.questions = [question]
    
    return checklist

# Test client fixture
@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db
    
    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    test_client = TestClient(app)
    yield test_client
    
    app.dependency_overrides.clear()

# Admin token fixture
@pytest.fixture(scope="function")
def admin_token(admin_user):
    return create_access_token(user_id=str(admin_user.id), role=str(admin_user.role))

# Customer token fixture
@pytest.fixture(scope="function")
def customer_token(customer_user):
    return create_access_token(user_id=str(customer_user.id), role=str(customer_user.role))
