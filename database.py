"""
SmartAI - Database Management
Supports Neon PostgreSQL with serverless connection pooling for production (Vercel),
with local SQLite fallback strictly confined to local development environments.
Includes user authentication, conversations, and message history with mandatory user scoping.
"""

import re
import uuid
import sqlite3
import threading
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Any

from werkzeug.security import generate_password_hash, check_password_hash
from config import Config, is_production

logger = logging.getLogger("SmartAI.Database")

# PostgreSQL drivers: support psycopg2 or psycopg3
PSYCOPG2_AVAILABLE = False
PSYCOPG3_AVAILABLE = False

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    ThreadedConnectionPool = None
    RealDictCursor = None

try:
    import psycopg
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    PSYCOPG3_AVAILABLE = True
except ImportError:
    psycopg = None
    ConnectionPool = None
    dict_row = None


def mask_dsn(dsn: str) -> str:
    """Masks database passwords in connection strings for safe logging."""
    if not dsn:
        return ""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", dsn)


def is_postgres() -> bool:
    """
    Returns True if PostgreSQL is explicitly configured OR if running in production/Vercel.
    In production (e.g. Vercel), PostgreSQL is mandatory.
    """
    if Config.DATABASE_URL:
        return True
    if is_production():
        return True
    return False


# =========================================
# CONNECTION POOLING (POSTGRESQL / NEON)
# =========================================

_pg_pool: Optional[Any] = None
_pool_lock = threading.Lock()
_db_initialized = False
_init_lock = threading.Lock()


def get_pg_pool():
    """Returns or initializes the ThreadedConnectionPool for Neon PostgreSQL."""
    global _pg_pool
    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                dsn = Config.DATABASE_URL
                if not dsn:
                    raise RuntimeError(
                        "DATABASE_URL is not set. In production (Vercel), a Neon PostgreSQL connection string "
                        "must be provided via the DATABASE_URL environment variable."
                    )

                if not PSYCOPG2_AVAILABLE:
                    raise RuntimeError(
                        "psycopg2 is required for PostgreSQL connections. "
                        "Ensure psycopg2-binary is installed."
                    )

                masked = mask_dsn(dsn)
                logger.info(f"Initializing Neon PostgreSQL connection pool: {masked}")

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
            try:
                _pg_pool.closeall()
            except Exception as e:
                logger.warning(f"Error closing PostgreSQL connection pool: {e}")
            _pg_pool = None


def get_pg_connection(pool):
    """
    Checks out a live connection from the pool.
    Verifies connection health; if closed or dropped by Neon PgBouncer, discards and reconnects.
    """
    for attempt in range(3):
        conn = None
        try:
            conn = pool.getconn()
            if getattr(conn, "closed", 0) != 0:
                pool.putconn(conn, close=True)
                continue

            # Ping connection to verify it is active on the socket
            with conn.cursor() as probe_cur:
                probe_cur.execute("SELECT 1")
            return conn
        except Exception as e:
            logger.warning(f"Stale PostgreSQL connection discarded (attempt {attempt+1}/3): {e}")
            if conn is not None:
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass

    # If all pooled connections were stale, reset the pool and try once more
    close_pg_pool()
    fresh_pool = get_pg_pool()
    return fresh_pool.getconn()


# =========================================
# UNIFIED DATABASE CONTEXT MANAGER
# =========================================

