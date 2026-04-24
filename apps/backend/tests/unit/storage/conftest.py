import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from home_curator.storage.models import Base


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()
