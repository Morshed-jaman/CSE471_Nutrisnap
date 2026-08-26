import logging

import pytest
from psycopg2 import InterfaceError as Psycopg2InterfaceError
from psycopg2 import OperationalError as Psycopg2OperationalError
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool
from werkzeug.exceptions import InternalServerError

from app import create_app
from app.config import Config, _database_engine_options, _validate_production_database
from app.database_resilience import _connect_with_retry, install_postgresql_connection_retry


def test_vercel_requires_postgresql_transaction_pooler():
    _validate_production_database(
        "postgresql://service:credential@pooler.example.test:6543/postgres",
        is_vercel=True,
    )

    with pytest.raises(RuntimeError, match="must use PostgreSQL"):
        _validate_production_database("sqlite:///production.db", is_vercel=True)
    with pytest.raises(RuntimeError, match="port 6543"):
        _validate_production_database(
            "postgresql://service:credential@pooler.example.test:5432/postgres",
            is_vercel=True,
        )
    with pytest.raises(RuntimeError, match="must be configured"):
        _validate_production_database(None, is_vercel=True)
    with pytest.raises(RuntimeError, match="not a valid database URL"):
        _validate_production_database("postgresql://host:not-a-port/db", is_vercel=True)


def test_local_sqlite_behavior_is_preserved():
    _validate_production_database("sqlite:///local.db", is_vercel=False)
    assert _database_engine_options("sqlite:///local.db") == {"pool_pre_ping": True}


def test_postgresql_uses_null_pool_ssl_and_connection_timeout():
    options = _database_engine_options(
        "postgresql://service:credential@pooler.example.test:6543/postgres"
    )
    assert options["poolclass"] is NullPool
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"sslmode": "require", "connect_timeout": 4}


def test_transient_connection_failures_recover_with_exact_delays(caplog):
    secret = "never-log-this-password"

    class TransientDialect:
        def __init__(self):
            self.attempts = 0

        def connect(self, *_args, **_params):
            self.attempts += 1
            if self.attempts < 3:
                raise Psycopg2OperationalError(
                    f"failed SQL SELECT secret FROM users at private.host for {secret}"
                )
            return "connected"

    dialect = TransientDialect()
    delays = []
    caplog.set_level(logging.WARNING)

    result = _connect_with_retry(
        dialect,
        (f"postgresql://account:{secret}@private.host/database",),
        {"password": secret},
        logger=logging.getLogger("connection-retry-test"),
        sleep=delays.append,
    )

    assert result == "connected"
    assert dialect.attempts == 3
    assert delays == [0.2, 0.8]
    assert "attempt=2 category=DBAPIConnectionError" in caplog.text
    assert "attempt=3 category=DBAPIConnectionError" in caplog.text
    for forbidden in (secret, "private.host", "postgresql://", "SELECT", "secret FROM users"):
        assert forbidden not in caplog.text


def test_interface_error_is_retried_and_final_failure_uses_three_attempts():
    class FailingDialect:
        def __init__(self):
            self.attempts = 0

        def connect(self, *_args, **_params):
            self.attempts += 1
            raise Psycopg2InterfaceError("diagnostic detail must stay private")

    dialect = FailingDialect()
    delays = []
    with pytest.raises(Psycopg2InterfaceError):
        _connect_with_retry(
            dialect,
            (),
            {},
            logger=logging.getLogger("connection-retry-final-test"),
            sleep=delays.append,
        )

    assert dialect.attempts == 3
    assert delays == [0.2, 0.8]


def test_connection_listener_is_postgresql_only_and_installed_once(monkeypatch):
    installed = []
    monkeypatch.setattr(
        "app.database_resilience.event.listen",
        lambda *args, **kwargs: installed.append((args, kwargs)),
    )

    class Dialect:
        def __init__(self, name):
            self.name = name

    class Engine:
        def __init__(self, name):
            self.dialect = Dialect(name)

    postgres_engine = Engine("postgresql")
    sqlite_engine = Engine("sqlite")
    logger = logging.getLogger("listener-test")

    assert install_postgresql_connection_retry(postgres_engine, logger) is True
    assert install_postgresql_connection_retry(postgres_engine, logger) is False
    assert install_postgresql_connection_retry(sqlite_engine, logger) is False
    assert len(installed) == 1
    assert installed[0][0][1] == "do_connect"
    assert installed[0][1] == {"retval": True}


def test_create_app_validates_database_when_running_on_vercel(monkeypatch):
    class UnsafeProductionConfig(Config):
        SECRET_KEY = "test-only"
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="SQLite is not allowed"):
        create_app(UnsafeProductionConfig)


def test_operational_error_returns_sanitized_503(app, caplog):
    secret = "do-not-log-this-credential"

    class DatabaseFailure(Exception):
        pgcode = "08006"

        def __str__(self):
            return f"connection failed for postgresql://user:{secret}@private.example/db"

    def unavailable():
        raise OperationalError("SELECT private_data", {}, DatabaseFailure())

    app.add_url_rule("/_test/database-unavailable", view_func=unavailable)
    caplog.set_level(logging.ERROR)

    response = app.test_client().get("/_test/database-unavailable")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert b"We could not complete that request" in response.data
    assert "category=OperationalError" in caplog.text
    assert "pgcode=08006" in caplog.text
    assert secret not in caplog.text
    assert "private.example" not in caplog.text
    assert "SELECT private_data" not in caplog.text


def test_wrapped_operational_error_returns_sanitized_503(app, caplog):
    secret = "wrapped-secret-must-not-appear"

    def wrapped_failure():
        database_error = OperationalError(
            "SELECT confidential_column",
            {},
            Exception(f"postgresql://user:{secret}@wrapped.private/database"),
        )
        wrapper = InternalServerError()
        wrapper.original_exception = database_error
        raise wrapper

    app.add_url_rule("/_test/wrapped-database-unavailable", view_func=wrapped_failure)
    caplog.set_level(logging.ERROR)

    response = app.test_client().get("/_test/wrapped-database-unavailable")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert b"We could not complete that request" in response.data
    assert "category=OperationalError" in caplog.text
    for forbidden in (secret, "wrapped.private", "postgresql://", "SELECT"):
        assert forbidden not in caplog.text


def test_login_database_failure_is_not_reported_as_invalid_credentials(app, monkeypatch):
    from app.routes import auth_routes

    class FailingQuery:
        def filter_by(self, **_kwargs):
            return self

        def first(self):
            raise OperationalError("SELECT users", {}, Exception("hidden connection detail"))

    class FailingUser:
        query = FailingQuery()

    monkeypatch.setattr(auth_routes, "User", FailingUser)
    response = app.test_client().post(
        "/login",
        data={"email": "person@example.test", "password": "valid-looking-password"},
    )

    assert response.status_code == 503
    assert b"Invalid email or password" not in response.data
