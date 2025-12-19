# backend/services/food_matcher.py
"""Hybrid semantic + fuzzy food matching."""

from sentence_transformers import SentenceTransformer, util
from rapidfuzz import fuzz
from functools import lru_cache
from typing import Optional


class FoodMatcher:
    """Matches user queries to USDA food entries."""

    def __init__(self, model_name: str = "paraphrase-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    @lru_cache(maxsize=1000)
    def _embed(self, text: str):
        return self._model.encode(text, convert_to_tensor=True)

    def find_best_match(
            self,
            query: str,
            candidates: list[dict],
            alpha: float = 0.5
    ) -> Optional[dict]:
        """
        Find best matching food using hybrid SBERT + fuzzy score.

        Args:
            query: User's food query
            candidates: List of USDA food results
            alpha: Weight for semantic (0-1), rest goes to fuzzy
        """
        if not candidates:
            return None

        query_emb = self._embed(query.lower())
        best_match, best_score = None, 0

        for food in candidates:
            desc = food.get("description", "")

            # Semantic score
            desc_emb = self._embed(desc.lower())
            semantic = util.pytorch_cos_sim(query_emb, desc_emb).item()

            # Fuzzy score
            fuzzy = fuzz.token_set_ratio(query.lower(), desc.lower()) / 100

            # Combined score
            score = (alpha * semantic) + ((1 - alpha) * fuzzy)

            if score > best_score:
                best_match, best_score = food, score

        return best_match