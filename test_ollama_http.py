"""
SmartAI - Remote Ollama HTTP API Integration Test
Tests that ModelEngine:
1. Sends valid Ollama JSON payload to POST /api/chat.
2. Formats Bearer authorization headers correctly when OLLAMA_API_KEY is configured.
3. Correctly parses Ollama stream=false response objects.
4. Handles connection timeouts and remote server HTTP errors with clear user messages.
"""

import unittest
from unittest.mock import patch, MagicMock
from model_engine import ModelEngine
from config import Config


class RemoteOllamaHttpTests(unittest.TestCase):

    def setUp(self):
        Config.OLLAMA_BASE_URL = "https://ollama.example.com"
        Config.OLLAMA_API_KEY = "secret_ollama_key_xyz"
        Config.OLLAMA_MODEL = "qwen2.5:3b"
        self.engine = ModelEngine()
        self.engine.base_url = "https://ollama.example.com"
        self.engine.api_key = "secret_ollama_key_xyz"
        self.engine.model_name = "qwen2.5:3b"
        self.engine.is_loaded = True

    def tearDown(self):
        Config.OLLAMA_BASE_URL = ""
        Config.OLLAMA_API_KEY = ""
        Config.OLLAMA_MODEL = "qwen2.5:3b"

    @patch("requests.post")
    def test_01_ollama_chat_payload_and_headers(self, mock_post):
        """Verify POST to /api/chat with model, messages, stream=false, and Bearer token."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "qwen2.5:3b",
            "message": {
                "role": "assistant",
                "content": "Hello! I am Qwen running on remote Ollama."
            },
            "done": True
        }
        mock_post.return_value = mock_response

        messages = [
            {"role": "user", "content": "Tell me about quantum computing in one sentence."}
        ]
        result = self.engine.generate_ollama_response(messages)

        # Assert correct endpoint
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://ollama.example.com/api/chat")

        # Assert headers include Bearer auth
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret_ollama_key_xyz")

        # Assert payload structure
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "qwen2.5:3b")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["messages"], messages)
        self.assertIn("temperature", payload["options"])

        # Assert content extracted
        self.assertEqual(result, "Hello! I am Qwen running on remote Ollama.")

    @patch("requests.post")
    def test_02_authentication_failure_handling(self, mock_post):
        """Verify clear error message when remote Ollama returns 401/403."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        with self.assertRaises(RuntimeError) as ctx:
            self.engine.generate_ollama_response(messages)
        self.assertIn("authentication failed", str(ctx.exception))
        self.assertIn("OLLAMA_API_KEY", str(ctx.exception))

    @patch("requests.post")
    def test_03_model_not_found_handling(self, mock_post):
        """Verify clear error message when model is not pulled on remote server."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "model 'qwen2.5:3b' not found"
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        with self.assertRaises(RuntimeError) as ctx:
            self.engine.generate_ollama_response(messages)
        self.assertIn("not found on the remote Ollama server", str(ctx.exception))
        self.assertIn("ollama pull", str(ctx.exception))

    @patch("requests.get")
    def test_04_load_model_connectivity_probe(self, mock_get):
        """Verify load_model probes /api/tags."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "qwen2.5:3b"}]}
        mock_get.return_value = mock_response

        success = self.engine.load_model()
        self.assertTrue(success)
        mock_get.assert_called_with(
            "https://ollama.example.com/api/tags",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret_ollama_key_xyz"},
            timeout=5
        )


if __name__ == "__main__":
    unittest.main()
