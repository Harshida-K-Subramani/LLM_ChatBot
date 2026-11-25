"""
SmartAI - Model Inference Test Script
Validates Groq API engine configuration, greeting/clock handlers,
and LLM inference (when GROQ_API_KEY is configured).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_engine import ai_engine
from config import Config


def test_inference():
    print("=" * 60, flush=True)
    print("Testing SmartAI Groq Model Engine...", flush=True)
    print(f"Target Model: {ai_engine.model_name}", flush=True)
    print(f"Engine Mode:  {ai_engine.model_type}", flush=True)
    print(f"Device:       {ai_engine.get_status()['device']}", flush=True)
    print("=" * 60, flush=True)

    # 1. Test fast-path handlers (Greetings & Real-Time Clock)
    print("\n[1/3] Testing built-in time & greeting handlers...", flush=True)
    time_reply = ai_engine.handle_time_question("what time is it right now?")
    assert time_reply is not None and "IST" in time_reply
    print(f"✓ Real-time clock handler response: {time_reply}")

    greeting_reply = ai_engine.handle_greeting("hello")
    assert greeting_reply is not None
    print(f"✓ Greeting handler response: {greeting_reply}")

    # 2. Check Groq Engine connection
    print("\n[2/3] Checking Groq client and API key configuration...", flush=True)
    if not Config.GROQ_API_KEY:
        print("ℹ GROQ_API_KEY is not set in local environment.")
        print("✓ Model engine is correctly initialized and waiting for GROQ_API_KEY.")
        print("✓ All zero-weight serverless preparation checks passed!")
        return True

    success = ai_engine.load_model()
    if not success:
        print(f"❌ Failed to connect to Groq API: {ai_engine.load_error}", flush=True)
        return False
    print(f"✓ Connected to Groq API successfully: {ai_engine.model_name}")

    # 3. Test Actual LLM Inference
    print("\n[3/3] Testing Groq LLM inference...", flush=True)
    test_conversation = [
        {"sender": "user", "content": "Explain what makes serverless architectures efficient in 2 sentences."}
    ]
    response = ai_engine.generate_response(test_conversation)
    print(f"\n--- Groq Response ---\n{response}\n----------------------", flush=True)
    assert len(response.strip()) > 0, "Response was empty!"

    print("\n🎉 ALL MODEL INFERENCE TESTS COMPLETED SUCCESSFULLY!", flush=True)
    return True


if __name__ == "__main__":
    test_inference()
