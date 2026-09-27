import pytest

from backend.app.core.config import Settings
from backend.app.service import RagService


@pytest.fixture
def settings(tmp_path):
    return Settings(app_env="test", database_url="sqlite:///:memory:", reports_path=tmp_path / "reports")


@pytest.fixture
def service(settings):
    instance = RagService(settings)
    instance.ingest()
    yield instance
    instance.db.engine.dispose()
