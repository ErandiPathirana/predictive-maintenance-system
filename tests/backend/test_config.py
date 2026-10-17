import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, Settings


def S(**kw):
    return Settings(_env_file=None, **kw)


def test_postgres_urls_are_normalised_for_psycopg3():
    assert S(database_url="postgres://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert S(database_url="postgresql://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"


def test_relative_sqlite_path_becomes_absolute_under_backend():
    url = S(database_url="sqlite:///predictions.db").database_url
    assert url.startswith("sqlite:///") and BACKEND_DIR.as_posix() in url


def test_memory_sqlite_is_untouched():
    assert S(database_url="sqlite:///:memory:").database_url == "sqlite:///:memory:"


def test_cors_list_is_parsed_and_trimmed():
    assert S(cors_origins="http://a.com/, https://b.com ,").cors_origin_list == ["http://a.com", "https://b.com"]


@pytest.mark.parametrize("bad", [{"cors_origins": "*"}, {"cors_origins": "http://a.com,*"}, {"cors_origins": ""},
                                 {"allow_smoke_test_bundle": True}, {"auto_create_tables": True}])
def test_production_refuses_unsafe_settings(bad):
    base = {"environment": "production", "cors_origins": "https://app.example.com"}
    base.update(bad)
    with pytest.raises(ValidationError):
        S(**base)


def test_development_allows_wildcard_but_production_does_not():
    assert S(environment="development", cors_origins="*").cors_origin_list == ["*"]


def test_blank_api_key_means_disabled():
    assert S(api_key="").api_key is None
