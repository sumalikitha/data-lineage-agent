import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.database.seed import seed_database


@pytest_asyncio.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await seed_database(path)
    return path


@pytest_asyncio.fixture
async def client(db_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    # Reset the singleton service so it picks up the patched env vars
    import src.api.deps as deps

    deps._service = None

    from src.api.app import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    deps._service = None
