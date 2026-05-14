import sqlite3
import secrets
import hashlib
import time
import json
from pathlib import Path
from typing import Optional, List, Dict

DB_PATH = Path(__file__).parent / "lahuta.db"

def init_db():
    """Initializes the SQLite database for auth and tasks."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Auth tables
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
    
    # Task tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT NOT NULL,
            output_schema TEXT, -- JSON string
            created_at INTEGER NOT NULL
        )
    """)
    
    # Feedback table (for RLHF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            user_id INTEGER,
            session_id TEXT,
            input_data TEXT NOT NULL,
            model_output TEXT NOT NULL,
            rating TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

# --- Auth Functions ---

def create_user(username: str) -> int:
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
    raw_key = secrets.token_urlsafe(32)
    api_key = f"lh_{raw_key}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    prefix = api_key[:7]
    
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
    if not api_key: return None
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

# --- Task Functions ---

def upsert_task(task_id: str, name: str, system_prompt: str, description: str = None, output_schema: dict = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    schema_json = json.dumps(output_schema) if output_schema else None
    cursor.execute("""
        INSERT INTO tasks (id, name, description, system_prompt, output_schema, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            description=excluded.description,
            system_prompt=excluded.system_prompt,
            output_schema=excluded.output_schema
    """, (task_id, name, description, system_prompt, schema_json, int(time.time())))
    conn.commit()
    conn.close()

def get_task(task_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        task = dict(row)
        if task['output_schema']:
            task['output_schema'] = json.loads(task['output_schema'])
        return task
    return None

def list_tasks() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, system_prompt, output_schema, created_at FROM tasks")

    rows = []
    for r in cursor.fetchall():
        task = dict(r)
        if task['output_schema']:
            try:
                task['output_schema'] = json.loads(task['output_schema'])
            except:
                pass
        rows.append(task)
    conn.close()
    return rows


def delete_task(task_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# --- Feedback Functions ---

def save_feedback(task_id: str, input_data: dict, model_output: dict, rating: str, user_id: int = None, session_id: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (task_id, user_id, session_id, input_data, model_output, rating, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, user_id, session_id, json.dumps(input_data), json.dumps(model_output), rating, int(time.time())))
    conn.commit()
    conn.close()

def get_feedback_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, rating, COUNT(*) FROM feedback GROUP BY task_id, rating")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Initialize on import
init_db()
