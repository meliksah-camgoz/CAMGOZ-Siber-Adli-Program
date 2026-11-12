
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base
from database import models


def get_database_path():
    """
    Geliştirme ortamında proje veritabanını,
    kurulu EXE sürümünde AppData veritabanını kullanır.
    """

    if getattr(sys, "frozen", False):
        app_data = Path(
            os.environ.get(
                "APPDATA",
                str(Path.home() / "AppData" / "Roaming")
            )
        )

        database_dir = app_data / "CAMGOZ"
        database_dir.mkdir(parents=True, exist_ok=True)

        return database_dir / "camgoz.db"

    return Path(__file__).resolve().parent / "camgoz.db"


DATABASE_PATH = get_database_path()
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)


def init_database():
    """
    Eksik tabloları oluşturur.
    Mevcut verileri silmez.
    """

    Base.metadata.create_all(bind=engine)
