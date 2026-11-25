"""
SmartAI - Database Management
Supports Neon PostgreSQL with serverless connection pooling,
with automatic fallback to SQLite for local development and tests.
Includes user authentication, conversations, and message history.
"""

import sqlite3
import uuid
import threading
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Any

from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

logger = logging.getLogger("SmartAI.Database")

# PostgreSQL dependencies (optional for local SQLite mode)
try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    ThreadedConnectionPool = None
    RealDictCursor = None


# =========================================
# CONNECTION POOLING (POSTGRESQL / NEON)
# =========================================

_pg_pool: Optional[Any] = None
_pool_lock = threading.Lock()


def get_pg_pool():
    """Returns or initializes the ThreadedConnectionPool for Neon PostgreSQL."""
    global _pg_pool
    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                if not PSYCOPG2_AVAILABLE:
                    raise RuntimeError(
                        "psycopg2 is required for PostgreSQL connection. "
                        "Install with: pip install psycopg2-binary"
                    )
                dsn = Config.DATABASE_URL
                if "sslmode=" not in dsn:
                    dsn += ("&" if "?" in dsn else "?") + "sslmode=require"

                logger.info("Initializing Neon PostgreSQL connection pool...")
                _pg_pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=dsn
                )
    return _pg_pool


def close_pg_pool():
    """Closes all connections in the pool."""
    global _pg_pool
    with _pool_lock:
        if _pg_pool is not None:
            _pg_pool.closeall()
            _pg_pool = None


# =========================================
# UNIFIED DATABASE CONTEXT MANAGER
# =========================================

@contextmanager
def get_db():
    """
    Context manager providing a database cursor.
    Uses Neon PostgreSQL with connection pooling if Config.DATABASE_URL is set;
    otherwise falls back to SQLite.
    """
    if Config.DATABASE_URL:
        pool = get_pg_pool()
        conn = pool.getconn()
        try:
            if getattr(conn, "closed", 0) != 0:
                conn = pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                pool.putconn(conn)
            except Exception:
                pass
    else:
        conn = sqlite3.connect(
            Config.DATABASE_PATH,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def db_execute(cursor, query: str, params: tuple = ()):
    """
    Executes a query converting ? placeholders to %s for PostgreSQL.
    """
    if Config.DATABASE_URL:
        pg_query = query.replace("?", "%s")
        cursor.execute(pg_query, params)
    else:
        cursor.execute(query, params)


# Backward compatibility for direct connection requests
def get_db_connection():
    if Config.DATABASE_URL:
        pool = get_pg_pool()
        return pool.getconn()
    conn = sqlite3.connect(Config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# =========================================
# DATABASE INITIALIZATION
# =========================================

def init_db() -> None:
    """Initializes tables and indexes for PostgreSQL or SQLite."""
    with get_db() as cursor:
        if Config.DATABASE_URL:
            # PostgreSQL / Neon DDL
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    created_at VARCHAR(64) NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(64) PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR(64) PRIMARY KEY,
                    conversation_id VARCHAR(64) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    sender VARCHAR(32) NOT NULL CHECK(sender IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at VARCHAR(64) NOT NULL
                );
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at);
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations(updated_at DESC);
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id);
            """)
        else:
            # SQLite DDL
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    user_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Migrate user_id column if needed in legacy SQLite tables
            cursor.execute("PRAGMA table_info(conversations)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "user_id" not in columns:
                cursor.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender TEXT NOT NULL CHECK(sender IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations(updated_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id)
            """)


# =========================================
# USER REGISTRATION
# =========================================

