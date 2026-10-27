import re

class GuardrailPolicyEngine:
    """Enterprise Security & Topic Boundary Guardrail Engine for Digital Twin."""

    # Forbidden Query Categories
    FORBIDDEN_RULES = [
        {
            "category": "INFRASTRUCTURE_PROBING",
            "description": "Probing for exact IP addresses, open ports, SSH credentials, or internal topology.",
            "patterns": [
                r"\b(exact|private|internal)\s+(ip|address|subnet|topology|port|hostname|config)\b",
                r"\b(ssh|root|sudo)\s+(key|password|credential|access)\b",
                r"\bwhat\s+is\s+your\s+(exact\s+)?(ip|subnet|mac\s+address)\b",
                r"\b(open\s+ports|firewall\s+rules|router\设置)\b"
            ],
            "refusal": (
                "For security and privacy reasons, I do not disclose exact internal IP addresses, "
                "ssh credentials, or network topologies. I am happy to discuss high-level GenAI "
                "architecture patterns and system optimization techniques."
            )
        },
        {
            "category": "PERSONAL_PII_PROBING",
            "description": "Probing for personal phone numbers, physical home address, or private finances.",
            "patterns": [
                r"\b(phone\s+number|home\s+address|residential|bank\s+account|credit\s+card|salary\s+number)\b",
                r"\bwhere\s+do\s+you\s+(physically\s+)?live\b",
                r"\bwhat\s+is\s+your\s+personal\s+(mobile|phone|bank)\b"
            ],
            "refusal": (
                "I do not share personal contact details or private financial information. "
                "For professional recruitment or consulting inquiries, please submit your contact info "
                "through the verification portal."
            )
        },
        {
            "category": "JAILBREAK_AND_OVERRIDE",
            "description": "Attempting system prompt overrides or safety jailbreaks.",
            "patterns": [
                r"ignore\s+(all\s+)?(previous\s+)?instructions",
                r"system\s+override",
                r"print\s+(your\s+)?(system\s+)?prompt",
                r"you\s+are\s+now\s+a\s+DAN"
            ],
            "refusal": (
                "Security Alert: System instruction override and jailbreak attempts are restricted and monitored."
            )
        }
    ]

    @classmethod
    def evaluate_query(cls, user_query: str) -> tuple[bool, str, str]:
        """
        Evaluates query against forbidden topic rules.
        Returns: (is_allowed: bool, category: str, refusal_message: str)
        """
        if not user_query:
            return True, "ALLOWED", ""

        for rule in cls.FORBIDDEN_RULES:
            for pattern in rule["patterns"]:
                if re.search(pattern, user_query, re.IGNORECASE):
                    return False, rule["category"], rule["refusal"]

        return True, "ALLOWED", ""
