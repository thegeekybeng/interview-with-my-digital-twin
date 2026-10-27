import re
import json
import math
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import settings
from core.pii_shield import PIIShield


class InferenceAdapter:
    """Abstract interface defining the contract for LLM inference generation."""
    def generate(self, prompt: str, system_instruction: str) -> str:
        raise NotImplementedError


class OllamaInferenceAdapter(InferenceAdapter):
    """Production adapter invoking the Ollama ChatML HTTP endpoint with anti-loop penalty."""
    def __init__(self, host: Optional[str] = None, model: str = "andrew-twin", timeout: int = 15):
        self.host = host or settings.OLLAMA_HOST
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system_instruction: str) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "repeat_penalty": 1.25,
                "num_predict": 220
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                msg = res_data.get("message", {})
                return msg.get("content", "").strip() if isinstance(msg, dict) else ""
        except Exception as e:
            print(f"[OllamaInferenceAdapter Exception]: {e}")
            return ""


class MockInferenceAdapter(InferenceAdapter):
    """Offline test adapter providing deterministic synthetic generation without live Ollama host."""
    def __init__(self, responses: Optional[Dict[str, str]] = None, default_response: Optional[str] = None):
        self.responses = responses or {}
        self.default_response = default_response or "Mock inference response for unit testing."

    def generate(self, prompt: str, system_instruction: str) -> str:
        for k, v in self.responses.items():
            if k.lower() in prompt.lower():
                return v
        return self.default_response


class QARetriever:
    """Cosine similarity lexical retriever across grounded persona facts."""
    def __init__(self, qa_file: Optional[Path] = None):
        self.qa_data: List[Dict[str, Any]] = []
        target_file = qa_file or (Path(__file__).parent.parent / "data" / "digital_twin_raw_qa.json")
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    self.qa_data = json.load(f)
            except Exception as e:
                print(f"[QARetriever Load Error]: {e}")

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def _cosine_similarity(self, vec1: Counter, vec2: Counter) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])
        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        return float(numerator) / denominator if denominator else 0.0

    def find_best_match(self, query: str) -> Optional[Dict[str, Any]]:
        if not self.qa_data:
            return None
        query_tokens = Counter(self._tokenize(query))
        best_score = 0.0
        best_item = None

        for item in self.qa_data:
            doc_text = f"{item.get('topic', '')} {item.get('question', '')} {item.get('answer', '')}"
            doc_tokens = Counter(self._tokenize(doc_text))
            score = self._cosine_similarity(query_tokens, doc_tokens)
            if score > best_score:
                best_score = score
                best_item = item

        return best_item if best_score > 0.05 else None


class PersonaDialogEngine:
    """
    Deep domain orchestrator for Andrew's Digital Twin.
    Encapsulates persona system prompts, grounded retrieval, LLM dispatch,
    robotic disclaimer stripping, and PII anonymization.
    """

    DEFAULT_FACT = (
        "I focus on privacy-first local inference, hardware-accelerated tensor backends, "
        "and enterprise RAG architecture."
    )

    def __init__(
        self,
        inference_adapter: Optional[InferenceAdapter] = None,
        retriever: Optional[QARetriever] = None,
        pii_shield: Optional[Any] = None
    ):
        self.adapter = inference_adapter or OllamaInferenceAdapter()
        self.retriever = retriever or QARetriever()
        self.pii_shield = pii_shield or PIIShield

    @staticmethod
    def transform_query_to_direct_dialog(query: str) -> str:
        """Converts third-person interview queries into direct second-person dialogue for the model."""
        q = query.strip()
        q = re.sub(r"\b(what is his|what's his)\b", "what is your", q, flags=re.IGNORECASE)
        q = re.sub(r"\btell me about his\b", "tell me about your", q, flags=re.IGNORECASE)
        q = re.sub(r"\bwhat architect roles has he held\b", "what architect roles have you held", q, flags=re.IGNORECASE)
        q = re.sub(r"\bwhat roles has he held\b", "what roles have you held", q, flags=re.IGNORECASE)
        q = re.sub(r"\bwhat has he\b", "what have you", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhas he\b", "have you", q, flags=re.IGNORECASE)
        q = re.sub(r"\bdoes he\b", "do you", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhis\b", "your", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhe is\b", "you are", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhe has\b", "you have", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhe\b", "you", q, flags=re.IGNORECASE)
        return q

    @staticmethod
    def clean_robotics(text: str) -> str:
        """Strips artificial self-referential disclaimers, AI meta-phrases, and robotic preambles."""
        if not text:
            return ""

        for _ in range(4):
            text = re.sub(
                r"^(Model,?\s*|As (Andrew Yeo|Andrew|the candidate|an Architect|a Solutions Architect|an AI language model|an AI designed by [^,]+|an AI Architect|the GenAI Lead|an AI),\s*)",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^(I don't have|I do not have|I lack|As an AI|I exist solely|I am an AI)[^.!\n]*[.!\n]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^[^.!\n]*\b(emotions|opinions|homelab|homelabs|philosophies|beliefs)\b[^.!\n]*[.!\n]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(r"^(or|however|but|also|additionally|furthermore)[,.]?\s*", "", text, flags=re.IGNORECASE)

        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def build_system_instruction(self, role_type: str, target_company: str) -> str:
        """Maps visitor persona role to nuanced narrative guidelines."""
        return (
            f"You are Andrew Yeo, GenAI Lead and Solutions Architect, speaking with a {role_type} from {target_company}. "
            f"Respond directly in 2-3 concise, authentic narrative sentences in first-person ('I', 'my'). "
            f"Never start with preambles such as 'As Andrew Yeo', 'As an AI', or 'Certainly'. "
            f"Never output bullet points, numbered lists, or repetitive loops. "
            f"Speak with authentic engineering depth and personal leadership experience."
        )

    def converse(
        self,
        clean_msg: str,
        role_type: str = "Guest",
        target_company: str = "your organization",
        access_tier: str = "RESTRICTED"
    ) -> str:
        """
        Executes complete RAG generation lifecycle:
        1. Query Normalization (3rd to 2nd person)
        2. Context Fact Retrieval
        3. Persona System Instruction Assembly
        4. LLM Generation via Adapter
        5. Robotic Disclaimer Stripping
        6. Grounded Fallback Validation
        7. PII Redaction
        """
        matched_qa = self.retriever.find_best_match(clean_msg)
        context_fact = matched_qa["answer"] if matched_qa else self.DEFAULT_FACT

        # Dynamically substitute target company name in facts
        context_fact = context_fact.replace("BCG X", target_company)

        direct_question = self.transform_query_to_direct_dialog(clean_msg)
        system_instruction = self.build_system_instruction(role_type, target_company)
        prompt = (
            f"Context: {context_fact}\n\n"
            f"Query: {direct_question}\n\n"
            f"Direct Answer:"
        )

        raw_output = self.adapter.generate(prompt, system_instruction)
        cleaned_output = self.clean_robotics(raw_output)

        # Fallback to cleaned context fact if LLM output fails, loops, or contains robotics
        lower = cleaned_output.lower()
        has_numbered_loop = "1." in cleaned_output and "2." in cleaned_output and "3." in cleaned_output
        if (
            not cleaned_output
            or "model," in lower
            or "as an ai" in lower
            or "as andrew yeo" in lower
            or "don't have" in lower
            or "do not have" in lower
            or has_numbered_loop
        ):
            cleaned_output = self.clean_robotics(context_fact)

        # Apply final PII redaction
        if self.pii_shield:
            return self.pii_shield.sanitize_text(cleaned_output)
        return cleaned_output