@contextmanager
def get_db():
    """
    Context manager providing a database cursor.
    Uses Neon PostgreSQL in production or when DATABASE_URL is set.
    SQLite is strictly reserved for local development and blocked in production.
    """
    if is_postgres():
        db_url = Config.DATABASE_URL
        if not db_url:
            raise RuntimeError(
                "CRITICAL: Production environment detected (Vercel) but no DATABASE_URL was found. "
                "SQLite is strictly disabled in production. "
                "Please configure DATABASE_URL in your Vercel Project Settings > Environment Variables."
            )

        pool = get_pg_pool()
        conn = get_pg_connection(pool)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                pool.putconn(conn)
            except Exception:
                pass
    else:
        # Local development SQLite mode only
        if is_production():
            raise RuntimeError(
                "CRITICAL: Production environment detected. "
                "Local SQLite database access is strictly prohibited in production."
            )

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
    Executes a query, converting ? placeholders to %s for PostgreSQL.
    """
    if is_postgres():
        pg_query = query.replace("?", "%s")
        cursor.execute(pg_query, params)
    else:
        cursor.execute(query, params)


# =========================================
# DATABASE INITIALIZATION
# =========================================

def init_db() -> None:
    """Initializes tables and indexes for PostgreSQL or SQLite."""
    global _db_initialized

    with get_db() as cursor:
        if is_postgres():
            # Neon PostgreSQL DDL
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
                    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE
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
            # Local SQLite DDL
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
                    user_id TEXT NOT NULL,
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

    _db_initialized = True


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

    integrity_errors = [sqlite3.IntegrityError]
    if PSYCOPG2_AVAILABLE and psycopg2 is not None:
        integrity_errors.append(psycopg2.IntegrityError)
    if PSYCOPG3_AVAILABLE and psycopg is not None:
        integrity_errors.append(psycopg.IntegrityError)

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
        except tuple(integrity_errors):
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
            "SELECT id, name, email, password, created_at FROM users WHERE email = ?",
            (email.strip().lower(),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    clean_id = (user_id or "").strip()
    if not clean_id:
        return None

    with get_db() as cursor:
        db_execute(cursor, """
            SELECT id, name, email, created_at
            FROM users
            WHERE id = ?
        """, (clean_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# =========================================
# PASSWORD VERIFICATION
# =========================================

def verify_password(password: str, hashed_password: str) -> bool:
    return check_password_hash(hashed_password, password)


# =========================================
# CREATE CONVERSATION (MANDATORY user_id)
# =========================================

def create_conversation(
    title: str = "New Chat",
    user_id: str = ""
) -> Dict[str, Any]:
    clean_user_id = (user_id or "").strip()
    if not clean_user_id:
        raise ValueError("user_id is mandatory to create a conversation.")

    clean_title = (title or "New Chat").strip() or "New Chat"
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        db_execute(cursor, """
            INSERT INTO conversations
            (id, title, created_at, updated_at, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            conv_id,
            clean_title,
            now,
            now,
            clean_user_id
        ))

    return {
        "id": conv_id,
        "title": clean_title,
        "created_at": now,
        "updated_at": now,
        "user_id": clean_user_id,
        "messages": []
    }


# =========================================
# LIST CONVERSATIONS (MANDATORY user_id)
# =========================================

