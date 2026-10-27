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

    # 4. Test stripping of role inversion preambles (e.g. As the Senior Technical Architect & Systems Evaluator from Corporate)
    inversion_text = (
        "As the Senior Technical Architect & Systems Evaluator from Corporate, I believe that my approach to systems architecture "
        "should be centered around creating solutions that are both efficient and effective while also ensuring privacy and security."
    )
    cleaned_inversion = engine.clean_robotics(inversion_text)
    assert "As the Senior Technical Architect" not in cleaned_inversion, f"Inversion preamble not stripped: {cleaned_inversion}"
    assert "Corporate" not in cleaned_inversion, f"Corporate leaked in preamble: {cleaned_inversion}"
    assert cleaned_inversion.startswith("I believe that my approach"), f"Cleaned output does not start with first-person: {cleaned_inversion}"
    print("✓ Role inversion preamble stripping verified.")

    # 5. Test conversion of collective/team pronouns into first-person singular solo builder
    team_text = (
        "One of the key principles behind our Agenic AI design philosophy is strong typing. "
        "We ensure that all data flows through secure channels. Our team has experience working with customers. "
        "This allows us to track the flow of data."
    )
    cleaned_team = engine.clean_robotics(team_text)
    assert "our Agenic" not in cleaned_team, f"Collective 'our' not replaced: {cleaned_team}"
    assert "We ensure" not in cleaned_team, f"Collective 'We' not replaced: {cleaned_team}"
    assert "Our team" not in cleaned_team, f"Collective 'Our team' not replaced: {cleaned_team}"
    assert "allows us to" not in cleaned_team, f"Collective 'us' not replaced: {cleaned_team}"
    assert "my Agenic AI design philosophy" in cleaned_team
    assert "I ensure" in cleaned_team
    assert "I have experience" in cleaned_team
    assert "allows me to" in cleaned_team
    print("✓ Collective pronoun conversion to solo first-person verified.")

    # 6. Test system instruction contains solo builder identity and prohibits collective language
    sys_instruction = engine.build_system_instruction(role_type="Technical Interviewer", target_company="Corporate")
    assert "independent solutions architect" in sys_instruction
    assert "one-man army" in sys_instruction
    assert "do not have an engineering team" in sys_instruction
    assert "first-person singular" in sys_instruction
    # 7. Test stripping of echoed context markers (e.g. Ingested Codebase Context / [Repo: ...)
    echoed_text = (
        "I have evolved from full-stack software engineering into enterprise systems architecture.\n\n"
        "Ingested Codebase Context:\n"
        "[Repo: the-perfect-fit | Path: .agents/canonical_facts.yaml]\n"
        "identity:\n"
        "name: \"Andrew Yeo\"\n"
        "contact:\n"
        "\"+65 9123 4567\"\n"
    )
    cleaned_echo = engine.clean_robotics(echoed_text)
    assert "Ingested Codebase Context" not in cleaned_echo, f"Echoed marker not stripped: {cleaned_echo}"
    assert "[Repo:" not in cleaned_echo, f"Repo marker not stripped: {cleaned_echo}"
    assert "canonical_facts" not in cleaned_echo, f"Filename not stripped: {cleaned_echo}"
    assert cleaned_echo == "I have evolved from full-stack software engineering into enterprise systems architecture."
    print("✓ Echoed context marker stripping verified.")

    # 8. Test PII shield phone and email redaction
    pii_sample = "Contact me at +65 9123 4567 or thegeekybeng@gmail.com for details."
    sanitized_pii = PIIShield.sanitize_text(pii_sample)
    assert "+65 9123 4567" not in sanitized_pii
    assert "thegeekybeng@gmail.com" not in sanitized_pii
    assert "[REDACTED_PHONE]" in sanitized_pii
    assert "[REDACTED_EMAIL]" in sanitized_pii
    print("✓ Phone and email PII redaction verified.")

    print("All PersonaDialogEngine unit tests PASSED successfully!")


if __name__ == "__main__":
    test_persona_dialog_engine_offline()
