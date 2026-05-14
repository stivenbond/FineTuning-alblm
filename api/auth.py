import sqlite3
import secrets
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict

DB_PATH = Path(__file__).parent / "lahuta_auth.db"

def init_db():
    """Initializes the SQLite database for authentication."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT NOT NULL,
            prefix TEXT NOT NULL,
            name TEXT,
            created_at INTEGER NOT NULL,
            last_used_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

def create_user(username: str) -> int:
    """Creates a new user or returns existing user ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, created_at) VALUES (?, ?)", (username, int(time.time())))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = cursor.fetchone()[0]
    finally:
        conn.close()
    return user_id

def generate_key(user_id: int, name: Optional[str] = None) -> str:
    """Generates a new API key for a user and stores its hash."""
    raw_key = secrets.token_urlsafe(32)
    api_key = f"lh_{raw_key}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    prefix = api_key[:7] # lh_ + first few chars of random part
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO api_keys (user_id, key_hash, prefix, name, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, key_hash, prefix, name, int(time.time())))
    conn.commit()
    conn.close()
    
    return api_key

def verify_key(api_key: str) -> Optional[Dict]:
    """Verifies an API key and returns user info if valid."""
    if not api_key:
        return None
    
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, k.id as key_id, k.name as key_name
        FROM users u
        JOIN api_keys k ON u.id = k.user_id
        WHERE k.key_hash = ?
    """, (key_hash,))
    row = cursor.fetchone()
    
    if row:
        user_info = dict(row)
        cursor.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (int(time.time()), user_info['key_id']))
        conn.commit()
        conn.close()
        return user_info
    
    conn.close()
    return None

def get_user_keys(user_id: int) -> List[Dict]:
    """Returns all API keys associated with a user (hashes excluded)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, prefix, name, created_at, last_used_at FROM api_keys WHERE user_id = ?", (user_id,))
    keys = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return keys

# Initialize DB on import
init_db()
