import sqlite3
import threading

DB_PATH = "bot_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER,
            key TEXT,
            value INTEGER,
            PRIMARY KEY (chat_id, key)
        )
    """)
    conn.commit()
    conn.close()

def get_setting(chat_id, key, default=0):
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(chat_id, key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (chat_id, key, value) VALUES (?, ?, ?)", (chat_id, key, value))
    conn.commit()
    conn.close()
