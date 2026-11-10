import sqlite3, time

PATH = "targets.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets(
    id INTEGER PRIMARY KEY, username TEXT UNIQUE, user_id INTEGER,
    title TEXT, num INTEGER, slug TEXT, price INTEGER DEFAULT 20,
    status TEXT DEFAULT 'new', created_at INTEGER);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS gifts_seen(owned_gift_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY, ts INTEGER, text TEXT);
CREATE TABLE IF NOT EXISTS offers(id INTEGER PRIMARY KEY, ts INTEGER,
    target_id INTEGER, business_connection_id TEXT, chat_id INTEGER,
    message_id INTEGER, status TEXT DEFAULT 'sent');
"""

def conn():
    c = sqlite3.connect(PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")   
    c.execute("PRAGMA busy_timeout=30000")
    return c

def init():
    with conn() as c:
        c.executescript(SCHEMA)

def log(text: str):
    with conn() as c:
        c.execute("INSERT INTO log(ts, text) VALUES (?,?)", (int(time.time()), text))

def set_setting(k, v):
    with conn() as c:
        c.execute("INSERT INTO settings(k,v) VALUES(?,?) "
                  "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

def get_setting(k, default=None):
    with conn() as c:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
        return r["v"] if r else default
