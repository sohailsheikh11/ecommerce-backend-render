import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# Set DB_SSL_CA=ca.pem on Render. Leave unset locally.
_ca = os.getenv("DB_SSL_CA")
connect_args = {"ssl": {"ca": _ca}} if _ca else {}

engine = create_engine(
      settings.database_url,
      pool_pre_ping=True,
      pool_recycle=280,
      connect_args=connect_args,
  )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
      pass


def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
