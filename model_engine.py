"""
SmartAI - AI Model Engine
High-performance inference powered by Groq API (e.g. Llama 3.3 70B Versatile).
Includes real-time clock handling, greetings, and multi-turn conversational context.
Designed for serverless Vercel deployment with zero local model weights.
"""

import logging
import threading
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartAI.ModelEngine")


class ModelEngine:
    """Manages AI conversation and response generation via Groq API."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelEngine, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.model_type = "groq"
        self.model_name = Config.GROQ_MODEL
        self.api_key = Config.GROQ_API_KEY

        self.is_loading = False
        self.is_loaded = False
        self.load_error = None
        self.client: Optional[Any] = None

        self._load_lock = threading.Lock()

        # Initialize Groq client if key is configured
        if self.api_key and GROQ_AVAILABLE:
            try:
                self.client = Groq(api_key=self.api_key)
                self.is_loaded = True
                logger.info(f"SmartAI initialized with Groq API: {self.model_name}")
            except Exception as e:
                self.load_error = str(e)
                logger.error(f"Failed to initialize Groq client: {e}")
        elif not self.api_key:
            self.load_error = "GROQ_API_KEY is not configured in environment variables."
            logger.warning("GROQ_API_KEY is missing. Model engine is standing by.")

        self._initialized = True

    # =========================================
    # CHECK / INITIALIZE GROQ CLIENT
    # =========================================

    def load_model(self) -> bool:
        """Verifies or re-initializes the Groq client connection."""
        if self.is_loaded and self.client is not None:
            return True

        with self._load_lock:
            # Re-read key in case it was set dynamically
            self.api_key = Config.GROQ_API_KEY
            self.model_name = Config.GROQ_MODEL

            if not GROQ_AVAILABLE:
                self.load_error = "groq Python package is not installed."
                self.is_loaded = False
                return False

            if not self.api_key:
                self.load_error = "GROQ_API_KEY is not configured in environment."
                self.is_loaded = False
                return False

            try:
                self.client = Groq(api_key=self.api_key)
                self.is_loaded = True
                self.load_error = None
                logger.info(f"Groq API connection established: {self.model_name}")
                return True
            except Exception as e:
                self.load_error = str(e)
                self.is_loaded = False
                logger.error(f"Failed to connect to Groq API: {e}", exc_info=True)
                return False

    # =========================================
    # REAL-TIME TIME HANDLER (INDIA / IST)
    # =========================================

    def handle_time_question(self, message: str) -> Optional[str]:
        text = message.lower().strip()

        time_patterns = [
            r"\bwhat(?:'s| is) the time\b",
            r"\bwhat time is it\b",
            r"\btime now\b",
            r"\bcurrent time\b",
            r"\btell me the time\b",
            r"\bwhat is the current time\b",
            r"\bcan you tell me the time\b",
            r"\bwhat time now\b"
        ]

        if any(re.search(pattern, text) for pattern in time_patterns):
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(ist)
            return (
                f"The current time is "
                f"{now.strftime('%I:%M:%S %p')} IST. "
                f"Today is {now.strftime('%d %B %Y')}."
            )

        return None

    # =========================================
    # GREETING HANDLER
    # =========================================

    def handle_greeting(self, message: str) -> Optional[str]:
        text = message.lower().strip()

        for char in ["!", ".", ",", "?", "😊", "👋"]:
            text = text.replace(char, "")

        text = " ".join(text.split())

        if any(x in text for x in [
            "how are you",
            "how are u",
            "how r you",
            "how r u",
            "how are you doing"
        ]):
            return "I'm doing great, thanks for asking! 😊 How are you?"

        if "good morning" in text:
            return "Good morning! ☀️ Hope you have a wonderful day!"

        if "good afternoon" in text:
            return "Good afternoon! 😊 How is your day going?"

        if "good evening" in text:
            return "Good evening! 🌆 What are you up to?"

        if "good night" in text:
            return "Good night! 🌙 Sleep well!"

        if any(x in text for x in ["what are you doing", "what are u doing"]):
            return "I'm here chatting with you! 😊 What are you doing?"

        if any(x in text for x in ["who are you", "what is your name"]):
            return "I'm SmartAI, your personal AI assistant! 😊 I'm here to help you."

        if "can you help me" in text:
            return "Of course! 😊 Tell me what you need help with."

        greeting_words = ["hi", "hii", "hiii", "hello", "hey", "heyy", "heyyy"]
        if text in greeting_words:
            return "Heyy! 😊 How are you doing?"

        return None

    # =========================================
    # BUILD PROMPT MESSAGES
    # =========================================

    def build_prompt_messages(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": Config.SYSTEM_PROMPT
            }
        ]

        # Use recent turns for conversational context
        recent_history = conversation_history[-12:]

        for msg in recent_history:
            sender = msg.get("sender") or msg.get("role", "user")
            role = "user" if sender == "user" else "assistant"
            content = msg.get("content", "").strip()

            if content:
                messages.append({
                    "role": role,
                    "content": content
                })

        return messages

    # =========================================
    # GENERATE GROQ API RESPONSE
    # =========================================

    def generate_groq_response(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        if not self.is_loaded or self.client is None:
            success = self.load_model()
            if not success or self.client is None:
                raise RuntimeError(
                    f"Groq API unavailable: {self.load_error or 'GROQ_API_KEY is not set.'}"
                )

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=Config.TEMPERATURE,
                top_p=Config.TOP_P,
                max_tokens=Config.MAX_NEW_TOKENS
            )

            answer = completion.choices[0].message.content
            if answer:
                return answer.strip()

            return "Sorry, I couldn't generate a response. Please try again."

        except Exception as e:
            logger.error(f"Groq API response generation failed: {e}", exc_info=True)
            raise RuntimeError(f"Could not generate response via Groq API: {e}")

    # =========================================
    # MAIN RESPONSE FUNCTION
    # =========================================

    def generate_response(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        if not conversation_history:
            return "Hello! How can I help you today?"

        last_user_message = ""
        for msg in reversed(conversation_history):
            sender = msg.get("sender") or msg.get("role", "")
            if sender == "user":
                last_user_message = msg.get("content", "").strip()
                break

        # 1. Real-time clock questions
        time_reply = self.handle_time_question(last_user_message)
        if time_reply:
            return time_reply

        # 2. Common greetings
        greeting_reply = self.handle_greeting(last_user_message)
        if greeting_reply:
            return greeting_reply

        # 3. LLM generation via Groq API
        messages = self.build_prompt_messages(conversation_history)
        return self.generate_groq_response(messages)

    # =========================================
    # MODEL STATUS
    # =========================================

    def get_status(self) -> Dict[str, Any]:
        return {
            "model_type": self.model_type,
            "model_name": self.model_name,
            "is_loaded": bool(self.client is not None or self.api_key),
            "is_loading": False,
            "device": "Groq Cloud",
            "load_error": self.load_error
        }


# Global model instance
ai_engine = ModelEngine()
