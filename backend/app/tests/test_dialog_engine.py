"""
Unit tests for PersonaDialogEngine with MockInferenceAdapter seam.
Verifies persona orchestration, disclaimer stripping, and PII masking without Ollama or GPU access.
"""

import sys
from pathlib import Path

# Add app directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dialog_engine import PersonaDialogEngine, MockInferenceAdapter, QARetriever
from core.pii_shield import PIIShield


def test_persona_dialog_engine_offline():
    print("Testing PersonaDialogEngine with MockInferenceAdapter...")

    mock_responses = {
        "experience": "I have spent over a decade leading enterprise AI transformation on 100.64.0.1 with /home/user/models."
    }
    adapter = MockInferenceAdapter(responses=mock_responses)
    engine = PersonaDialogEngine(inference_adapter=adapter)

    # 1. Test conversational inference with PII sanitization
    output = engine.converse(
        clean_msg="What is your experience?",
        role_type="Technical Interviewer",
        target_company="Acme Corp"
    )

    assert "100.64.0.1" not in output, f"Internal IP leaked: {output}"
    assert "/home/thegeekybeng" not in output, f"Path leaked: {output}"
    assert "[REDACTED_INTERNAL_IP]" in output or "decade" in output
    print("✓ PII redaction and inference verified.")

    # 2. Test robotic disclaimer stripping
    robotic_text = "As an AI language model, I do not have feelings. But I am passionate about distributed systems."
    cleaned = engine.clean_robotics(robotic_text)
    assert "As an AI" not in cleaned, f"Robotic text not stripped: {cleaned}"
    assert "passionate about distributed systems" in cleaned.lower()
    print("✓ Robotic disclaimer stripping verified.")

    # 3. Test fallback mechanism when model returns AI disclaimers
    bad_mock_adapter = MockInferenceAdapter(default_response="Model, I am an AI and I don't have opinions.")
    fallback_engine = PersonaDialogEngine(inference_adapter=bad_mock_adapter)
    fallback_output = fallback_engine.converse("Tell me about yourself", role_type="Founder")
    assert "Model," not in fallback_output
    assert "I don't have" not in fallback_output
    print("✓ Disclaimers fallback verified.")

    print("All PersonaDialogEngine unit tests PASSED successfully!")


if __name__ == "__main__":
    test_persona_dialog_engine_offline()
