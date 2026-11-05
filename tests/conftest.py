import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main
from app.database import Base


@pytest.fixture
def test_session_local(tmp_path):
    test_db = tmp_path / "test.db"

    test_engine = create_engine(
        f"sqlite:///{test_db.as_posix()}",
        connect_args={"check_same_thread": False}
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    Base.metadata.create_all(bind=test_engine)

    yield TestingSessionLocal

    test_engine.dispose()


@pytest.fixture
def client(test_session_local):
    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db

    with TestClient(main.app) as test_client:
        yield test_client

    main.app.dependency_overrides.clear()