def get_conversations(
    user_id: str
) -> List[Dict[str, Any]]:
    clean_user_id = (user_id or "").strip()
    if not clean_user_id:
        raise ValueError("user_id is mandatory to retrieve conversations.")

    with get_db() as cursor:
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
        """, (clean_user_id,))

        rows = cursor.fetchall() or []
        result = []
        for row in rows:
            d = dict(row)
            d["message_count"] = int(d.get("message_count") or 0)
            result.append(d)
        return result


# =========================================
# GET SINGLE CONVERSATION (MANDATORY user_id)
# =========================================

def get_conversation(
    conv_id: str,
    user_id: str
) -> Optional[Dict[str, Any]]:
    clean_conv_id = (conv_id or "").strip()
    clean_user_id = (user_id or "").strip()
    if not clean_user_id:
        raise ValueError("user_id is mandatory to retrieve a conversation.")
    if not clean_conv_id:
        return None

    with get_db() as cursor:
        db_execute(cursor, """
            SELECT id, title, created_at, updated_at, user_id
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (clean_conv_id, clean_user_id))

        conv_row = cursor.fetchone()
        if not conv_row:
            return None

        conv = dict(conv_row)

        db_execute(cursor, """
            SELECT id, conversation_id, sender, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (clean_conv_id,))

        conv["messages"] = [
            dict(row) for row in (cursor.fetchall() or [])
        ]
        return conv


# =========================================
# UPDATE CONVERSATION TITLE (MANDATORY user_id)
# =========================================

def update_conversation_title(
    conv_id: str,
    title: str,
    user_id: str
) -> bool:
    clean_conv_id = (conv_id or "").strip()
    clean_title = (title or "").strip()
    clean_user_id = (user_id or "").strip()

    if not clean_user_id:
        raise ValueError("user_id is mandatory to update conversation title.")
    if not clean_conv_id or not clean_title:
        return False

    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        db_execute(cursor, """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
        """, (clean_title, now, clean_conv_id, clean_user_id))

        return cursor.rowcount > 0


# =========================================
# DELETE CONVERSATION (MANDATORY user_id)
# =========================================

def delete_conversation(
    conv_id: str,
    user_id: str
) -> bool:
    clean_conv_id = (conv_id or "").strip()
    clean_user_id = (user_id or "").strip()

    if not clean_user_id:
        raise ValueError("user_id is mandatory to delete a conversation.")
    if not clean_conv_id:
        return False

    with get_db() as cursor:
        db_execute(cursor, """
            DELETE FROM conversations
            WHERE id = ? AND user_id = ?
        """, (clean_conv_id, clean_user_id))

        return cursor.rowcount > 0


# =========================================
# CLEAR CONVERSATION MESSAGES (MANDATORY user_id)
# =========================================

def clear_conversation_messages(
    conv_id: str,
    user_id: str
) -> bool:
    clean_conv_id = (conv_id or "").strip()
    clean_user_id = (user_id or "").strip()

    if not clean_user_id:
        raise ValueError("user_id is mandatory to clear conversation messages.")
    if not clean_conv_id:
        return False

    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        db_execute(cursor, """
            DELETE FROM messages
            WHERE conversation_id = ?
            AND EXISTS (
                SELECT 1 FROM conversations
                WHERE id = ? AND user_id = ?
            )
        """, (clean_conv_id, clean_conv_id, clean_user_id))

        db_execute(cursor, """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ? AND user_id = ?
        """, (now, clean_conv_id, clean_user_id))

        return cursor.rowcount > 0


# =========================================
# ADD MESSAGE
# =========================================

def add_message(
    conv_id: str,
    sender: str,
    content: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    clean_conv_id = (conv_id or "").strip()
    if not clean_conv_id:
        raise ValueError("conv_id is required to add message.")

    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    with get_db() as cursor:
        if user_id:
            clean_user_id = user_id.strip()
            db_execute(cursor, """
                SELECT 1 FROM conversations WHERE id = ? AND user_id = ?
            """, (clean_conv_id, clean_user_id))
            if not cursor.fetchone():
                raise PermissionError("Access denied: Conversation does not belong to user.")

        db_execute(cursor, """
            INSERT INTO messages
            (id, conversation_id, sender, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            msg_id,
            clean_conv_id,
            sender,
            content,
            now
        ))

        db_execute(cursor, """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
        """, (now, clean_conv_id))

    return {
        "id": msg_id,
        "conversation_id": clean_conv_id,
        "sender": sender,
        "content": content,
        "created_at": now
    }


# =========================================
# DELETE LAST ASSISTANT MESSAGE (MANDATORY user_id)
# =========================================

def delete_last_assistant_message(
    conv_id: str,
    user_id: str
) -> Optional[Dict[str, Any]]:
    clean_conv_id = (conv_id or "").strip()
    clean_user_id = (user_id or "").strip()

    if not clean_user_id:
        raise ValueError("user_id is mandatory to delete assistant message.")
    if not clean_conv_id:
        return None

    with get_db() as cursor:
        # First verify ownership
        db_execute(cursor, """
            SELECT 1 FROM conversations WHERE id = ? AND user_id = ?
        """, (clean_conv_id, clean_user_id))
        if not cursor.fetchone():
            return None

        db_execute(cursor, """
            SELECT id, content
            FROM messages
            WHERE conversation_id = ? AND sender = 'assistant'
            ORDER BY created_at DESC
            LIMIT 1
        """, (clean_conv_id,))

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
    clean_conv_id = (conv_id or "").strip()
    clean_user_id = (user_id or "").strip()
    if not clean_conv_id or not clean_user_id:
        return False

    with get_db() as cursor:
        db_execute(
            cursor,
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (clean_conv_id, clean_user_id)
        )
        return cursor.fetchone() is not None
