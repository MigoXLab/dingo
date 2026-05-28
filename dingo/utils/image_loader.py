import base64
import io
import os
from typing import List, Union

from PIL import Image


def _unwrap(source):
    """If source is a list/tuple, return the first element."""
    if isinstance(source, (list, tuple)):
        if not source:
            raise ValueError("Empty image list provided")
        return source[0]
    return source


_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".svg": "image/svg+xml",
}


def _mime_from_ext(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _MIME_MAP.get(ext, "image/png")


def _download_url(url: str, timeout: int = 30) -> bytes:
    import requests

    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    return resp.content


class ImageLoader:
    """Unified image loading for all Dingo evaluators.

    Supports four input types:
      - PIL.Image.Image object
      - Local file path (absolute or relative to CWD)
      - HTTP/HTTPS URL
      - Base64 data URL (``data:image/...;base64,...``)

    If a list is passed, the first element is used automatically.
    """

    @staticmethod
    def load_pil(source: Union[str, List[str], Image.Image]) -> Image.Image:
        """Load an image as a PIL Image (for Rule evaluators).

        Args:
            source: Local path, HTTP URL, base64 data URL, PIL Image,
                    or a list containing any of the above.

        Returns:
            PIL.Image.Image
        """
        source = _unwrap(source)

        if isinstance(source, Image.Image):
            return source

        if not isinstance(source, str):
            raise TypeError(
                f"Expected str or PIL.Image, got {type(source).__name__}"
            )

        if source.startswith("data:"):
            header, data = source.split(",", 1)
            image_bytes = base64.b64decode(data)
            return Image.open(io.BytesIO(image_bytes))

        if source.startswith(("http://", "https://")):
            image_bytes = _download_url(source)
            return Image.open(io.BytesIO(image_bytes))

        # Local file path
        if not os.path.isfile(source):
            raise FileNotFoundError(
                f"Image file not found: '{source}'\n"
                f"Current working directory: {os.getcwd()}\n"
                f"Absolute path would be: {os.path.abspath(source)}\n"
                f"Ensure the path is correct relative to your working directory."
            )
        return Image.open(source)

    @staticmethod
    def encode_for_api(source: Union[str, List[str], Image.Image]) -> str:
        """Encode an image for OpenAI-compatible vision APIs.

        Returns a string suitable for ``{"type": "image_url", "image_url": {"url": ...}}``.

        Args:
            source: Local path, HTTP URL, base64 data URL, PIL Image,
                    or a list containing any of the above.

        Returns:
            URL string or ``data:image/...;base64,...`` data URL.
        """
        source = _unwrap(source)

        if isinstance(source, Image.Image):
            buf = io.BytesIO()
            fmt = source.format or "PNG"
            mime = _MIME_MAP.get(f".{fmt.lower()}", "image/png")
            source.save(buf, format=fmt)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:{mime};base64,{b64}"

        if not isinstance(source, str):
            raise TypeError(
                f"Expected str or PIL.Image, got {type(source).__name__}"
            )

        # Already a data URL or remote URL — pass through
        if source.startswith(("data:", "http://", "https://")):
            return source

        # Local file path
        if not os.path.isfile(source):
            raise FileNotFoundError(
                f"Image file not found: '{source}'\n"
                f"Current working directory: {os.getcwd()}\n"
                f"Absolute path would be: {os.path.abspath(source)}\n"
                f"Ensure the path is correct relative to your working directory."
            )

        mime = _mime_from_ext(source)
        with open(source, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
