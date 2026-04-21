"""SQLAlchemy custom column types."""
from datetime import UTC

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class TZDateTime(TypeDecorator):
    """Timezone-aware datetime that survives SQLite's tzinfo-stripping round-trip.

    Incoming aware datetimes are normalised to UTC before storage. On read,
    the naive datetime returned by SQLite is re-stamped with UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        del _dialect
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, _dialect):
        del _dialect
        if value is not None:
            return value.replace(tzinfo=UTC)
        return value
