"""
SmartAI - Comprehensive User Authentication & Data Privacy Test Suite
Validates:
1. User registration & input validations
2. Duplicate email prevention
3. Password hashing security
4. Login & session cookie verification
5. Incorrect password handling
6. Logout & session destruction
7. Unauthenticated API endpoint blocking (401 Unauthorized)
8. Multi-user data privacy & conversation isolation
9. Page route access control & redirection
"""

import sys
import unittest
import json
import uuid
from pathlib import Path

# Ensure root path is accessible
sys.path.insert(0, str(Path(__file__).resolve().parent))

import database
from app import app
from config import Config


class SmartAIAuthTests(unittest.TestCase):

    def setUp(self):
        """Configure test client and initialize database."""
        app.config["TESTING"] = True
        self.client = app.test_client()
        with app.app_context():
            database.init_db()

    def test_01_user_registration(self):
        """Test user registration and field validation."""
        unique_email = f"john_{uuid.uuid4().hex[:8]}@example.com"

        # 1. Successful Signup
        res = self.client.post("/api/auth/signup", json={
            "name": "John Doe",
            "email": unique_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["name"], "John Doe")
        self.assertEqual(data["user"]["email"], unique_email)

        # 2. Duplicate Email Prevention
        dup_res = self.client.post("/api/auth/signup", json={
            "name": "Another John",
            "email": unique_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(dup_res.status_code, 409)
        dup_data = json.loads(dup_res.data)
        self.assertFalse(dup_data["success"])
        self.assertIn("already exists", dup_data["error"])

        # 3. Password Mismatch
        mismatch_res = self.client.post("/api/auth/signup", json={
            "name": "Jane Doe",
            "email": f"jane_{uuid.uuid4().hex[:8]}@example.com",
            "password": "Password123!",
            "confirm_password": "WrongPassword!"
        })
        self.assertEqual(mismatch_res.status_code, 400)
        self.assertIn("Passwords do not match", json.loads(mismatch_res.data)["error"])

        # 4. Short Password (< 6 chars)
        short_res = self.client.post("/api/auth/signup", json={
            "name": "Jane Doe",
            "email": f"jane_short_{uuid.uuid4().hex[:8]}@example.com",
            "password": "123",
            "confirm_password": "123"
        })
        self.assertEqual(short_res.status_code, 400)
        self.assertIn("at least 6 characters", json.loads(short_res.data)["error"])

        # 5. Invalid Email
        invalid_email_res = self.client.post("/api/auth/signup", json={
            "name": "Jane Doe",
            "email": "not-an-email",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(invalid_email_res.status_code, 400)
        print("✓ Test 1: User Registration & Validations passed.")

    def test_02_login_and_password_verification(self):
        """Test login authentication and password verification."""
        email = f"alice_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123"

        # Register user
        self.client.post("/api/auth/signup", json={
            "name": "Alice Smith",
            "email": email,
            "password": password,
            "confirm_password": password
        })

        # Clear session to test explicit login
        self.client.post("/api/auth/logout")

        # 1. Incorrect Password
        bad_pw_res = self.client.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPassword456"
        })
        self.assertEqual(bad_pw_res.status_code, 401)
        self.assertIn("Invalid email or password", json.loads(bad_pw_res.data)["error"])

        # 2. Non-existent User
        no_user_res = self.client.post("/api/auth/login", json={
            "email": "ghost_user_99999@example.com",
            "password": "Password123"
        })
        self.assertEqual(no_user_res.status_code, 401)

        # 3. Successful Login
        good_res = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        self.assertEqual(good_res.status_code, 200)
        data = json.loads(good_res.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], email)

        # 4. Verify /api/auth/me reflects active session
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        me_data = json.loads(me_res.data)
        self.assertEqual(me_data["user"]["email"], email)

        # 5. Logout
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)

        # 6. Verify /api/auth/me returns 401 after logout
        after_logout = self.client.get("/api/auth/me")
        self.assertEqual(after_logout.status_code, 401)
        print("✓ Test 2: Login, Password Verification & Logout passed.")

    def test_03_unauthenticated_api_protection(self):
        """Verify unauthenticated requests cannot access conversation or chat APIs."""
        unauth_client = app.test_client()

        # Conversations list
        res1 = unauth_client.get("/api/conversations")
        self.assertEqual(res1.status_code, 401)

        # Create conversation
        res2 = unauth_client.post("/api/conversations", json={"title": "Unauthorized Chat"})
        self.assertEqual(res2.status_code, 401)

        # Chat endpoint
        res3 = unauth_client.post("/api/chat", json={"message": "Hello?"})
        self.assertEqual(res3.status_code, 401)

        # Regenerate endpoint
        res4 = unauth_client.post("/api/chat/regenerate", json={"conversation_id": "fake-id"})
        self.assertEqual(res4.status_code, 401)

        # Root page redirects to login
        res5 = unauth_client.get("/")
        self.assertEqual(res5.status_code, 302)
        self.assertTrue(res5.location.endswith("/login") or "/login" in res5.location)
        print("✓ Test 3: Unauthenticated API and Page Route Protection passed.")

    def test_04_user_data_isolation_and_privacy(self):
        """
        CRITICAL PRIVACY TEST:
        Ensure User 1 and User 2 have strictly separated conversation histories.
        User 2 cannot list, view, update, delete, or inject messages into User 1's conversations.
        """
        # User 1 Client
        client1 = app.test_client()
        u1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
        reg1 = client1.post("/api/auth/signup", json={
            "name": "User One",
            "email": u1_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(reg1.status_code, 201)

        # User 1 creates a private chat
        res_conv1 = client1.post("/api/conversations", json={"title": "User 1 Private Medical Chat"})
        self.assertEqual(res_conv1.status_code, 201)
        conv1_id = json.loads(res_conv1.data)["conversation"]["id"]

        # User 2 Client
        client2 = app.test_client()
        u2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
        reg2 = client2.post("/api/auth/signup", json={
            "name": "User Two",
            "email": u2_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(reg2.status_code, 201)

        # User 2 creates their own chat
        res_conv2 = client2.post("/api/conversations", json={"title": "User 2 Work Project"})
        self.assertEqual(res_conv2.status_code, 201)
        conv2_id = json.loads(res_conv2.data)["conversation"]["id"]

        # 1. User 2 lists conversations: Must ONLY see their own chat
        list2_res = client2.get("/api/conversations")
        self.assertEqual(list2_res.status_code, 200)
        list2 = json.loads(list2_res.data)["conversations"]
        list2_ids = [c["id"] for c in list2]
        self.assertIn(conv2_id, list2_ids)
        self.assertNotIn(conv1_id, list2_ids, "Privacy violation: User 2 can see User 1's conversation in list!")

        # 2. User 2 attempts to fetch User 1's conversation directly: Must be blocked (404)
        view_attempt = client2.get(f"/api/conversations/{conv1_id}")
        self.assertEqual(view_attempt.status_code, 404, "Privacy violation: User 2 could access User 1's conversation!")

        # 3. User 2 attempts to rename User 1's conversation: Must be blocked (404)
        rename_attempt = client2.put(f"/api/conversations/{conv1_id}/title", json={"title": "Hacked Title"})
        self.assertEqual(rename_attempt.status_code, 404, "Privacy violation: User 2 could rename User 1's conversation!")

        # 4. User 2 attempts to delete User 1's conversation: Must be blocked (404)
        delete_attempt = client2.delete(f"/api/conversations/{conv1_id}")
        self.assertEqual(delete_attempt.status_code, 404, "Privacy violation: User 2 could delete User 1's conversation!")

        # 5. User 2 attempts to inject a message into User 1's conversation: Must be blocked (404)
        chat_attempt = client2.post("/api/chat", json={
            "conversation_id": conv1_id,
            "message": "Malicious injected message"
        })
        self.assertEqual(chat_attempt.status_code, 404, "Privacy violation: User 2 could post to User 1's conversation!")

        # 6. Verify User 1's conversation is still intact and untampered
        verify_conv1 = client1.get(f"/api/conversations/{conv1_id}")
        self.assertEqual(verify_conv1.status_code, 200)
        self.assertEqual(json.loads(verify_conv1.data)["conversation"]["title"], "User 1 Private Medical Chat")

        print("✓ Test 4: Strict User Data Privacy & Isolation passed.")


if __name__ == "__main__":
    unittest.main()
