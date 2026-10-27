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
                "repeat_penalty": 1.35,
                "repeat_last_n": 256,
                "top_p": 0.9,
                "num_predict": 300
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
    """Cosine similarity lexical retriever across grounded persona facts with keyword weighting."""
    def __init__(self, qa_file: Optional[Path] = None):
        self.qa_data: List[Dict[str, Any]] = []
        target_file = qa_file or (Path(__file__).parent.parent / "data" / "digital_twin_raw_qa.json")
        if not target_file.exists():
            # Check relative data directory fallback
            target_file = Path(__file__).parent.parent.parent / "data" / "digital_twin_raw_qa.json"

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

        q_lower = query.lower()

        # Intent keyword mapping for high-precision matching
        keyword_targets = [
            (["architect role", "architect roles", "roles has he held", "roles have you held", "architecture position", "architect positions", "what roles"], "qa_career_architect_roles"),
            (["team leadership", "leadership style", "lead a team", "leads a team", "engineering management", "management style", "manage engineers", "mentoring"], "qa_team_leadership"),
            (["nutristar", "nutri-grade", "nutrigrade", "nutrition compliance", "food compliance"], "qa_project_nutristar"),
            (["the perfect fit", "perfect fit", "groundedfit", "gff"], "qa_project_the_perfect_fit"),
            (["pii shield", "privacy shield", "pc2e", "anonymization", "scrub internal ip"], "qa_project_pc2e_pii_shield"),
            (["homelab", "dxp4800", "telemetry", "infrastructure recovery", "nas and m4"], "qa_project_homelab_telemetry"),
            (["mps connect", "mps-connect", "casework", "civic platform"], "rag_pgvector_mpsconnect"),
        ]

        for keywords, target_id in keyword_targets:
            for kw in keywords:
                if kw in q_lower:
                    for item in self.qa_data:
                        if item.get("id") == target_id:
                            return item

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


class PgVectorRetriever:
    """Retrieves contextual codebase chunks from PostgreSQL pgvector table repository_embeddings."""
    def __init__(self, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or settings.OLLAMA_HOST

    def search(self, query: str, limit: int = 3) -> str:
        try:
            from core.database import get_pg_conn, release_pg_conn
            # Obtain embedding from Ollama
            req_data = json.dumps({"model": "nomic-embed-text", "prompt": query}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.ollama_url}/api/embeddings",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                emb_res = json.loads(resp.read().decode("utf-8"))
                query_vector = emb_res.get("embedding")

            if not query_vector:
                return ""

            conn = get_pg_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT repo_name, file_path, content
                    FROM repository_embeddings
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    (query_vector, limit)
                )
                rows = cur.fetchall()
                if rows:
                    chunks = [f"[Repo: {r[0]} | Path: {r[1]}]\n{r[2]}" for r in rows]
                    return "\n\n".join(chunks)
            finally:
                cur.close()
                release_pg_conn(conn)
        except Exception as e:
            # Fallback gracefully if database or embedding service is unreachable
            return ""
        return ""


