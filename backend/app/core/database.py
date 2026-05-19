from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings
from app.models.models import *  # noqa: F401,F403


connect_args = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}

engine = create_engine(
    settings.database_url,
    echo=settings.env == 'development',
    pool_pre_ping=True,
    connect_args=connect_args,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
