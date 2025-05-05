# core/db_manager.py
import sqlite3
import datetime
import os
from pathlib import Path
from .config_manager import get_config_dir # Reuse config dir logic

DB_FILE = "chat_history.db"

def get_db_path():
    """Gets the full path to the database file."""
    # Store DB alongside config in the AppDataLocation
    return get_config_dir() / DB_FILE

def initialize_db():
    """Creates the database and table if they don't exist."""
    db_path = get_db_path()
    conn = None
    created = False
    if not db_path.parent.exists():
         db_path.parent.mkdir(parents=True, exist_ok=True)
         print(f"Created directory for database: {db_path.parent}")

    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        cursor = conn.cursor()
        # Check if table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if cursor.fetchone() is None:
            cursor.execute('''
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT NOT NULL CHECK(role IN ('user', 'model', 'system')), -- Add check constraint
                    content TEXT NOT NULL,
                    model_used TEXT -- Store which model generated the response
                )
            ''')
            conn.commit()
            print(f"Database table 'messages' created in: {db_path}")
            created = True
        else:
             # print(f"Database table 'messages' already exists in: {db_path}") # Optional: Less verbose
             pass


    except sqlite3.Error as e:
        print(f"Database error during initialization: {e} (DB Path: {db_path})")
    finally:
        if conn:
            conn.close()
    # Only print initialized if we actually created the table
    # if created: print(f"Database initialized at: {db_path}")


def add_message(role, content, model_used=None):
    """Adds a message to the history."""
    db_path = get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (timestamp, role, content, model_used) VALUES (?, ?, ?, ?)",
            (datetime.datetime.now(), role, content, model_used) # Insert current timestamp explicitly
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error adding message: {e}")
    finally:
        if conn:
            conn.close()

def get_history(limit=100):
    """Retrieves the chat history, oldest first for processing, limited count."""
    db_path = get_db_path()
    conn = None
    messages = []
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # Make sure connection uses TEXT factory that handles UTF-8 correctly
        conn.text_factory = str
        cursor = conn.cursor()
        # Fetch most recent 'limit' messages
        cursor.execute(
            "SELECT timestamp, role, content, model_used FROM messages ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        # Fetch all results and then reverse in Python to get chronological order
        messages = cursor.fetchall()[::-1] # Reverse the list
        return messages
    except sqlite3.Error as e:
        print(f"Database error getting history: {e}")
        return [] # Return empty list on error
    finally:
        if conn:
            conn.close()


def clear_history():
    """Deletes all messages from the history."""
    db_path = get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        # Optional: Reset autoincrement counter
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='messages';")
        conn.commit()
        print("Chat history cleared.")
        return True
    except sqlite3.Error as e:
        print(f"Database error clearing history: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Initialize DB on module import (ensures table exists when app starts)
# Suppress output unless table is actually created
initialize_db()

