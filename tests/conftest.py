import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session as SQLASession
from app.models import Base, User, UserRole
import os
import dotenv

dotenv.load_dotenv(dotenv.find_dotenv(".env", usecwd=True))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ckecklist")

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@pytest.fixture(scope="function")
def db():
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session: SQLASession = Session()
    yield session
    session.close()
    transaction.rollback()
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
