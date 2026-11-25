"""
SmartAI - Application Configuration
Configuration for Flask, Neon PostgreSQL, and Groq API.
Supports seamless deployment on Vercel serverless environment with strict production safety.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env if present (used in local development)
load_dotenv(BASE_DIR / ".env")


def is_production() -> bool:
    """
    Detects if application is running in a production environment (Vercel, container, or production mode).
    """
    return bool(
        os.getenv("VERCEL") == "1"
        or os.getenv("VERCEL_ENV") in ("production", "preview")
        or os.getenv("FLASK_ENV") == "production"
        or os.getenv("ENV") == "production"
        or os.getenv("ENVIRONMENT") == "production"
    )


def normalize_database_url(url: str) -> str:
    """
    Normalizes PostgreSQL connection URL for psycopg/psycopg2 and Neon compatibility:
    - Replaces 'postgres://' with 'postgresql://'
    - Ensures 'sslmode=require' is present for secure Neon connections.
    """
    if not url:
        return ""
    clean_url = url.strip()
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)

    if "sslmode=" not in clean_url:
        clean_url += ("&" if "?" in clean_url else "?") + "sslmode=require"

    return clean_url


def get_database_url() -> str:
    """
    Retrieves and normalizes the PostgreSQL database URL from environment variables.
    Checks standard DATABASE_URL as well as Vercel/Neon integration variables (POSTGRES_URL, etc.).
    """
    raw_url = (
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("POSTGRES_URL", "").strip()
        or os.getenv("POSTGRES_PRISMA_URL", "").strip()
        or os.getenv("POSTGRES_URL_NON_POOLING", "").strip()
    )
    return normalize_database_url(raw_url)


class ConfigMeta(type):
    """Metaclass allowing dynamic property access on the Config class."""
    @property
    def DATABASE_URL(cls) -> str:
        return get_database_url()

    @property
    def IS_PRODUCTION(cls) -> bool:
        return is_production()


class Config(metaclass=ConfigMeta):
    """SmartAI application configuration."""

    # Flask settings
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "smartai-dev-secret-key-change-later"
    )
    if is_production() and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is required in production")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1" and not is_production()

    # Session Security settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = is_production() or os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Local SQLite database path (used ONLY for local development)
    DATABASE_PATH = str(BASE_DIR / "smartai.db")

    # AI Model settings - Groq API
    MODEL_TYPE = "groq"
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

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
