import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from framework.adapters.sql_adapter import SQLAdapter


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE repo (id TEXT, name TEXT, division_id TEXT)"))
        conn.execute(text("INSERT INTO repo VALUES ('r1', 'payments-api', 'payments')"))
        conn.execute(text("INSERT INTO repo VALUES ('r2', 'platform-core', 'platform')"))
    monkeypatch.setenv("TEST_WAREHOUSE_URL", url)
    return url


def test_sql_adapter_runs_query_and_normalizes(sqlite_url):
    adapter = SQLAdapter("repos", "repo", {
        "connection_env": "TEST_WAREHOUSE_URL",
        "query": "SELECT id, name, division_id FROM repo WHERE division_id = :div",
        "params": {"div": "payments"},
    })
    records = adapter.run()
    assert len(records) == 1
    assert records[0].id == "r1"
    assert records[0].name == "payments-api"


def test_sql_adapter_requires_connection_env(monkeypatch):
    monkeypatch.delenv("MISSING_URL", raising=False)
    with pytest.raises(ValueError, match="MISSING_URL"):
        SQLAdapter("repos", "repo", {"connection_env": "MISSING_URL", "query": "SELECT 1"})
