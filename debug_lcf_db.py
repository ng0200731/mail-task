import sqlite3
from pathlib import Path
from datetime import datetime


def main() -> None:
    db_path = Path("mailtask.db")
    print("DB path:", db_path.resolve())
    print("Exists:", db_path.exists())
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\nTables:")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for row in cur.fetchall():
        print("-", row["name"])

    print("\nEmails table schema:")
    cur.execute("PRAGMA table_info(emails)")
    for row in cur.fetchall():
        print(dict(row))

    print("\nTotal emails rows:")
    cur.execute("SELECT COUNT(*) AS c FROM emails")
    print(cur.fetchone()["c"])

    print("\nPer provider counts:")
    cur.execute(
        "SELECT provider, COUNT(*) AS c "
        "FROM emails GROUP BY provider ORDER BY c DESC"
    )
    for row in cur.fetchall():
        print(dict(row))

    print("\nLatest 10 LCF emails by date:")
    cur.execute(
        """
        SELECT email_uid, date, fetched_at, created_by
        FROM emails
        WHERE provider = 'lcf'
        ORDER BY datetime(date) DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    for row in rows:
        print(dict(row))

    print("\nMAX datetime(date) for LCF:")
    cur.execute(
        "SELECT MAX(datetime(date)) AS last_date FROM emails WHERE provider = 'lcf'"
    )
    row = cur.fetchone()
    print(row["last_date"])

    print("\nNow (local):", datetime.now().isoformat(" "))
    print("Now (UTC):  ", datetime.utcnow().isoformat(" "))

    conn.close()


if __name__ == "__main__":
    main()


