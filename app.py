"""
SmartAI - Flask Backend Application
Connects frontend, Neon PostgreSQL / SQLite database and Remote Ollama LLM engine.
Features complete user authentication, session security,
user-isolated conversation history, and protected chat endpoints.
Optimized for serverless deployment on Vercel.
"""

import os
import re
import logging
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS

from config import Config
import database
from model_engine import ai_engine

BASE_DIR = Path(__file__).resolve().parent

# -----------------------------
# Initialize Flask Application
# -----------------------------

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static"
)
app.config.from_object(Config)

CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartAI.App")


# -----------------------------
# Initialize Database
# -----------------------------

with app.app_context():
    try:
        database.init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database auto-initialization deferred or failed: {e}")


# -----------------------------
# Authentication Decorator
# -----------------------------

def login_required(f):
    """Protects API endpoints, ensuring user is authenticated via session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in."
            }), 401
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------
# Page Routes
# -----------------------------

@app.route("/")
def index():
    """Renders the main chat interface if authenticated; otherwise redirects to login."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/login")
def login():
    """Renders the login/signup authentication page."""
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("auth.html", mode="login")


@app.route("/signup")
def signup():
    """Renders the signup page."""
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("auth.html", mode="signup")


@app.route("/logout")
def logout_page():
    """Clears the session and redirects to login."""
    session.clear()
    return redirect(url_for("login"))


# -----------------------------
# Authentication API Endpoints
# -----------------------------

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    """Registers a new user and establishes a session."""
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")

        # Form validations
        if not name:
            return jsonify({"success": False, "error": "Full Name is required."}), 400

        if len(name) < 2:
            return jsonify({"success": False, "error": "Name must be at least 2 characters long."}), 400

        if not email or not EMAIL_REGEX.match(email):
            return jsonify({"success": False, "error": "Please enter a valid email address."}), 400

        if not password:
            return jsonify({"success": False, "error": "Password is required."}), 400

        if len(password) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters long."}), 400

        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match."}), 400

        # Check existing user
        existing_user = database.get_user_by_email(email)
        if existing_user:
            return jsonify({"success": False, "error": "An account with this email already exists."}), 409

        # Create user in database
        user = database.create_user(name=name, email=email, password=password)

        # Set session for automatic login
        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        logger.info(f"User registered successfully: {email}")

        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }), 201

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected error occurred during signup."}), 500


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticates existing user with email and password."""
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        remember = bool(data.get("remember", True))

        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required."}), 400

        user = database.get_user_by_email(email)
        if not user or not database.verify_password(password, user["password"]):
            return jsonify({"success": False, "error": "Invalid email or password."}), 401

        # Establish session
        session.permanent = remember
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        logger.info(f"User logged in: {email}")

        return jsonify({
            "success": True,
            "message": "Login successful!",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected error occurred during login."}), 500


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Logs out current user by clearing session."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Returns currently authenticated user profile."""
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    user = database.get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return jsonify({"success": False, "error": "User account no longer exists."}), 401

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }), 200


# -----------------------------
# Health Check
# -----------------------------

@app.route("/api/health", methods=["GET"])
def health():
    status = ai_engine.get_status()
    return jsonify({
        "status": "healthy",
        "engine": status,
        "database": "connected"
    }), 200


# -----------------------------
# List User Conversations
# -----------------------------

@app.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    try:
        user_id = session["user_id"]
        conversations = database.get_conversations(user_id=user_id)

        return jsonify({
            "success": True,
            "conversations": conversations
        }), 200

    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Create Conversation
# -----------------------------

@app.route("/api/conversations", methods=["POST"])
@login_required
def create_conversation():
    try:
        user_id = session["user_id"]
        data = request.get_json(silent=True) or {}
        title = data.get("title", "New Chat").strip() or "New Chat"

        conv = database.create_conversation(title=title, user_id=user_id)

        return jsonify({
            "success": True,
            "conversation": conv
        }), 201

    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Get Conversation Details
# -----------------------------

@app.route("/api/conversations/<conv_id>", methods=["GET"])
@login_required
def get_conversation_details(conv_id):
    try:
        user_id = session["user_id"]
        conv = database.get_conversation(conv_id, user_id=user_id)

        if not conv:
            return jsonify({
                "success": False,
                "error": "Conversation not found or access denied."
            }), 404

        return jsonify({
            "success": True,
            "conversation": conv
        }), 200

    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Delete Conversation
# -----------------------------

@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
@login_required
def delete_conversation(conv_id):
    try:
        user_id = session["user_id"]
        success = database.delete_conversation(conv_id, user_id=user_id)

        if not success:
            return jsonify({
                "success": False,
                "error": "Conversation not found or access denied."
            }), 404

        return jsonify({
            "success": True,
            "message": "Conversation deleted successfully."
        }), 200

    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Clear Conversation Messages
# -----------------------------

