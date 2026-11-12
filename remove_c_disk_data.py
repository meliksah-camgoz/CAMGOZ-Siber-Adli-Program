"""Back up CAMGOZ SQLite DB, then remove only the C: filesystem activity table."""
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "database" / "camgoz.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"Veritabanı bulunamadı: {DB_PATH}")
        print("database/database.py içindeki gerçek DB yolunu kontrol edin.")
        return 1

    backup_path = DB_PATH.with_name(
        f"camgoz_before_c_cleanup_{datetime.now():%Y%m%d_%H%M%S}.db"
    )

    try:
        # SQLite backup API: canlı dosya kopyalamaktan daha güvenlidir.
        with sqlite3.connect(DB_PATH) as source:
            with sqlite3.connect(backup_path) as backup:
                source.backup(backup)

        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                ("filesystem_activities",),
            ).fetchone()

            if exists:
                connection.execute("DROP TABLE filesystem_activities")
                connection.commit()
                print("filesystem_activities tablosu kaldırıldı.")
            else:
                print("filesystem_activities tablosu zaten mevcut değil.")

        print(f"Yedek oluşturuldu: {backup_path}")
        print("Evidence, Audit Trail ve USB tablolarına dokunulmadı.")
        return 0

    except Exception as exc:
        print(f"Temizlik başarısız: {exc}")
        print(f"Oluşturulmuşsa yedek dosya: {backup_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
