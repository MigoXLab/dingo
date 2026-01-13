"""
Render Tool for OCR Self-Verification

This tool renders text/equation/table content as images for VLM comparison.
Used by agent-based OCR quality evaluation to implement the "render-judge-refine" loop.
"""

import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from dingo.model.llm.agent.tools.base_tool import BaseTool
from dingo.model.llm.agent.tools.tool_registry import tool_register
from dingo.utils import log

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class RenderToolConfig(BaseModel):
    """Configuration for RenderTool"""
    font_path: Optional[str] = Field(
        default=None,
        description="Path to font file for text rendering (e.g., simsun.ttc)"
    )
    cjk_font: Optional[str] = Field(
        default=None,
        description="CJK font name for LaTeX rendering (e.g., 'SimSun' on Windows, 'PingFang SC' on macOS, 'Noto Sans CJK SC' on Linux)"
    )
    density: int = Field(
        default=150,
        ge=72,
        le=300,
        description="Rendering density (DPI) for LaTeX"
    )
    timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Timeout for LaTeX rendering in seconds"
    )
    pad: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Padding around rendered content"
    )


@tool_register
class RenderTool(BaseTool):
    """
    Render text/equation/table content as images.

    This tool converts OCR output (text, LaTeX equations, HTML tables) into
    rendered images that can be compared with original document images by VLM.

    Features:
        - Text rendering with CJK support
        - LaTeX equation rendering via xelatex
        - HTML table rendering

    Configuration:
        font_path: Path to font file (default: system font)
        density: Rendering DPI (default: 150)
        timeout: Rendering timeout in seconds (default: 60)
        pad: Padding around content (default: 20)

    Returns:
        Dict with:
            - success: bool
            - image_base64: Base64 encoded PNG image
            - image_path: Optional path to saved image file
            - error: Error message if failed
    """

    name = "render_tool"
    description = "Render text, equations, or tables as images for VLM comparison"
    config: RenderToolConfig = RenderToolConfig()

    LATEX_TEMPLATE = r"""
\documentclass[12pt]{article}
\usepackage{geometry}
\usepackage[CJKmath]{xeCJK}
[CJKFONT]
\geometry{paperwidth=[PAPERWIDTH], paperheight=5000cm, margin=1cm}
\pagestyle{empty}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{wasysym}
\usepackage{unicode-math}
\usepackage{upgreek}
\usepackage{xcolor}
\usepackage{textcomp}
\usepackage{fontspec}
\setmathfont{Latin Modern Math}
\setcounter{MaxMatrixCols}{1000}
\xeCJKDeclareCharClass{CJK}{"0080->"FFFF}
\xeCJKDeclareCharClass{CJK}{"10000->"1FFFF}
\xeCJKDeclareCharClass{CJK}{"20000->"2FFFF}
\xeCJKDeclareCharClass{CJK}{"30000->"3FFFF}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\begin{document}
\raggedright
\makeatletter
\makeatother
[CONTENT]
\end{document}
"""

    @classmethod
    def execute(
        cls,
        content: str,
        content_type: str = "text",
        output_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute rendering and return image.

        Args:
            content: The content to render (text, LaTeX, or HTML)
            content_type: Type of content - "text", "equation", or "table"
            output_path: Optional path to save rendered image

        Returns:
            Dict with:
                - success: bool
                - image_base64: Base64 encoded image
                - image_path: Path to saved image (if output_path provided)
                - content_type: Type of rendered content
                - error: Error message if failed
        """
        if not HAS_PIL:
            return {
                'success': False,
                'error': 'PIL (Pillow) is required for rendering. Install with: pip install Pillow'
            }

        if not content or not content.strip():
            return {
                'success': False,
                'error': 'Content is empty or None'
            }

        try:
            # Route to appropriate renderer
            if content_type == "equation":
                image = cls._render_latex(content)
            elif content_type == "table":
                image = cls._render_table(content)
            else:  # default to text
                image = cls._render_text(content)

            if image is None:
                return {
                    'success': False,
                    'error': f'Failed to render {content_type} content'
                }

            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            result = {
                'success': True,
                'image_base64': image_base64,
                'content_type': content_type,
                'image_size': image.size
            }

            # Optionally save to file
            if output_path:
                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                image.save(output_path)
                result['image_path'] = output_path
                log.info(f"Rendered image saved to: {output_path}")

            return result

        except Exception as e:
            log.error(f"Rendering failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'content_type': content_type
            }

    @classmethod
    def _render_text(cls, content: str) -> Optional[Image.Image]:
        """
        Render plain text as image.

        Args:
            content: Text content to render

        Returns:
            PIL Image or None if failed
        """
        try:
            # Try to load font
            font = None
            font_size = 24

            if cls.config.font_path and os.path.exists(cls.config.font_path):
                try:
                    font = ImageFont.truetype(cls.config.font_path, font_size)
                except Exception:
                    pass

            if font is None:
                try:
                    # Try common system fonts (prioritize Western fonts for better symbol support)
                    font_candidates = [
                        '/System/Library/Fonts/Helvetica.ttc',  # macOS Helvetica
                        'Arial',                                 # Windows/Linux Arial
                        'Arial Unicode MS',                      # Unicode support
                        'DejaVuSans',                           # Linux fallback
                        'SimSun'                                 # Chinese font (last resort)
                    ]
                    for font_name in font_candidates:
                        try:
                            font = ImageFont.truetype(font_name, font_size)
                            break
                        except Exception:
                            continue
                except Exception:
                    font = ImageFont.load_default()

            # Calculate text size
            dummy_img = Image.new('RGB', (1, 1), 'white')
            draw = ImageDraw.Draw(dummy_img)

            # Handle multiline text
            lines = content.split('\n')
            max_width = 0
            total_height = 0
            line_heights = []

            for line in lines:
                bbox = draw.textbbox((0, 0), line or ' ', font=font)
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                max_width = max(max_width, width)
                line_heights.append(height)
                total_height += height + 5  # 5px line spacing

            # Create image with padding
            pad = cls.config.pad
            img_width = max_width + 2 * pad
            img_height = total_height + 2 * pad

            image = Image.new('RGB', (img_width, img_height), 'white')
            draw = ImageDraw.Draw(image)

            # Draw text
            y_offset = pad
            for i, line in enumerate(lines):
                draw.text((pad, y_offset), line, font=font, fill='black')
                y_offset += line_heights[i] + 5

            return image

        except Exception as e:
            log.error(f"Text rendering failed: {e}")
            return None

    @classmethod
    def _render_latex(cls, content: str) -> Optional[Image.Image]:
        """
        Render LaTeX equation as image using xelatex.

        Args:
            content: LaTeX content to render

        Returns:
            PIL Image or None if failed
        """
        temp_dir = tempfile.mkdtemp(prefix="latex_render_")

        try:
            # Prepare content - wrap in math mode if needed
            processed_content = cls._preprocess_latex(content)

            # Determine paper width based on content length
            char_count = len(content)
            if char_count < 100:
                paper_width = "20cm"
            elif char_count < 300:
                paper_width = "40cm"
            else:
                paper_width = "60cm"

            # Determine CJK font to use
            cjk_font_line = ""
            if cls.config.cjk_font:
                cjk_font_line = f"\\setCJKmainfont{{{cls.config.cjk_font}}}"
            else:
                # Try to detect system and use appropriate default
                import platform
                system = platform.system()
                if system == "Windows":
                    cjk_font_line = "\\setCJKmainfont{SimSun}"
                elif system == "Darwin":  # macOS
                    cjk_font_line = "\\setCJKmainfont{PingFang SC}"
                elif system == "Linux":
                    cjk_font_line = "\\setCJKmainfont{Noto Sans CJK SC}"
                else:
                    # Fallback: try SimSun, may fail on non-Windows
                    cjk_font_line = "\\setCJKmainfont{SimSun}"

            # Generate LaTeX file
            latex = cls.LATEX_TEMPLATE.replace("[PAPERWIDTH]", paper_width)
            latex = latex.replace("[CJKFONT]", cjk_font_line)
            latex = latex.replace("[CONTENT]", processed_content)

            tex_file = os.path.join(temp_dir, "formula.tex")
            pdf_file = os.path.join(temp_dir, "formula.pdf")
            png_file = os.path.join(temp_dir, "formula.png")

            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(latex)

            # Compile with xelatex (use list args to prevent shell injection)
            xelatex_cmd = [
                "xelatex",
                "-interaction=nonstopmode",
                f"-output-directory={temp_dir}",
                tex_file
            ]
            result = subprocess.run(
                xelatex_cmd,
                capture_output=True,
                timeout=cls.config.timeout
            )

            if not os.path.exists(pdf_file):
                log.error(f"LaTeX compilation failed: {result.stderr.decode()}")
                return None

            # Convert PDF to PNG using ImageMagick (use list args to prevent shell injection)
            convert_cmd = [
                "magick",
                "-density", str(cls.config.density),
                pdf_file,
                "-background", "white",
                "-alpha", "remove",
                "-quality", "100",
                png_file
            ]
            subprocess.run(convert_cmd, timeout=30)

            if not os.path.exists(png_file):
                log.error("PDF to PNG conversion failed")
                return None

            # Load and crop image
            image = cls._crop_image(png_file)
            return image

        except subprocess.TimeoutExpired:
            log.error("LaTeX rendering timed out")
            return None
        except Exception as e:
            log.error(f"LaTeX rendering failed: {e}")
            return None
        finally:
            # Cleanup
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    @classmethod
    def _preprocess_latex(cls, content: str) -> str:
        """
        Preprocess LaTeX content for rendering.

        Args:
            content: Raw LaTeX content

        Returns:
            Preprocessed LaTeX content
        """
        # Check if content already has math delimiters
        math_patterns = [
            r'\$\$.*?\$\$',
            r'\$.*?\$',
            r'\\\(.*?\\\)',
            r'\\\[.*?\\\]',
            r'\\begin\{equation',
            r'\\begin\{align',
        ]

        has_math = any(re.search(p, content, re.DOTALL) for p in math_patterns)

        if not has_math:
            # Wrap in display math mode
            content = f"$${content}$$"

        # Escape special characters in text mode
        # (simplified - full implementation would be more complex)
        return content

    @classmethod
    def _render_table(cls, content: str) -> Optional[Image.Image]:
        """
        Render HTML table as image.

        Args:
            content: HTML table content

        Returns:
            PIL Image or None if failed
        """
        # For now, fall back to text rendering
        # A full implementation would use a headless browser or
        # specialized HTML-to-image converter
        log.warning("Table rendering falling back to text mode")
        return cls._render_text(content)

    @classmethod
    def _crop_image(cls, image_path: str) -> Image.Image:
        """
        Crop image to content bounds with padding.

        Args:
            image_path: Path to image file

        Returns:
            Cropped PIL Image
        """
        img = Image.open(image_path).convert("L")
        img_data = np.asarray(img, dtype=np.uint8)

        # Find non-white pixels
        nnz_inds = np.where(img_data < 250)

        if len(nnz_inds[0]) == 0:
            # All white - return small image
            return Image.new('RGB', (100, 50), 'white')

        y_min = np.min(nnz_inds[0])
        y_max = np.max(nnz_inds[0])
        x_min = np.min(nnz_inds[1])
        x_max = np.max(nnz_inds[1])

        # Add padding
        pad = cls.config.pad
        h, w = img_data.shape
        x_min = max(0, x_min - pad)
        y_min = max(0, y_min - pad)
        x_max = min(w, x_max + pad)
        y_max = min(h, y_max + pad)

        # Crop and convert to RGB
        img = Image.open(image_path).convert("RGB")
        cropped = img.crop((x_min, y_min, x_max, y_max))

        return cropped
