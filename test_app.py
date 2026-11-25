"""
SmartAI - Automated Unit and Integration Tests
Validates database CRUD operations, REST API endpoints, and model engine integration.
"""

import sys
import unittest
import json
import uuid
from pathlib import Path

# Ensure application imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

import database
from app import app
from config import Config


class SmartAITests(unittest.TestCase):
    def setUp(self):
        """Set up test environment, Flask test client, and authenticated test session."""
        app.config["TESTING"] = True
        self.client = app.test_client()
        with app.app_context():
            database.init_db()

        # Create unique user and establish session for authenticated tests
        self.test_email = f"app_tester_{uuid.uuid4().hex[:8]}@example.com"
        self.test_password = "Password123!"
        signup_res = self.client.post("/api/auth/signup", json={
            "name": "App Tester",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password
        })
        self.assertEqual(signup_res.status_code, 201)

    def test_01_database_crud(self):
        """Test database conversation and message CRUD operations."""
        # 1. Create conversation
        conv = database.create_conversation("Test Conversation")
        conv_id = conv["id"]
        self.assertIsNotNone(conv_id)
        self.assertEqual(conv["title"], "Test Conversation")

        # 2. Add user message
        msg1 = database.add_message(conv_id, "user", "Hello SmartAI!")
        self.assertEqual(msg1["sender"], "user")
        self.assertEqual(msg1["content"], "Hello SmartAI!")

        # 3. Add assistant response
        msg2 = database.add_message(conv_id, "assistant", "Hello! How can I assist you today?")
        self.assertEqual(msg2["sender"], "assistant")

        # 4. Fetch conversation details
        fetched = database.get_conversation(conv_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched["messages"]), 2)
        self.assertEqual(fetched["messages"][0]["content"], "Hello SmartAI!")

        # 5. Delete last assistant message (Regenerate simulation)
        deleted = database.delete_last_assistant_message(conv_id)
        self.assertIsNotNone(deleted)
        after_regen = database.get_conversation(conv_id)
        self.assertEqual(len(after_regen["messages"]), 1)

        # 6. Clear conversation messages
        database.clear_conversation_messages(conv_id)
        cleared = database.get_conversation(conv_id)
        self.assertEqual(len(cleared["messages"]), 0)

        # 7. Delete conversation
        del_success = database.delete_conversation(conv_id)
        self.assertTrue(del_success)
        self.assertIsNone(database.get_conversation(conv_id))
        print("✓ Database CRUD tests passed successfully!")

    def test_02_health_endpoint(self):
        """Test /api/health endpoint."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("engine", data)
        self.assertEqual(data["database"], "connected")
        print("✓ /api/health endpoint test passed!")

    def test_03_conversations_api(self):
        """Test authenticated /api/conversations REST endpoints."""
        # Create
        res = self.client.post("/api/conversations", json={"title": "API Test Chat"})
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        conv_id = data["conversation"]["id"]

        # List
        res = self.client.get("/api/conversations")
        self.assertEqual(res.status_code, 200)
        list_data = json.loads(res.data)
        ids = [c["id"] for c in list_data["conversations"]]
        self.assertIn(conv_id, ids)

        # Rename
        res = self.client.put(f"/api/conversations/{conv_id}/title", json={"title": "Updated Title"})
        self.assertEqual(res.status_code, 200)

        # Delete
        res = self.client.delete(f"/api/conversations/{conv_id}")
        self.assertEqual(res.status_code, 200)
        print("✓ Conversations REST API tests passed!")


if __name__ == "__main__":
    unittest.main()
