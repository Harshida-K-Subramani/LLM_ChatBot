"""
SmartAI - Production Database & PostgreSQL Compliance Test Suite
Validates that:
1. In production (Vercel), SQLite is strictly forbidden and blocked.
2. In production without DATABASE_URL, clear configuration errors are raised (no SQLite file operations).
3. Database queries, schemas, and parameter conversions are 100% PostgreSQL compliant.
4. User authentication, password hashing, sessions, and chat history CRUD work seamlessly.
"""

import os
import unittest
import uuid
import database
from config import Config, normalize_database_url, get_database_url


class ProductionDatabaseComplianceTests(unittest.TestCase):

    def setUp(self):
        # Save original environment state
        self.orig_env = {
            "VERCEL": os.environ.get("VERCEL"),
            "VERCEL_ENV": os.environ.get("VERCEL_ENV"),
            "FLASK_ENV": os.environ.get("FLASK_ENV"),
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "POSTGRES_URL": os.environ.get("POSTGRES_URL"),
        }

    def tearDown(self):
        # Restore original environment state
        for key, val in self.orig_env.items():
            if val is not None:
                os.environ[key] = val
            elif key in os.environ:
                del os.environ[key]
        database.close_pg_pool()

    def test_01_url_normalization(self):
        """Test URL normalization handles postgres:// and enforces sslmode=require."""
        # Standard postgres:// conversion
        url = "postgres://user:pass@ep-cool.neon.tech/neondb"
        norm = normalize_database_url(url)
        self.assertTrue(norm.startswith("postgresql://"))
        self.assertIn("sslmode=require", norm)

        # Already postgresql://
        url2 = "postgresql://user:pass@ep-cool.neon.tech/neondb?sslmode=require"
        norm2 = normalize_database_url(url2)
        self.assertEqual(norm2.count("sslmode=require"), 1)

        # Existing query params without sslmode
        url3 = "postgresql://user:pass@ep-cool.neon.tech/neondb?channel_binding=disable"
        norm3 = normalize_database_url(url3)
        self.assertIn("&sslmode=require", norm3)

    def test_02_detects_vercel_postgres_url(self):
        """Test detection of Neon integration variable POSTGRES_URL."""
        os.environ["DATABASE_URL"] = ""
        os.environ["POSTGRES_URL"] = "postgres://user:pass@ep-test.neon.tech/neondb"
        url = get_database_url()
        self.assertTrue(url.startswith("postgresql://"))
        self.assertIn("sslmode=require", url)

    def test_03_production_blocks_sqlite_without_database_url(self):
        """CRITICAL: In production (Vercel), SQLite must NEVER be accessed when DATABASE_URL is missing."""
        os.environ["VERCEL"] = "1"
        os.environ["DATABASE_URL"] = ""
        os.environ["POSTGRES_URL"] = ""

        self.assertTrue(database.is_postgres())
        with self.assertRaises(RuntimeError) as ctx:
            with database.get_db():
                pass
        self.assertIn("Production environment detected", str(ctx.exception))
        self.assertIn("SQLite is strictly disabled", str(ctx.exception))

    def test_04_query_placeholders_converted_for_postgres(self):
        """Verify ? placeholders are converted to %s when executing PostgreSQL queries."""
        class MockCursor:
            def __init__(self):
                self.executed_query = ""
                self.executed_params = None

            def execute(self, query, params=()):
                self.executed_query = query
                self.executed_params = params

        mock_cur = MockCursor()

        # Simulate postgres mode
        os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test?sslmode=require"
        database.db_execute(
            mock_cur,
            "SELECT * FROM users WHERE email = ? AND id = ?",
            ("test@example.com", "user_123")
        )
        self.assertIn("%s", mock_cur.executed_query)
        self.assertNotIn("?", mock_cur.executed_query)
        self.assertEqual(mock_cur.executed_params, ("test@example.com", "user_123"))

    def test_05_auth_and_chat_crud_operations(self):
        """Test full user registration, password verification, conversation, and message CRUD."""
        # Ensure local development mode for CRUD validation
        os.environ["VERCEL"] = ""
        os.environ["DATABASE_URL"] = ""
        os.environ["POSTGRES_URL"] = ""

        database.init_db()

        # 1. User Registration
        test_email = f"prod_test_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        user = database.create_user("Prod Tester", test_email, password)
        self.assertIsNotNone(user["id"])
        self.assertEqual(user["email"], test_email)

        # 2. Prevent duplicate email
        with self.assertRaises(ValueError):
            database.create_user("Prod Tester 2", test_email, "AnotherPass123!")

        # 3. Lookup user & verify password
        user_row = database.get_user_by_email(test_email)
        self.assertIsNotNone(user_row)
        self.assertTrue(database.verify_password(password, user_row["password"]))
        self.assertFalse(database.verify_password("WrongPassword!", user_row["password"]))

        # 4. Create Conversation
        conv = database.create_conversation("Neon PostgreSQL Architecture", user_id=user["id"])
        conv_id = conv["id"]
        self.assertIsNotNone(conv_id)
        self.assertTrue(database.check_conversation_ownership(conv_id, user["id"]))

        # 5. Add messages
        msg1 = database.add_message(conv_id, "user", "How does connection pooling work in Neon?")
        msg2 = database.add_message(conv_id, "assistant", "Neon PgBouncer multiplexes connections efficiently.")
        self.assertEqual(msg1["sender"], "user")
        self.assertEqual(msg2["sender"], "assistant")

        # 6. Fetch single conversation
        fetched = database.get_conversation(conv_id, user_id=user["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched["messages"]), 2)

        # 7. List conversations
        convs = database.get_conversations(user_id=user["id"])
        self.assertGreaterEqual(len(convs), 1)
        self.assertEqual(convs[0]["id"], conv_id)
        self.assertEqual(convs[0]["message_count"], 2)

        # 8. Update Title
        updated = database.update_conversation_title(conv_id, "Updated Title", user_id=user["id"])
        self.assertTrue(updated)

        # 9. Delete last assistant message (Regenerate flow)
        deleted_msg = database.delete_last_assistant_message(conv_id, user_id=user["id"])
        self.assertIsNotNone(deleted_msg)
        conv_after_delete = database.get_conversation(conv_id, user_id=user["id"])
        self.assertEqual(len(conv_after_delete["messages"]), 1)

        # 10. Clear messages
        cleared = database.clear_conversation_messages(conv_id, user_id=user["id"])
        self.assertTrue(cleared)
        conv_cleared = database.get_conversation(conv_id, user_id=user["id"])
        self.assertEqual(len(conv_cleared["messages"]), 0)

        # 11. Delete conversation
        del_conv = database.delete_conversation(conv_id, user_id=user["id"])
        self.assertTrue(del_conv)
        self.assertIsNone(database.get_conversation(conv_id, user_id=user["id"]))

    def test_06_mandatory_user_id_scoping(self):
        """CRITICAL: Verify conversation operations reject missing or empty user_id."""
        with self.assertRaises(ValueError):
            database.create_conversation("Invalid Chat", user_id="")

        with self.assertRaises(ValueError):
            database.get_conversations(user_id="")

        with self.assertRaises(ValueError):
            database.get_conversation("dummy_id", user_id="")

        with self.assertRaises(ValueError):
            database.update_conversation_title("dummy_id", "New Title", user_id="")

        with self.assertRaises(ValueError):
            database.delete_conversation("dummy_id", user_id="")

        with self.assertRaises(ValueError):
            database.clear_conversation_messages("dummy_id", user_id="")

        with self.assertRaises(ValueError):
            database.delete_last_assistant_message("dummy_id", user_id="")


if __name__ == "__main__":
    unittest.main()

