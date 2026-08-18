import pytest
from pathlib import Path
from app.core.config import get_settings
from app.database.database import db

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database(tmp_path_factory):
    """
    Guarantees pytest runs against an isolated, clean temporary SQLite database,
    preventing any test projects, assets, or dummy artifacts from polluting
    the user's live production database (balladeer.db).
    """
    temp_dir = tmp_path_factory.mktemp("test_db_session")
    test_db_file = temp_dir / "balladeer_test.db"

    settings = get_settings()
    original_db_path = db.db_path
    original_settings_path = settings.db_path

    # Point the singleton database and settings to the temporary test DB
    db.db_path = test_db_file
    settings.db_path = test_db_file
    db._init_db()

    yield test_db_file

    # Clean up and restore original paths upon test session teardown
    db.db_path = original_db_path
    settings.db_path = original_settings_path
