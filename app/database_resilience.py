import time
from collections.abc import Callable
from logging import Logger

from psycopg2 import InterfaceError as Psycopg2InterfaceError
from psycopg2 import OperationalError as Psycopg2OperationalError
from sqlalchemy import event
from sqlalchemy.engine import Engine


_RETRY_DELAYS = (0.2, 0.8)
_RETRY_INSTALLED_ATTRIBUTE = "_nutrisnap_connect_retry_installed"


def _connect_with_retry(
    dialect,
    connection_args,
    connection_params,
    *,
    logger: Logger,
    sleep: Callable[[float], None] = time.sleep,
):
    """Create one DBAPI connection, retrying only transient handshake failures."""
    for attempt in range(1, len(_RETRY_DELAYS) + 2):
        try:
            return dialect.connect(*connection_args, **connection_params)
        except (Psycopg2OperationalError, Psycopg2InterfaceError):
            if attempt > len(_RETRY_DELAYS):
                raise
            logger.warning(
                "PostgreSQL connection retry attempt=%d category=DBAPIConnectionError",
                attempt + 1,
            )
            sleep(_RETRY_DELAYS[attempt - 1])


def install_postgresql_connection_retry(engine: Engine, logger: Logger) -> bool:
    """Install the connection-only retry listener once on a PostgreSQL engine."""
    if engine.dialect.name != "postgresql":
        return False
    if getattr(engine, _RETRY_INSTALLED_ATTRIBUTE, False):
        return False

    def do_connect(dialect, _connection_record, connection_args, connection_params):
        return _connect_with_retry(
            dialect,
            connection_args,
            connection_params,
            logger=logger,
        )

    event.listen(engine, "do_connect", do_connect, retval=True)
    setattr(engine, _RETRY_INSTALLED_ATTRIBUTE, True)
    return True
