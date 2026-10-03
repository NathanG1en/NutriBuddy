# backend/services/food_matcher.py
"""
High-performance two-stage hybrid food matcher.
Combines sub-millisecond lexical pre-filtering (RapidFuzz) with batched
semantic vector reranking (SentenceTransformer).
"""

import logging
from typing import Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


def get_best_device() -> str:
    """Detect optimal compute device: CUDA → MPS → CPU."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            try:
                t = torch.zeros(1, device="mps")
                del t
                return "mps"
            except Exception as e:
                logger.warning(f"MPS available but initialization failed ({e}). Falling back to CPU.")
    except Exception as e:
        logger.warning(f"PyTorch device check error: {e}")
    return "cpu"


class FoodMatcher:
    """
    Two-stage food matcher:
    - Stage 1: Sub-millisecond lexical pre-filter using token-set and token-sort ratios.
    - Stage 2: Batched semantic reranking on the top candidates via SentenceTransformer.
    """

    def __init__(self, model_name: str = "paraphrase-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._model_load_failed = False
        self._device = None

    def _ensure_model(self):
        """Lazy-load the transformer model on first semantic query to keep startup instant."""
        if self._model is None and not self._model_load_failed:
            try:
                from sentence_transformers import SentenceTransformer

                self._device = get_best_device()
                logger.info(f"Loading SentenceTransformer '{self._model_name}' on device '{self._device}'...")
                self._model = SentenceTransformer(self._model_name, device=self._device)
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer ({e}). Falling back to pure fuzzy matching.")
                self._model_load_failed = True

    def find_best_match(
        self,
        query: str,
        candidates: list[dict],
        alpha: float = 0.5,
        top_k_candidates: int = 6,
    ) -> Optional[dict]:
        """
        Find the best matching candidate using two-stage hybrid search.

        Args:
            query: User's food query (e.g. "rolled oats")
            candidates: List of USDA food candidate objects
            alpha: Weight for semantic similarity (0.0 to 1.0), remaining weight is lexical
            top_k_candidates: Number of candidates to pass to Stage 2 semantic reranking

        Returns:
            The best matching candidate dict, or None if candidates list is empty.
        """
        if not candidates:
            return None

        clean_query = query.strip().lower()

        # Fast path 1: Exactly 1 candidate
        if len(candidates) == 1:
            return candidates[0]

        # Fast path 2: Exact string match found
        for food in candidates:
            desc = food.get("description", "").strip().lower()
            if desc == clean_query:
                return food

        # --- Stage 1: Rapid Lexical Pre-Filter (Sub-millisecond) ---
        scored_candidates = []
        for food in candidates:
            desc = food.get("description", "").strip().lower()
            # Combine token set and token sort ratios for word-order invariance
            token_set = fuzz.token_set_ratio(clean_query, desc)
            token_sort = fuzz.token_sort_ratio(clean_query, desc)
            fuzzy_score = (token_set * 0.6 + token_sort * 0.4) / 100.0

            scored_candidates.append((fuzzy_score, food))

        # Sort descending by lexical relevance
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # If highest lexical match is an overwhelming exact match (> 0.98), return it immediately
        top_lexical_score, top_lexical_food = scored_candidates[0]
        if top_lexical_score >= 0.98:
            return top_lexical_food

        # --- Stage 2: Batched Semantic Reranking on Top K ---
        self._ensure_model()

        # If semantic model is unavailable, return best lexical match
        if self._model is None or alpha <= 0.0:
            return top_lexical_food

        # Take only the top-K candidates for semantic reranking
        eval_candidates = scored_candidates[:top_k_candidates]
        descriptions = [c[1].get("description", "").strip().lower() for c in eval_candidates]

        try:
            import numpy as np

            # Encode query and all candidate descriptions in a single batch
            all_texts = [clean_query] + descriptions
            embeddings = self._model.encode(
                all_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            query_vec = embeddings[0]
            cand_vecs = embeddings[1:]

            # Compute cosine similarity via dot product (since normalized)
            semantic_scores = np.dot(cand_vecs, query_vec)

            best_food = None
            best_score = -1.0

            for i, (fuzzy_score, food) in enumerate(eval_candidates):
                semantic_score = float(semantic_scores[i])
                combined_score = (alpha * semantic_score) + ((1.0 - alpha) * fuzzy_score)

                if combined_score > best_score:
                    best_score = combined_score
                    best_food = food

            return best_food

        except Exception as e:
            logger.warning(f"Semantic reranking failed ({e}), falling back to top lexical match.")
            return top_lexical_food