@app.route("/api/conversations/<conv_id>/clear", methods=["POST"])
@login_required
def clear_conversation(conv_id):
    try:
        user_id = session["user_id"]
        conv = database.get_conversation(conv_id, user_id=user_id)

        if not conv:
            return jsonify({
                "success": False,
                "error": "Conversation not found or access denied."
            }), 404

        database.clear_conversation_messages(conv_id, user_id=user_id)

        return jsonify({
            "success": True,
            "message": "Conversation cleared successfully."
        }), 200

    except Exception as e:
        logger.error(f"Error clearing conversation: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Rename Conversation
# -----------------------------

@app.route("/api/conversations/<conv_id>/title", methods=["PUT"])
@login_required
def rename_conversation(conv_id):
    try:
        user_id = session["user_id"]
        data = request.get_json(silent=True) or {}
        new_title = data.get("title", "").strip()

        if not new_title:
            return jsonify({
                "success": False,
                "error": "Title cannot be empty."
            }), 400

        success = database.update_conversation_title(conv_id, new_title, user_id=user_id)
        if not success:
            return jsonify({
                "success": False,
                "error": "Conversation not found or access denied."
            }), 404

        return jsonify({
            "success": True,
            "title": new_title
        }), 200

    except Exception as e:
        logger.error(f"Error updating conversation title: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------
# Main Chat API
# -----------------------------

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    try:
        user_id = session["user_id"]
        data = request.get_json(silent=True) or {}

        user_message_text = data.get("message", "").strip()
        conv_id = data.get("conversation_id")

        if not user_message_text:
            return jsonify({
                "success": False,
                "error": "Message cannot be empty."
            }), 400

        # Verify or create conversation with ownership check
        conv = None
        if conv_id:
            conv = database.get_conversation(conv_id, user_id=user_id)
            if not conv:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found or access denied."
                }), 404

        if not conv:
            title = user_message_text[:33]
            if len(user_message_text) > 36:
                title += "..."

            conv = database.create_conversation(title=title, user_id=user_id)
            conv_id = conv["id"]

        elif len(conv.get("messages", [])) == 0:
            title = user_message_text[:33]
            if len(user_message_text) > 36:
                title += "..."

            database.update_conversation_title(conv_id, title, user_id=user_id)

        # Save user message
        user_msg = database.add_message(
            conv_id,
            "user",
            user_message_text,
            user_id=user_id
        )

        # Retrieve conversation history
        updated_conv = database.get_conversation(conv_id, user_id=user_id)
        history = updated_conv.get("messages", [])

        # Generate AI response
        ai_response_text = ai_engine.generate_response(history)

        # Save assistant response
        ai_msg = database.add_message(
            conv_id,
            "assistant",
            ai_response_text,
            user_id=user_id
        )

        return jsonify({
            "success": True,
            "conversation_id": conv_id,
            "title": updated_conv.get("title"),
            "user_message": user_msg,
            "assistant_message": ai_msg
        }), 200

    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Model inference error: {str(e)}"
        }), 500


# -----------------------------
# Regenerate AI Response
# -----------------------------

@app.route("/api/chat/regenerate", methods=["POST"])
@login_required
def regenerate():
    try:
        user_id = session["user_id"]
        data = request.get_json(silent=True) or {}
        conv_id = data.get("conversation_id")

        if not conv_id:
            return jsonify({
                "success": False,
                "error": "conversation_id is required."
            }), 400

        conv = database.get_conversation(conv_id, user_id=user_id)
        if not conv:
            return jsonify({
                "success": False,
                "error": "Conversation not found or access denied."
            }), 404

        messages = conv.get("messages", [])
        if not messages:
            return jsonify({
                "success": False,
                "error": "No messages found in this conversation."
            }), 400

        # Remove last assistant response if present
        if messages[-1]["sender"] == "assistant":
            database.delete_last_assistant_message(conv_id, user_id=user_id)
            messages = messages[:-1]

        if not messages:
            return jsonify({
                "success": False,
                "error": "Cannot regenerate empty conversation."
            }), 400

        # Generate new response
        ai_response_text = ai_engine.generate_response(messages)

        new_ai_msg = database.add_message(
            conv_id,
            "assistant",
            ai_response_text,
            user_id=user_id
        )

        return jsonify({
            "success": True,
            "conversation_id": conv_id,
            "assistant_message": new_ai_msg
        }), 200

    except Exception as e:
        logger.error(f"Regeneration error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# -----------------------------
# Model Status & Verification
# -----------------------------

@app.route("/api/model/load", methods=["POST"])
def preload_model():
    """Verifies remote Ollama model server status."""
    success = ai_engine.load_model()
    if success:
        return jsonify({
            "success": True,
            "message": f"Remote Ollama model {ai_engine.model_name} is ready."
        }), 200

    return jsonify({
        "success": False,
        "error": ai_engine.load_error or "Remote Ollama endpoint is not reachable."
    }), 500


# -----------------------------
# Application Startup (Local Development)
# -----------------------------

if __name__ == "__main__":
    logger.info(
        f"Starting SmartAI server at http://{Config.HOST}:{Config.PORT}"
    )

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        use_reloader=Config.DEBUG
    )
