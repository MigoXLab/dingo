import re
from typing import List, Optional, Tuple

from dingo.utils import log

_global_model = None
_model_name = None


class SemanticMatcher:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        global _global_model, _model_name

        if _global_model is not None and _model_name == self.model_name:
            self.model = _global_model
            log.debug(f"Reusing cached model: {self.model_name}")
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for semantic matching.\n"
                "Install with: pip install sentence-transformers torch"
            )

        log.info(f"Loading semantic model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)

        _global_model = self.model
        _model_name = self.model_name
        log.info(f"Model loaded successfully: {self.model_name}")

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'\b[\w-]+\b', text)
        return words

    def _cosine_similarity(self, vec1, vec2) -> float:
        import numpy as np

        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def find_match(
        self, keyword: str, text: str, threshold: float = 0.70
    ) -> Tuple[bool, Optional[str], float]:
        if self.model is None:
            self._load_model()

        words = self._tokenize(text)
        if not words:
            return False, None, 0.0

        keyword_embedding = self.model.encode(keyword, convert_to_numpy=True)

        best_match = None
        best_score = 0.0

        for word in words:
            word_embedding = self.model.encode(word, convert_to_numpy=True)
            similarity = self._cosine_similarity(keyword_embedding, word_embedding)

            if similarity > best_score:
                best_score = similarity
                best_match = word

        if best_score >= threshold:
            return True, best_match, best_score
        else:
            return False, None, best_score

