"""
SmartAI - Application Configuration
Configuration for Flask, Neon PostgreSQL, and Groq API.
Supports seamless deployment on Vercel serverless environment.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "smartai.db"

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """SmartAI application configuration."""

    # Flask settings
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "smartai-dev-secret-key-change-later"
    )
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # Session Security settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("FLASK_ENV") == "production"
        or os.getenv("VERCEL") == "1"
        or os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    )
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Database settings - Neon PostgreSQL preferred, SQLite fallback
    raw_db_url = os.getenv("DATABASE_URL", "").strip()
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = raw_db_url
    DATABASE_PATH = str(DATABASE_PATH)

    # AI Model settings - Groq API
    MODEL_TYPE = "groq"
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    # Generation settings
    MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "1024"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    TOP_P = float(os.getenv("TOP_P", "0.9"))
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.1"))

    # SmartAI system instruction
    SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        "You are SmartAI, a friendly, intelligent and helpful AI assistant. "
        "Understand the user's question and answer it directly. "
        "Provide accurate, relevant, high quality and well-structured responses. "
        "Maintain conversational context. "
        "Explain complex topics simply and step-by-step. "
        "When providing code, produce complete, clean and working code with syntax highlighting. "
        "If you do not know the answer or lack verified information, admit it honestly."
    )
