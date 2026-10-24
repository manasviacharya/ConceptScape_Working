from sqlalchemy import inspect, text

from storage.database import Base, engine


SCHEMA_VERSION = 1


def upgrade_database() -> None:
    """Create the current schema and record its version for local/prod startup."""
    from storage import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL)"
        )
        connection.execute(
            text("INSERT INTO schema_migrations (version, applied_at) "
                 "SELECT :version, CURRENT_TIMESTAMP WHERE NOT EXISTS "
                 "(SELECT 1 FROM schema_migrations WHERE version = :version)"),
            {"version": SCHEMA_VERSION},
        )
        existing = {column["name"] for column in inspect(engine).get_columns("documents")}
        if "version" not in existing:
            connection.exec_driver_sql("ALTER TABLE documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        if "processed_at" not in existing:
            connection.exec_driver_sql("ALTER TABLE documents ADD COLUMN processed_at TIMESTAMP NULL")
        message_columns = {column["name"] for column in inspect(engine).get_columns("chat_messages")}
        if "metadata_json" not in message_columns:
            connection.exec_driver_sql("ALTER TABLE chat_messages ADD COLUMN metadata_json TEXT NULL")
