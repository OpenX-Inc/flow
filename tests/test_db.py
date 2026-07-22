"""Tests for database engine setup and URL normalization."""

from unittest.mock import MagicMock, patch

from flow.store.db import make_engine, normalize_db_url


def test_normalize_db_url_sqlite():
    assert normalize_db_url("sqlite:///foo.db") == "sqlite:///foo.db"


def test_normalize_db_url_psycopg():
    url = "postgresql+psycopg://user:pass@localhost:5432/db"
    assert normalize_db_url(url) == url


def test_normalize_db_url_asyncpg_conversion():
    async_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
    expected = "postgresql+psycopg://user:pass@localhost:5432/db"
    assert normalize_db_url(async_url) == expected

    async_url_short = "postgres+asyncpg://user:pass@localhost:5432/db"
    assert normalize_db_url(async_url_short) == expected


@patch("flow.store.db.create_engine")
@patch("flow.store.db.SQLModel.metadata.create_all")
def test_make_engine_normalizes_asyncpg(mock_create_all, mock_create_engine):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    async_url = "postgresql+asyncpg://openx:openx@db:5432/openx_cloud"
    make_engine(async_url)

    mock_create_engine.assert_called_once_with(
        "postgresql+psycopg://openx:openx@db:5432/openx_cloud",
        connect_args={}
    )
