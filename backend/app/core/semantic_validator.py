import httpx
from typing import Tuple, Optional
import datetime
from .config import settings
from .database import pg_connection

class SemanticValidator:
    def __init__(self, ollama_url: str = settings.OLLAMA_URL):
        self.ollama_url = ollama_url

    async def get_embedding(self, text: str) -> list[float]:
        """Compute 768-dim vector via local Ollama nomic-embed-text."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.ollama_url.rstrip('/')}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=10.0
            )
            res.raise_for_status()
            return res.json()["embedding"]

    async def validate_input_intent(
        self, 
        role_type: str, 
        query: str, 
        similarity_threshold: float = 0.82
    ) -> Tuple[bool, Optional[str]]:
        """
        Blocks taboo/out-of-scope questions prior to LLM execution.
        Returns: (is_safe, refusal_reason)
        """
        try:
            query_vector = await self.get_embedding(query)
        except Exception as e:
            print(f"SemanticValidator: Input embedding query failed: {e}")
            return True, None

        # Format vector array for PG
        vector_str = f"[{','.join(map(str, query_vector))}]"
        
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT description, (1 - (embedding <=> %s::vector)) AS similarity
                    FROM semantic_policy_anchors
                    WHERE anchor_type = 'taboo_topic'
                      AND (role_type = %s OR role_type = 'global')
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1;
                    """,
                    (vector_str, role_type, vector_str)
                )
                row = cur.fetchone()

        if row:
            description, similarity = row
            if similarity >= similarity_threshold:
                return False, f"Query aligns with restricted topic: {description}"
        
        return True, None

    async def validate_output_tone(
        self, 
        role_type: str, 
        response_text: str,
        min_positive_similarity: float = 0.65,
        max_negative_similarity: float = 0.75
    ) -> Tuple[bool, str]:
        """
        Ensures the generated output matches expected tone and style.
        Returns: (is_valid, validation_status)
        """
        try:
            response_vector = await self.get_embedding(response_text)
        except Exception as e:
            print(f"SemanticValidator: Output embedding query failed: {e}")
            return True, "Passed (Embedding failed)"

        vector_str = f"[{','.join(map(str, response_vector))}]"

        with pg_connection() as conn:
            with conn.cursor() as cur:
                # 1. Match against target positive tone anchor
                cur.execute(
                    """
                    SELECT (1 - (embedding <=> %s::vector)) AS similarity
                    FROM semantic_policy_anchors
                    WHERE anchor_type = 'positive_tone' AND role_type = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1;
                    """,
                    (vector_str, role_type, vector_str)
                )
                pos_row = cur.fetchone()

                # 2. Match against forbidden negative tone anchor
                cur.execute(
                    """
                    SELECT description, (1 - (embedding <=> %s::vector)) AS similarity
                    FROM semantic_policy_anchors
                    WHERE anchor_type = 'negative_tone' AND (role_type = %s OR role_type = 'global')
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1;
                    """,
                    (vector_str, role_type, vector_str)
                )
                neg_row = cur.fetchone()

        if neg_row:
            description, similarity = neg_row
            if similarity >= max_negative_similarity:
                return False, f"Tone violation: {description}"

        if pos_row:
            similarity = pos_row[0]
            if similarity < min_positive_similarity:
                return False, "Tone drift: response lacks required role-specific framing."

        return True, "Passed"
