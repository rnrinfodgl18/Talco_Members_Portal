from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings


engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def database_status() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "reachable"
    except SQLAlchemyError:
        return False, "unreachable"

