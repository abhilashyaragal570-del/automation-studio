import sqlite3
import datetime
import os
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "studio.db")))


def conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def now_str():
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            raw_text TEXT,
            category TEXT,
            urgency TEXT,
            sender_name TEXT,
            topic TEXT,
            deadline TEXT,
            summary TEXT,
            reply TEXT,
            mock INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT,
            source TEXT,
            raw_text TEXT,
            email_id INTEGER,
            error TEXT
        )""")


def log_call():
    now = datetime.datetime.now()
    with conn() as c:
        c.execute("INSERT INTO calls (day, created_at) VALUES (?, ?)",
                  (now.date().isoformat(), now.isoformat()))


def calls_today():
    today = datetime.date.today().isoformat()
    with conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM calls WHERE day = ?", (today,)).fetchone()
    return row["n"]


def save_email(raw_text, r, mock):
    with conn() as c:
        cur = c.execute(
            """INSERT INTO emails (created_at, raw_text, category, urgency, sender_name,
               topic, deadline, summary, reply, mock) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (now_str(), raw_text,
             r["category"], r["urgency"], r["sender_name"], r["topic"],
             r["deadline"], r["summary"], r["reply"], 1 if mock else 0))
        return cur.lastrowid


def list_emails(limit=50):
    with conn() as c:
        rows = c.execute("SELECT * FROM emails ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def create_job(raw_text, source):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO jobs (created_at, status, source, raw_text, error) VALUES (?, 'queued', ?, ?, '')",
            (now_str(), source, raw_text))
        return cur.lastrowid


def queued_count():
    with conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM jobs WHERE status = 'queued'").fetchone()
    return row["n"]


def claim_next_job():
    with conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        c.execute("UPDATE jobs SET status = 'processing', started_at = ? WHERE id = ?",
                  (now_str(), row["id"]))
        return dict(row)


def finish_job(job_id, status, email_id=None, error=""):
    with conn() as c:
        c.execute("UPDATE jobs SET status = ?, finished_at = ?, email_id = ?, error = ? WHERE id = ?",
                  (status, now_str(), email_id, error, job_id))


def reset_stuck_jobs():
    with conn() as c:
        c.execute("UPDATE jobs SET status = 'queued' WHERE status = 'processing'")


def get_job(job_id):
    with conn() as c:
        row = c.execute(
            """SELECT id, created_at, started_at, finished_at, status, source, email_id, error
               FROM jobs WHERE id = ?""", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit=30):
    with conn() as c:
        rows = c.execute(
            """SELECT id, created_at, started_at, finished_at, status, source, email_id, error
               FROM jobs ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]

def stats():
    with conn() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM emails").fetchone()["n"]
        by_category = c.execute(
            "SELECT category AS name, COUNT(*) AS n FROM emails GROUP BY category ORDER BY n DESC").fetchall()
        by_urgency = c.execute(
            "SELECT urgency AS name, COUNT(*) AS n FROM emails GROUP BY urgency ORDER BY n DESC").fetchall()
        by_status = c.execute(
            "SELECT status AS name, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()
        avg = c.execute(
            """SELECT AVG((julianday(finished_at) - julianday(started_at)) * 86400) AS s
               FROM jobs WHERE status = 'done' AND started_at IS NOT NULL AND finished_at IS NOT NULL""").fetchone()["s"]
    return {
        "total_emails": total,
        "by_category": [dict(r) for r in by_category],
        "by_urgency": [dict(r) for r in by_urgency],
        "jobs_by_status": [dict(r) for r in by_status],
        "avg_job_seconds": round(avg, 1) if avg is not None else None,
    }

def retry_job(job_id):
    with conn() as c:
        cur = c.execute(
            """UPDATE jobs SET status = 'queued', started_at = NULL, finished_at = NULL,
               email_id = NULL, error = '' WHERE id = ? AND status = 'failed'""", (job_id,))
        return cur.rowcount == 1

def clear_finished_jobs():
    with conn() as c:
        cur = c.execute("DELETE FROM jobs WHERE status IN ('done', 'failed')")
        return cur.rowcount    