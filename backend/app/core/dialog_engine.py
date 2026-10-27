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
        # Anchor persona with conversational few-shot turn to prevent small model from hallucinating or disclaiming
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "What is your working model as a solutions architect?"},
            {"role": "assistant", "content": "I operate as an independent solutions architect and hands-on builder—essentially a one-man army. I take complete ownership of systems from architecture and security boundaries all the way down to implementation, local inference pipelines, and production deployment, delivering high-velocity execution without organizational overhead."},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.25,
                "repeat_penalty": 1.3,
                "repeat_last_n": 256,
                "top_p": 0.9,
                "num_predict": 350
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

    STOPWORDS = {
        "what", "is", "are", "his", "your", "my", "the", "a", "an", "to", "for", "in",
        "on", "with", "and", "of", "tell", "me", "about", "can", "you", "he", "him",
        "how", "do", "does", "did", "have", "has", "had", "would", "could", "should",
        "this", "that", "these", "those", "from", "at", "by", "or", "so", "if"
    }

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'\w+', text.lower())
        filtered = [w for w in words if w not in self.STOPWORDS]
        return filtered if filtered else words

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
            (["technical skill", "technical skills", "key skills", "key technical", "tech stack", "technologies", "what are your skills", "what skills", "core skills", "programming languages"], "qa_key_technical_skills"),
            (["genai", "generative ai", "experience with ai", "ai experience", "experience with genai", "genai experience", "genai track record", "genai work"], "qa_experience_with_genai"),
            (["architecture approach", "approach to systems architecture", "systems architecture", "design philosophy", "engineering philosophy", "architectural philosophy", "how do you approach architecture", "systems approach", "architecture philosophy"], "qa_approach_to_systems_architecture"),
            (["background", "career journey", "career background", "tell me about your background", "tell me about andrew's background", "walk me through your background", "your journey", "career story"], "qa_career_background_journey"),
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
        "I am Andrew Yeo, an independent solutions architect and hands-on systems builder ('one-man army') specializing in local AI inference pipelines, "
        "agentic orchestration, enterprise RAG platforms, and secure multi-agent architectures."
    )

    ROLE_SCHEMAS = {
        "HR Recruiter": {
            "title": "Executive HR Recruiter & Talent Partner",
            "narrative_focus": (
                "Focus on my 18+ years of engineering leadership, hands-on architectural mastery, executive presence, "
                "and proven track record delivering strategic enterprise value as an independent high-velocity builder."
            ),
        },
        "Technical Interviewer": {
            "title": "Technical Systems Evaluator",
            "narrative_focus": (
                "Focus on my deep systems architecture, local inference pipelines (Ollama on Apple Silicon unified memory with Metal MPS), "
                "PostgreSQL pgvector HNSW indexing, RAG retrieval architectures, zero-trust container security (Docker, Tailscale mesh), "
                "and hands-on production full-stack TypeScript/Python engineering as a solo builder."
            ),
        },
        "Founder/Builder Collaborator": {
            "title": "Founder & Technical Builder",
            "narrative_focus": (
                "Focus on my zero-to-one MVP velocity, rapid prototyping, pragmatic tech stack selection, "
                "token economics, cost minimization, and resilient delivery without technical debt."
            ),
        },
        "Cultural Fit Interview": {
            "title": "Cultural Fit & Engineering Culture Interviewer",
            "narrative_focus": (
                "Focus on my collaborative approach, empathetic communication, active pair programming, "
                "and transparent problem-solving."
            ),
        },
        "Media / Press": {
            "title": "Technology Journalist & Media Representative",
            "narrative_focus": (
                "Focus on my architectural stance on AI privacy, edge compute sovereignty, responsible AI governance (Singapore AIGF, EU AI Act), "
                "and enterprise data protection."
            ),
        },
        "Others / Guest": {
            "title": "Visitor & Technology Enthusiast",
            "narrative_focus": (
                "Provide an engaging, welcoming, and succinct narrative of my career, flagship platforms "
                "(MPS-Connect, Nutristar, The Perfect Fit, PC2E), and core architectural focus as an independent builder."
            ),
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
        q = re.sub(r"\b(what are his|what're his)\b", "what are your", q, flags=re.IGNORECASE)
        q = re.sub(r"\b(what is his|what's his)\b", "what is your", q, flags=re.IGNORECASE)
        q = re.sub(r"\btell me about his\b", "tell me about your", q, flags=re.IGNORECASE)
        q = re.sub(r"\btell me about andrew's\b", "tell me about your", q, flags=re.IGNORECASE)
        q = re.sub(r"\btell me about andrew\b", "tell me about your background", q, flags=re.IGNORECASE)
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

        # Remove disclaimers, meta-commentary, and third-person prefixes
        for _ in range(6):
            text = re.sub(r"^Certainly[!,.]?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"^Sure[!,.]?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(
                r"^As my identity is[^.\n]+(?:here's how you might answer this query:)?\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^Here's how you might answer[^.\n]*:\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
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
            # Remove any "As [the/a/an] [role/title/company], " preambles
            text = re.sub(
                r"^As (?:the|an?)\s+[^,.\n]+(?:from|at|in)\s+[^,.\n]+[,.:]\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^As (?:the|an?)\s+(?:experienced\s+)?(?:Senior\s+)?[A-Za-z\s&]+(?:Architect|Engineer|Lead|Evaluator|Partner|Recruiter|Founder|Builder|Interviewer?|Candidate|Consultant)[^,.:\n]*[,.:]\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^As\s+(?:the\s+candidate|the\s+interviewer|the\s+visitor|the\s+evaluator|an?\s+independent\s+solutions\s+architect)[,.:]\s*",
                "",
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r"^(?:Model,?\s*|As (?:Andrew Yeo|Andrew|TheGeekyBeng|TheGeekybeng|Andrew's Digital Twin|the candidate|an Architect|a Solutions Architect|an AI language model|an AI designed by [^,]+|an AI Architect|the GenAI Lead|an AI),?\s*)",
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

        # Convert collective/corporate/team pronouns into first-person singular (independent solo architect)
        replacements = [
            (r"\b(?:[Oo]ur team has|[Mm]y team has)\b", "I have"),
            (r"\b(?:[Oo]ur team|[Mm]y team)\b", "I"),
            (r"\b(?:[Oo]ur approach)\b", "my approach"),
            (r"\b(?:[Oo]ur approaches)\b", "my approaches"),
            (r"\b(?:[Oo]ur strategy)\b", "my strategy"),
            (r"\b(?:[Oo]ur philosophy|[Oo]ur design philosophy)\b", "my design philosophy"),
            (r"\b(?:[Oo]ur products|[Oo]ur solutions|[Oo]ur platforms)\b", "my platforms"),
            (r"\b(?:[Ww]e have developed|[Ww]e developed)\b", "I developed"),
            (r"\b(?:[Ww]e have built out|[Ww]e built out)\b", "I built out"),
            (r"\b(?:[Ww]e have built|[Ww]e built)\b", "I built"),
            (r"\b(?:[Ww]e have created|[Ww]e created)\b", "I created"),
            (r"\b(?:[Ww]e ensure)\b", "I ensure"),
            (r"\b(?:[Ww]e can provide|[Ww]e provide)\b", "I provide"),
            (r"\b(?:[Ww]e understand)\b", "I understand"),
            (r"\b(?:[Ww]e tailor)\b", "I tailor"),
            (r"\b(?:[Ww]e focus)\b", "I focus"),
            (r"\b(?:[Ww]e believe)\b", "I believe"),
            (r"\b(?:allows us to|enables us to)\b", "allows me to"),
            (r"\b(?:for us to)\b", "for me to"),
            (r"\b(?:with us)\b", "with me"),
            (r"\b(?:We have|We've|we have|we've)\b", "I have"),
            (r"\b(?:We are|We're|we are|we're)\b", "I am"),
            (r"\bWe\b", "I"),
            (r"\bwe\b", "I"),
            (r"\bOur\b", "My"),
            (r"\bour\b", "my"),
            (r"\bus\b", "me"),
        ]
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text)

        # Flatten markdown numbered or bulleted items into flowing prose
        text = re.sub(r"^\s*\d+\.\s+\*\*([^*]+)\*\*:\s*", r"\1: ", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s+\*\*([^*]+)\*\*:\s*", r"\1: ", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)

        # Clean up any phantom label merges
        text = re.sub(r"\bCore Identity Solutions\b", "I", text, flags=re.IGNORECASE)

        # Replace any remaining TheGeekyBeng references with Andrew Yeo or remove if parenthetical
        text = re.sub(r"\s*\(TheGeekyBeng\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bTheGeekyBeng\b", "Andrew Yeo", text, flags=re.IGNORECASE)

        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def build_system_instruction(self, role_type: str, target_company: str) -> str:
        """Builds a direct first-person interview persona prompt tailored to the visitor's role."""
        normalized_role = "Others / Guest"
        for key in self.ROLE_SCHEMAS:
            if key.lower() in role_type.lower():
                normalized_role = key
                break

        cfg = self.ROLE_SCHEMAS.get(normalized_role, self.ROLE_SCHEMAS["Others / Guest"])

        return (
            f"You are Andrew Yeo, an independent solutions architect and hands-on systems builder ('one-man army') with over 18 years of technology experience.\n"
            f"You work independently as a solo architect and engineer. You do not work for any company, and you do not have an engineering team. You design, architect, code, test, and deploy complete systems entirely on your own.\n"
            f"You are in an executive interview with a visitor whose background is {cfg['title']} ({target_company}). Do not adopt their role, title, or company—you are Andrew Yeo, the candidate being interviewed, not the interviewer.\n"
            f"Speak exclusively in the first-person singular: 'I', 'me', 'my', 'myself'. Never say 'we', 'our', 'us', or 'our team'. You are a solo builder.\n"
            f"{cfg['narrative_focus']}\n"
            f"Speak naturally, warmly, and compellingly as a real person talking in the room. Directly answer the core semantics of what the interviewer asked.\n"
            f"Never start your answer with 'As...', 'Certainly', 'Sure', 'As an AI', 'As a...', 'As the...', 'Digital Twin', or 'TheGeekyBeng'. Never output bullet points, numbered lists, or bold markdown outline headings. Flow smoothly in 2 to 3 natural conversational paragraphs."
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
        "as my identity is",
        "here's how you might answer",
        "as thegeekybeng",
        "thegeekybeng",
        "andrew's digital twin",
        "digital twin",
        "anthropic",
        "openai",
        "microsoft",
        "direct3d",
        "in 1986",
        "google cloud platform",
        "corporations like",
        "born as part of",
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
            f"Context facts:\n{combined_context}\n\n"
            f"Interviewer asks: \"{direct_question}\"\n\n"
            f"Respond conversationally as Andrew Yeo in the first-person singular ('I', 'my'), as an independent solo architect ('one-man army'). "
            f"Never use 'we', 'our', or 'our team'. Speak naturally in 2 to 3 flowing paragraphs without bullet points or numbered lists:"
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