def create_user(name: str, email: str, password: str) -> Dict[str, Any]:
    clean_name = name.strip()
    clean_email = email.strip().lower()

    if not clean_name:
        raise ValueError("Name cannot be empty.")

    if not clean_email or "@" not in clean_email:
        raise ValueError("Please provide a valid email address.")

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    hashed_password = generate_password_hash(password)

    integrity_errors = (sqlite3.IntegrityError,)
    if PSYCOPG2_AVAILABLE and psycopg2 is not None:
        integrity_errors = (sqlite3.IntegrityError, psycopg2.IntegrityError)

    with get_db() as cursor:
        try:
            db_execute(cursor, """
                INSERT INTO users
                (id, name, email, password, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                clean_name,
                clean_email,
                hashed_password,
                now
            ))
        except integrity_errors:
            raise ValueError("An account with this email already exists.")

    return {
        "id": user_id,
        "name": clean_name,
        "email": clean_email,
        "created_at": now
    }


# =========================================
# GET USER
# =========================================

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_db() as cursor:
        db_execute(
            cursor,
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as cursor:
        db_execute(cursor, """
            SELECT id, name, email, created_at
            FROM users
            WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# =========================================
# PASSWORD VERIFICATION
# =========================================

def verify_password(password: str, hashed_password: str) -> bool:
    return check_password_hash(hashed_password, password)


# =========================================
# CREATE CONVERSATION
# =========================================

def create_conversation(
    title: str = "New Chat",
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        db_execute(cursor, """
            INSERT INTO conversations
            (id, title, created_at, updated_at, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            conv_id,
            title,
            now,
            now,
            user_id
        ))

    return {
        "id": conv_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "user_id": user_id,
        "messages": []
    }


# =========================================
# LIST CONVERSATIONS
# =========================================

def get_conversations(
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    with get_db() as cursor:
        if user_id:
            db_execute(cursor, """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                    (SELECT content FROM messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at ASC LIMIT 1)
                    AS preview_message,
                    (SELECT COUNT(*) FROM messages
                     WHERE conversation_id = c.id)
                    AS message_count
                FROM conversations c
                WHERE c.user_id = ?
                ORDER BY c.updated_at DESC
            """, (user_id,))
        else:
            db_execute(cursor, """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                    (SELECT content FROM messages
                     WHERE conversation_id = c.id
                     ORDER BY created_at ASC LIMIT 1)
                    AS preview_message,
                    (SELECT COUNT(*) FROM messages
                     WHERE conversation_id = c.id)
                    AS message_count
                FROM conversations c
                ORDER BY c.updated_at DESC
            """)

        return [dict(row) for row in cursor.fetchall()]


# =========================================
# GET SINGLE CONVERSATION
# =========================================

def get_conversation(
    conv_id: str,
    user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    with get_db() as cursor:
        if user_id:
            db_execute(cursor, """
                SELECT * FROM conversations
                WHERE id = ? AND user_id = ?
            """, (conv_id, user_id))
        else:
            db_execute(cursor, """
                SELECT * FROM conversations
                WHERE id = ?
            """, (conv_id,))

        conv_row = cursor.fetchone()
        if not conv_row:
            return None

        conv = dict(conv_row)

        db_execute(cursor, """
            SELECT id, conversation_id, sender, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (conv_id,))

        conv["messages"] = [
            dict(row) for row in cursor.fetchall()
        ]
        return conv


# =========================================
# UPDATE CONVERSATION TITLE
# =========================================

def update_conversation_title(
    conv_id: str,
    title: str,
    user_id: Optional[str] = None
) -> bool:
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        if user_id:
            db_execute(cursor, """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
            """, (title, now, conv_id, user_id))
        else:
            db_execute(cursor, """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (title, now, conv_id))

        return cursor.rowcount > 0


# =========================================
# DELETE CONVERSATION
# =========================================

def delete_conversation(
    conv_id: str,
    user_id: Optional[str] = None
) -> bool:
    with get_db() as cursor:
        if user_id:
            db_execute(cursor, """
                DELETE FROM conversations
                WHERE id = ? AND user_id = ?
            """, (conv_id, user_id))
        else:
            db_execute(cursor, """
                DELETE FROM conversations
                WHERE id = ?
            """, (conv_id,))

        return cursor.rowcount > 0


# =========================================
# CLEAR CONVERSATION MESSAGES
# =========================================

def clear_conversation_messages(
    conv_id: str,
    user_id: Optional[str] = None
) -> bool:
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        if user_id:
            db_execute(cursor, """
                DELETE FROM messages
                WHERE conversation_id = ?
                AND EXISTS (
                    SELECT 1 FROM conversations
                    WHERE id = ? AND user_id = ?
                )
            """, (conv_id, conv_id, user_id))

            db_execute(cursor, """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ? AND user_id = ?
            """, (now, conv_id, user_id))
        else:
            db_execute(cursor, """
                DELETE FROM messages
                WHERE conversation_id = ?
            """, (conv_id,))

            db_execute(cursor, """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
            """, (now, conv_id))

        return cursor.rowcount > 0


# =========================================
# ADD MESSAGE
# =========================================

def add_message(
    conv_id: str,
    sender: str,
    content: str
) -> Dict[str, Any]:
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        db_execute(cursor, """
            INSERT INTO messages
            (id, conversation_id, sender, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            msg_id,
            conv_id,
            sender,
            content,
            now
        ))

        db_execute(cursor, """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
        """, (now, conv_id))

    return {
        "id": msg_id,
        "conversation_id": conv_id,
        "sender": sender,
        "content": content,
        "created_at": now
    }


# =========================================
# DELETE LAST ASSISTANT MESSAGE
# =========================================

def delete_last_assistant_message(
    conv_id: str
) -> Optional[Dict[str, Any]]:
    with get_db() as cursor:
        db_execute(cursor, """
            SELECT id, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (conv_id,))

        last_row = cursor.fetchone()
        if not last_row:
            return None

        last_msg = dict(last_row)

        db_execute(cursor, """
            DELETE FROM messages
            WHERE id = ?
        """, (last_msg["id"],))

        return last_msg


# =========================================
# CHECK CONVERSATION OWNERSHIP
# =========================================

def check_conversation_ownership(
    conv_id: str,
    user_id: str
) -> bool:
    """Verifies that the conversation belongs to the specified user."""
    with get_db() as cursor:
        db_execute(
            cursor,
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id)
        )
        return cursor.fetchone() is not None
