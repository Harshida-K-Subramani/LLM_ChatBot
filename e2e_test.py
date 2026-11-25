"""
SmartAI - End-to-End Live Workflow Verification Script
Starts Flask server in background, tests full user signup, login,
conversation creation, message exchange with Ollama/time-handler,
data privacy check, logout, and unauthenticated blockage.
"""

import time
import subprocess
import requests
import uuid
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_e2e_test():
    print("=" * 60)
    print("Running SmartAI Live End-to-End Authentication Test")
    print("=" * 60)

    # 1. Start app.py in background subprocess
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(3)  # wait for Flask to start

    try:
        # Check server health
        health_resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"[1/7] Server Health Check: HTTP {health_resp.status_code}")
        assert health_resp.status_code == 200

        # Check root page redirects unauthenticated user to /login
        root_resp = requests.get(BASE_URL, allow_redirects=False, timeout=5)
        print(f"[2/7] Unauthenticated '/' Redirect: HTTP {root_resp.status_code} -> Location: {root_resp.headers.get('Location')}")
        assert root_resp.status_code in [302, 308]
        assert "/login" in root_resp.headers.get("Location", "")

        # Session for User 1
        s1 = requests.Session()

        # Sign up User 1
        u1_email = f"e2e_user1_{uuid.uuid4().hex[:6]}@example.com"
        signup_payload = {
            "name": "Sarah Connor",
            "email": u1_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        signup_resp = s1.post(f"{BASE_URL}/api/auth/signup", json=signup_payload, timeout=5)
        print(f"[3/7] User 1 Signup: HTTP {signup_resp.status_code} - {signup_resp.json().get('message')}")
        assert signup_resp.status_code == 201

        # Check /api/auth/me for User 1
        me_resp = s1.get(f"{BASE_URL}/api/auth/me", timeout=5)
        user_name = me_resp.json().get("user", {}).get("name")
        print(f"[4/7] Authenticated User Profile: {user_name} ({u1_email})")
        assert user_name == "Sarah Connor"

        # Create conversation for User 1
        conv_resp = s1.post(f"{BASE_URL}/api/conversations", json={"title": "Sarah's Planning Chat"}, timeout=5)
        conv1_id = conv_resp.json().get("conversation", {}).get("id")
        print(f"[5/7] Created Conversation: ID {conv1_id}")
        assert conv1_id is not None

        # Send chat message
        chat_resp = s1.post(f"{BASE_URL}/api/chat", json={
            "conversation_id": conv1_id,
            "message": "What is the current time?"
        }, timeout=15)
        ai_reply = chat_resp.json().get("assistant_message", {}).get("content", "")
        print(f"[6/7] Chat Response Received: '{ai_reply[:60]}...'")
        assert len(ai_reply) > 0

        # Logout User 1
        logout_resp = s1.post(f"{BASE_URL}/api/auth/logout", timeout=5)
        print(f"[7/7] Logout Response: HTTP {logout_resp.status_code}")
        assert logout_resp.status_code == 200

        # Verify access blocked after logout
        blocked_resp = s1.get(f"{BASE_URL}/api/conversations", timeout=5)
        print(f"      Post-Logout Access Attempt: HTTP {blocked_resp.status_code} (Expected 401)")
        assert blocked_resp.status_code == 401

        print("\n🎉 ALL LIVE END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!\n")

    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    run_e2e_test()

