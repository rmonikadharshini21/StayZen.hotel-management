"""MySQL connection helpers. Settings come from backend/.env (copy .env.example)."""
import os
import pymysql
import pymysql.cursors

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_env():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()


def settings(with_db=True):
    cfg = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    if with_db:
        cfg["database"] = os.getenv("DB_NAME", "stayzen")
    return cfg


class DB:
    """Tiny wrapper so route code stays short: db.all(), db.one(), db.run()."""

    def __init__(self, conn):
        self.conn = conn

    def all(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())

    def one(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()

    def run(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.lastrowid

    def many(self, sql, rows):
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)


def connect(with_db=True):
    return pymysql.connect(**settings(with_db))


def get_db():
    """FastAPI dependency: one connection per request, committed at the end."""
    conn = connect()
    try:
        yield DB(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
