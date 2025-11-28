from dingo.utils import log

try:
    from dingo.utils.semantic.matcher import SemanticMatcher  # noqa E402.

    __all__ = ["SemanticMatcher"]
except ImportError as e:
    log.warning("Semantic matching not available. Install with: pip install sentence-transformers torch")
    log.debug(f"Import error: {e}")

    class SemanticMatcher:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Semantic matching requires additional dependencies.\n"
                "Install with: pip install sentence-transformers torch"
            )

    __all__ = ["SemanticMatcher"]