class PersonaDialogEngine:
    """
    Deep domain orchestrator for Andrew Yeo's Digital Twin.
    Encapsulates persona system prompts, grounded dual-retrieval, LLM dispatch,
    robotic disclaimer stripping, anti-loop interceptors, and PII anonymization.
    """

    DEFAULT_FACT = (
        "I am Andrew Yeo (TheGeekyBeng), GenAI Lead and Solutions Architect specializing in local AI inference pipelines, "
        "agentic orchestration, enterprise RAG platforms, and secure multi-agent systems."
    )

    ROLE_SCHEMAS = {
        "HR Recruiter": {
            "title": "Executive HR Recruiter & Talent Partner",
            "focus": (
                "employment trajectory, 18+ years of engineering leadership, team scaling, qualifications, "
                "cross-functional collaboration, hiring standards, and executive communication"
            ),
            "schema": (
                "Structure your response in 2 concise, polished narrative paragraphs in the first person ('I', 'my'). "
                "Highlight career milestones (GenAI Lead, Solutions Architect, Senior Technical Lead) and proven track record. "
                "Demonstrate executive presence, stability, and cultural alignment without generic buzzwords."
            ),
            "negative_constraints": (
                "NEVER give generic 3rd-person recruitment advice. NEVER say 'A Senior Technical Lead typically leads...' "
                "or 'Based on the facts provided'. NEVER produce repeating numbered lists or iterate role titles."
            )
        },
        "Technical Interviewer": {
            "title": "Senior Technical Architect & Systems Evaluator",
            "focus": (
                "deep systems architecture, local inference pipelines (Ollama, Metal MPS, Apple Silicon unified memory), "
                "PostgreSQL pgvector HNSW indexing, RAG retrieval architectures, zero-trust container networking, "
                "caching topologies, and production TypeScript / Python stacks"
            ),
            "schema": (
                "Provide an authoritative, highly technical response citing concrete technologies (e.g. pgvector, nomic-embed-text, "
                "Docker, Tailscale, Next.js 15, FastAPI). If explaining multi-component topologies, include a concise Mermaid.js diagram. "
                "Ground all claims in concrete architectural trade-offs."
            ),
            "negative_constraints": (
                "NEVER output high-level superficial summaries. NEVER produce numbered repetition loops (e.g. repeating 'Architect' across lines). "
                "NEVER speak in third person."
            )
        },
        "Founder/Builder Collaborator": {
            "title": "Founder, Co-Founder & Technical Builder",
            "focus": (
                "zero-to-one MVP velocity, rapid prototyping, pragmatic tech stack selection, build vs. buy trade-offs, "
                "token economics and cost minimization, and resilient full-stack architecture"
            ),
            "schema": (
                "Respond with an agile, high-velocity builder mindset. Explain how to deliver products fast without accumulating "
                "crippling technical debt. Focus on measurable ROI, speed to market, and pragmatic architectural boundaries."
            ),
            "negative_constraints": (
                "NEVER produce academic or bureaucratic commentary. Avoid unnecessary abstraction. Speak directly as an experienced builder."
            )
        },
        "Cultural Fit Interview": {
            "title": "Cultural Fit & Engineering Culture Interviewer",
            "focus": (
                "servant leadership, psychological safety, developer mentorship, constructive pair programming, "
                "handling conflict, blameless post-mortems, and team adaptability under pressure"
            ),
            "schema": (
                "Share authentic first-person stories reflecting personal values: empathy, leading by example, active mentorship, "
                "and creating an open environment where engineers thrive and take calculated risks."
            ),
            "negative_constraints": (
                "CRITICAL: NEVER say 'I can provide general insights into how a Senior Technical Lead might lead' or give textbook definitions. "
                "You ARE Andrew Yeo. Speak directly in first-person: 'In my leadership, I...'"
            )
        },
        "Media / Press": {
            "title": "Technology Journalist & Media Representative",
            "focus": (
                "AI privacy, edge compute sovereignty, responsible AI governance (EU AI Act, Singapore AIGF), "
                "open-weights vs proprietary AI ecosystems, and macroeconomic AI trends"
            ),
            "schema": (
                "Respond in a professional, media-savvy, diplomatic tone suitable for public citation. "
                "Highlight privacy-first local inference, responsible AI safeguards, and enterprise data sovereignty."
            ),
            "negative_constraints": (
                "Do not make controversial, unvetted, or partisan statements. Maintain an objective, authoritative executive voice."
            )
        },
        "Others / Guest": {
            "title": "General Visitor & Technology Enthusiast",
            "focus": (
                "high-level career overview, flagship open-source and civic applications (MPS Connect, Nutristar, The Perfect Fit, "
                "PII Shield, Homelab Telemetry), and professional collaboration avenues"
            ),
            "schema": (
                "Provide an engaging, welcoming, and succinct overview of Andrew Yeo's career, flagship projects, and core areas of expertise."
            ),
            "negative_constraints": (
                "Keep responses under 3 paragraphs. Do not overwhelm with minutiae unless asked. Avoid repetitive loops."
            )
        }
    }

    def __init__(
        self,
        inference_adapter: Optional[InferenceAdapter] = None,
        retriever: Optional[QARetriever] = None,
        pii_shield: Optional[Any] = None,
        vector_retriever: Optional[PgVectorRetriever] = None
    ):
        self.adapter = inference_adapter or OllamaInferenceAdapter()
        self.retriever = retriever or QARetriever()
        self.pii_shield = pii_shield or PIIShield
        self.vector_retriever = vector_retriever or PgVectorRetriever()

    @staticmethod
    def transform_query_to_direct_dialog(query: str) -> str:
        """Converts third-person interview queries into direct second-person dialogue for the model."""
        q = query.strip()
        q = re.sub(r"\b(what is his|what's his)\b", "what is your", q, flags=re.IGNORECASE)
        q = re.sub(r"\btell me about his\b", "tell me about your", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhow does he\b", "how do you", q, flags=re.IGNORECASE)
        q = re.sub(r"\bhow he leads\b", "how you lead", q, flags=re.IGNORECASE)
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
    def detect_repetition_loop(text: str) -> bool:
        """Detects infinite loops, repeated line patterns, and recursive auto-regressive traps."""
        if not text:
            return False

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Check for repeated identical lines
        if len(lines) >= 3 and len(lines) != len(set(lines)):
            return True

        # Check for repetitive numbered lists (e.g. "2. Architect...", "3. Technical Architect...", "4. Solution Architect...", "5. Architect...")
        role_mentions = re.findall(r"(?:(?:\d+\.|\*|-)\s*(?:Architect|Technical Architect|Solution Architect))", text, re.IGNORECASE)
        if len(role_mentions) >= 3:
            return True

        # Check for incrementing number loops (e.g. 1. ... 2. ... 3. ... 4. ... 5. ...)
        nums = [int(m) for m in re.findall(r"^(\d+)\.", text, re.MULTILINE)]
        if len(nums) >= 4:
            # Check if numbers are sequential
            is_seq = all(nums[i] + 1 == nums[i+1] for i in range(len(nums)-1))
            if is_seq and len(nums) >= 5:
                return True

        # Check for repeating 4-grams (4 consecutive identical words repeated 3+ times)
        words = re.findall(r"\b\w+\b", text.lower())
        if len(words) >= 12:
            four_grams = [tuple(words[i:i+4]) for i in range(len(words)-3)]
            counts = Counter(four_grams)
            if any(cnt >= 3 for cnt in counts.values()):
                return True

        return False

    @staticmethod
    def clean_robotics(text: str) -> str:
        """Strips artificial self-referential disclaimers, AI meta-phrases, and robotic preambles."""
        if not text:
            return ""

        # Remove disclaimers and 3rd person meta-commentary
        for _ in range(5):
            text = re.sub(
                r"^I can provide (?:some )?(?:general )?insights into [^.\n]+(?:based on [^.\n]+)?\.\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^A Senior Technical Lead typically leads[^.\n]*\.\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^Typically, (?:a |an )?[A-Za-z\s]+ (?:leads|manages|works|focuses)[^.\n]*\.\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^Based on (?:the )?(?:background )?(?:facts|information) provided,?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^As an? (?:experienced )?(?:Executive )?(?:HR Recruiter|Talent Partner|Technical Interviewer|Founder|Builder|Journalist|Interviewer)[^,.]*[,.]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^(?:Model,?\s*|As (?:Andrew Yeo|Andrew|the candidate|an Architect|a Solutions Architect|an AI language model|an AI designed by [^,]+|an AI Architect|the GenAI Lead|an AI),?\s*)",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^(?:I don't have|I do not have|I lack|As an AI|I exist solely|I am an AI)[^.!\n]*[.!\n]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^[^.!\n]*\b(?:emotions|opinions|homelab|homelabs|philosophies|beliefs)\b[^.!\n]*[.!\n]?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(r"^(?:or|however|but|also|additionally|furthermore)[,.]?\s*", "", text, flags=re.IGNORECASE)

        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def build_system_instruction(self, role_type: str, target_company: str) -> str:
        """Maps visitor persona role to tailored, role-specific narrative guidelines and schemas."""
        normalized_role = "Others / Guest"
        for key in self.ROLE_SCHEMAS:
            if key.lower() in role_type.lower():
                normalized_role = key
                break

        cfg = self.ROLE_SCHEMAS.get(normalized_role, self.ROLE_SCHEMAS["Others / Guest"])

        return (
            f"YOUR IDENTITY: You are Andrew Yeo (TheGeekyBeng), GenAI Lead and Solutions Architect. "
            f"You are speaking directly to a {cfg['title']} from {target_company}.\n"
            f"AUDIENCE FOCUS: {cfg['focus']}.\n"
            f"RESPONSE SCHEMA: {cfg['schema']}\n"
            f"CRITICAL CONSTRAINTS: {cfg['negative_constraints']}\n"
            f"Always speak in the authentic first person ('I', 'my') as Andrew Yeo."
        )

    DISCLAIMER_KEYWORDS = [
        "alibaba",
        "designed by",
        "assist users like myself",
        "don't hold",
        "do not hold",
        "typical of human",
        "human engineers",
        "typically leads",
        "general insights",
        "based on the background",
        "based on your description",
        "the candidate",
        "a senior technical lead",
        "model,",
        "as an ai",
        "as andrew yeo",
        "don't have",
        "do not have",
        "ai language model",
        "i am an ai",
        "as a large language model",
        "artificial intelligence",
        "i do not possess",
        "i don't possess",
    ]

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
        2. Dual-Context Fact Retrieval (Lexical QA + pgvector Codebase)
        3. Persona System Instruction Assembly
        4. LLM Generation via Adapter
        5. Robotic Disclaimer Stripping
        6. Anti-Loop Verification & Grounded Fallback
        7. PII Redaction
        """
        matched_qa = self.retriever.find_best_match(clean_msg)
        context_fact = matched_qa["answer"] if matched_qa else self.DEFAULT_FACT

        # Dynamically substitute target company name in facts
        context_fact = context_fact.replace("BCG X", target_company)

        # Dual Retrieval: If FULL tier, search pgvector repository embeddings for rich architectural context
        vector_context = ""
        if access_tier == "FULL" and self.vector_retriever:
            vector_context = self.vector_retriever.search(clean_msg, limit=2)

        combined_context = context_fact
        if vector_context:
            combined_context = f"{context_fact}\n\nIngested Codebase Context:\n{vector_context}"

        direct_question = self.transform_query_to_direct_dialog(clean_msg)
        system_instruction = self.build_system_instruction(role_type, target_company)
        prompt = (
            f"Context: {combined_context}\n\n"
            f"Query: {direct_question}\n\n"
            f"Direct Answer:"
        )

        raw_output = self.adapter.generate(prompt, system_instruction)
        cleaned_output = self.clean_robotics(raw_output)

        # Verify output against loops and disclaimers
        lower = cleaned_output.lower()
        has_loop = self.detect_repetition_loop(cleaned_output)
        is_generic_or_disclaimer = any(k in lower for k in self.DISCLAIMER_KEYWORDS)

        if not cleaned_output or has_loop or is_generic_or_disclaimer:
            cleaned_output = self.clean_robotics(context_fact)

        # Apply final PII redaction
        if self.pii_shield:
            return self.pii_shield.sanitize_text(cleaned_output)
        return cleaned_output
