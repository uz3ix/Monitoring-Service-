import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


# Загружаем .env из корня проекта независимо от рабочей папки терминала.
# Уже заданные переменные окружения имеют приоритет.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    database=os.environ["POSTGRES_DB"],
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)


class Base(DeclarativeBase):
    pass


def get_session():
    # Для каждого HTTP-запроса открывается отдельная сессия.
    with Session(engine) as session:
        yield session
