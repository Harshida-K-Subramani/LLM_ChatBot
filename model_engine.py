"""
SmartAI - AI Model Engine
High-performance inference powered exclusively by a remote, always-on Cloud Ollama server
running Qwen 2.5 3B (qwen2.5:3b).
Includes real-time clock handling, greetings, and multi-turn conversational context.
Communicates via remote HTTP API (/api/chat) with bearer token authentication.
"""

import logging
import threading
import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartAI.ModelEngine")


class ModelEngine:
    """Manages AI conversation and response generation via remote Ollama HTTP API."""

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

        self.model_type = "ollama"
        self.model_name = Config.OLLAMA_MODEL
        self.base_url = Config.OLLAMA_BASE_URL
        self.api_key = Config.OLLAMA_API_KEY

        self.is_loading = False
        self.is_loaded = False
        self.load_error = None

        self._load_lock = threading.Lock()

        if self.base_url:
            logger.info(f"SmartAI configured with remote Ollama server: {self.base_url} (model: {self.model_name})")
            self.is_loaded = True
        else:
            self.load_error = "OLLAMA_BASE_URL is not configured in environment variables."
            logger.warning("OLLAMA_BASE_URL is missing. Model engine is standing by.")

        self._initialized = True

    def _get_headers(self) -> Dict[str, str]:
        """Constructs HTTP headers with optional Bearer authentication."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # =========================================
    # CHECK REMOTE OLLAMA SERVER STATUS
    # =========================================

    def load_model(self) -> bool:
        """Verifies connectivity to the remote Ollama server."""
        with self._load_lock:
            # Re-read configuration in case environment changed dynamically
            if Config.OLLAMA_BASE_URL:
                self.base_url = Config.OLLAMA_BASE_URL
            if Config.OLLAMA_API_KEY:
                self.api_key = Config.OLLAMA_API_KEY
            if Config.OLLAMA_MODEL:
                self.model_name = Config.OLLAMA_MODEL

            if not self.base_url:
                self.load_error = "OLLAMA_BASE_URL is not configured in environment variables."
                self.is_loaded = False
                return False

            try:
                # Probe remote Ollama server tags endpoint
                probe_url = f"{self.base_url}/api/tags"
                response = requests.get(
                    probe_url,
                    headers=self._get_headers(),
                    timeout=5
                )

                if response.status_code in (401, 403):
                    self.load_error = "Remote Ollama authentication failed. Please verify your OLLAMA_API_KEY."
                    self.is_loaded = False
                    logger.error(self.load_error)
                    return False

                if not response.ok:
                    self.load_error = f"Remote Ollama server returned HTTP {response.status_code} on probe."
                    self.is_loaded = False
                    return False

                self.is_loaded = True
                self.load_error = None
                logger.info(f"Remote Ollama server is reachable and ready: {self.base_url} ({self.model_name})")
                return True

            except requests.exceptions.RequestException as e:
                self.load_error = f"Cannot reach remote Ollama server at {self.base_url}: {e}"
                self.is_loaded = False
                logger.warning(self.load_error)
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
    # GENERATE REMOTE OLLAMA HTTP RESPONSE
    # =========================================

    def generate_ollama_response(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        # Dynamically refresh base url and api key in case set after initialization
        base_url = Config.OLLAMA_BASE_URL or self.base_url
        api_key = Config.OLLAMA_API_KEY or self.api_key
        model_name = Config.OLLAMA_MODEL or self.model_name

        if not base_url:
            raise RuntimeError(
                "OLLAMA_BASE_URL is not configured. Please set OLLAMA_BASE_URL in your environment variables "
                "to point to your remote Ollama cloud server."
            )

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": Config.TEMPERATURE,
                "top_p": Config.TOP_P,
                "repeat_penalty": Config.REPETITION_PENALTY,
                "num_predict": Config.MAX_NEW_TOKENS
            }
        }

        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        chat_url = f"{base_url}/api/chat"

        try:
            response = requests.post(
                chat_url,
                headers=headers,
                json=payload,
                timeout=(5, 60)
            )

            if response.status_code in (401, 403):
                raise RuntimeError("Remote Ollama authentication failed. Please verify your OLLAMA_API_KEY.")

            if response.status_code == 404:
                raise RuntimeError(
                    f"Model '{model_name}' was not found on the remote Ollama server. "
                    f"Please ensure 'ollama pull {model_name}' has been executed on the server."
                )

            if not response.ok:
                err_text = response.text[:200]
                raise RuntimeError(f"Remote Ollama server error (HTTP {response.status_code}): {err_text}")

            data = response.json()
            content = data.get("message", {}).get("content", "")
            if content:
                return content.strip()

            return "Sorry, I could not generate a response. Please try again."

        except requests.exceptions.ConnectTimeout:
            logger.error(f"Connection timeout reaching remote Ollama server at {base_url}")
            raise RuntimeError(
                f"Connection timed out reaching remote Ollama server at {base_url}. "
                "Please verify that the server is online and port/domain is accessible."
            )

        except requests.exceptions.ReadTimeout:
            logger.error(f"Read timeout waiting for response from remote Ollama server at {base_url}")
            raise RuntimeError(
                "Remote Ollama server took too long to generate a response (request read timeout)."
            )

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to remote Ollama server at {base_url}: {e}")
            raise RuntimeError(
                f"Failed to connect to remote Ollama server at {base_url}. "
                "Please ensure the remote Ollama cloud instance is running."
            )

        except Exception as e:
            logger.error(f"Remote Ollama response generation failed: {e}", exc_info=True)
            raise RuntimeError(f"Remote Ollama inference failed: {e}")

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

        # 3. LLM generation via remote Ollama HTTP API
        messages = self.build_prompt_messages(conversation_history)
        return self.generate_ollama_response(messages)

    # =========================================
    # MODEL STATUS
    # =========================================

    def get_status(self) -> Dict[str, Any]:
        base_url = Config.OLLAMA_BASE_URL or self.base_url
        model_name = Config.OLLAMA_MODEL or self.model_name
        return {
            "model_type": self.model_type,
            "model_name": model_name,
            "is_loaded": bool(base_url),
            "is_loading": False,
            "device": "Remote Cloud",
            "load_error": self.load_error
        }


# Global model instance
ai_engine = ModelEngine()
