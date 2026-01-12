"""
VLM Render Judge - Visual OCR Quality Evaluation

This metric implements the "Render → Judge" pattern from MinerU_Metis:
1. Render OCR content as image (using LaTeX/HTML rendering)
2. Use VLM to compare original image vs rendered image
3. Output quality assessment

This is a standalone metric that can be used independently or as part of
an iterative refinement workflow.

Prompt source: MinerU_Metis configs/prompts/text/judge-render.j2
"""

import base64
import os
import re
from typing import Any, Dict, List, Optional

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("VLMRenderJudge")
class VLMRenderJudge(BaseOpenAI):
    """
    VLM-based OCR quality evaluation through visual comparison.

    Workflow:
    1. Receive original image + OCR content
    2. Render OCR content as image
    3. VLM compares original vs rendered
    4. Output quality assessment

    ┌─────────┐    ┌──────────┐    ┌─────────────────────┐
    │ 原始图像 │───▶│          │    │                     │
    └─────────┘    │   VLM    │───▶│  EvalDetail         │
    ┌─────────┐    │  Judge   │    │  - is_correct       │
    │ OCR内容  │───▶│          │    │  - reason           │
    └────┬────┘    └──────────┘    └─────────────────────┘
         │              ▲
         ▼              │
    ┌─────────┐         │
    │  渲染    │─────────┘
    │ (LaTeX) │
    └─────────┘

    Input Data Fields:
        - image: Original document image (path or base64)
        - content: OCR result text to evaluate
        - content_type: "text" | "equation" | "table" (optional, default: "text")

    Output:
        - score: 1.0 (correct) or 0.0 (incorrect)
        - label: QUALITY_GOOD or QUALITY_BAD_OCR.*
        - reason: VLM's detailed judgment reason
        - extra: {"is_correct": bool, "rendered_available": bool}

    Configuration Example:
    {
        "name": "VLMRenderJudge",
        "config": {
            "key": "your-api-key",
            "api_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "parameters": {
                "content_type": "equation",
                "render_config": {
                    "density": 150,
                    "pad": 20
                }
            }
        }
    }
    """

    _metric_info = {
        "category": "Multimodality Assessment Metrics",
        "metric_name": "VLMRenderJudge",
        "description": "VLM-based OCR quality evaluation through visual render-compare",
    }

    # Judge prompt from MinerU_Metis (configs/prompts/text/judge-render.j2)
    JUDGE_PROMPT = """You are a Text Consistency Verification Expert. Your only task is to compare text content (including characters, symbols, and text) between two images:
1.    First Image: Ground Truth (original image with accurate text content)
2.    Second Image: Model-rendered OCR result to be evaluated

Judgment Rules:
1.    Core Consistency: Return TRUE only if the text, characters, and symbols in the second image are fully consistent with those in the first image.  Return FALSE if there are actual missing, incorrect, or extra text, characters, or symbols (excluding mere rendering differences).  Additionally, any content that should be present but is not displayed (i.e., undisplayed portions) shall also be deemed inconsistent (return FALSE).
2.    In addition to punctuation marks, spaces, and line breaks, all symbols (including superscripts/subscripts, e.g., ⁸, ₃, ²α) must maintain both semantic consistency and visual shape consistency. Differences in text font styles (e.g., bold/italic, serif/sans-serif, font color) do NOT affect consistency, provided that the core character identity is preserved. Note: This font style exemption applies solely to standard text characters (not symbols) — superscripts, subscripts, and all non-text symbols are excluded from this exemption and must strictly match the ground truth in visual shape.
3.    Space Quantity Rule: Differences in the number of spaces (e.g., 1 space vs. 2 spaces, no space vs. multiple spaces) between the two images do NOT count as inconsistency (IGNORE).
4.    Symbol Punctuation Rule: Differences between Chinese and English symbols/punctuation (e.g., "," vs "，", "." vs "。", "" vs "", ":" vs "：") do NOT count as inconsistency (IGNORE).
5.    Line Break Rule: Differences in line breaks/line wrapping between the two images do NOT count as inconsistency (IGNORE).
6.    Special Character Rule: For ellipsis (.../.......), underscores (//) (or equivalent horizontal line representations), or similar repeated symbols:
- Mandatory Requirement: The symbol type (e.g., ellipsis vs. underscore) MUST exist in the corresponding position of the second image as the first (complete absence of the symbol = ERROR; line break differences do NOT affect position judgment).
- Acceptable Difference: The length/number of repeated symbols (e.g., 3 dots vs. 6 dots, 1 underscore "_" vs. 5 underscores "_____") does NOT need to match (ACCEPT any length).
7.    Truncated Character Rule: If either image contains partial/truncated characters (e.g., half-cut characters at image edges), the OCR result SHOULD NOT recognize these partial characters as valid text. These truncated characters must be IGNORED during consistency comparison – the OCR result is considered incorrect if it attempts to recognize/truncate partial characters.

Output Requirements (MUST COMPLY)
1.    First output concise reason (max 300 words) explaining your judgment (key differences/findings)
2.    Then output ONLY XML (no extra text/formatting) with exactly this structure:
<reason>Concise reason (max 300 words) explaining your judgment.</reason>
<answer>The final judge result: true / false</answer>

Example Reasoning & Output
Case 1 (Allowed Rendering Difference):
<reason>GT has "答案" , OCR has "答案"  → allowed, consistent.</reason>
<answer>true</answer>

Case 2 (Forbidden Difference):
<reason>GT has "ABC" , OCR has "EFG" → inconsistent.</reason>
<answer>false</answer>

Case 3 (Forbidden Difference: Symbol Shape)
<reason>GT has "ⓐ 128r⁸", OCR has "(a) 128r⁸" → ⓐ changed to (a) (Rule 3A violation), inconsistent.</reason>
<answer>false</answer>"""

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Evaluate OCR quality through render-compare.

        Args:
            input_data: Data with 'image' and 'content' fields

        Returns:
            EvalDetail with quality assessment
        """
        try:
            cls.create_client()

            # Get inputs
            image = cls._get_image(input_data)
            content = cls._get_content(input_data)
            content_type = cls._get_content_type(input_data)

            if not image:
                return cls._error_result("No image provided for comparison")

            if not content:
                return cls._error_result("No OCR content provided for evaluation")

            log.info(f"{cls.__name__}: Evaluating {content_type} content")

            # Step 1: Render OCR content
            rendered_base64 = cls._render_content(content, content_type)

            if not rendered_base64:
                log.warning(f"{cls.__name__}: Render failed, using text-only comparison")
                return cls._text_only_comparison(image, content)

            # Step 2: VLM Judge
            judge_result = cls._judge(image, rendered_base64)

            # Step 3: Build result
            return cls._build_result(judge_result, content)

        except Exception as e:
            log.error(f"{cls.__name__} failed: {e}")
            return cls._error_result(f"Evaluation failed: {str(e)}")

    @classmethod
    def _render_content(cls, content: str, content_type: str) -> Optional[str]:
        """
        Render OCR content to image.

        Uses RenderTool if available, otherwise returns None.
        """
        try:
            from dingo.model.llm.agent.tools.render_tool import RenderTool

            # Get render config
            params = cls.dynamic_config.parameters or {}
            render_config = params.get('render_config', {})

            if render_config:
                RenderTool.update_config(render_config)

            result = RenderTool.execute(content=content, content_type=content_type)

            if result.get('success'):
                return result.get('image_base64')
            else:
                log.warning(f"Render failed: {result.get('error')}")
                return None

        except ImportError:
            log.warning("RenderTool not available")
            return None
        except Exception as e:
            log.warning(f"Render error: {e}")
            return None

    @classmethod
    def _judge(cls, original_image: str, rendered_base64: str) -> Dict[str, Any]:
        """
        Use VLM to compare original vs rendered image.

        Returns:
            Dict with 'is_correct' and 'reason'
        """
        try:
            # Build multimodal message
            messages = cls._build_judge_message(original_image, rendered_base64)
            response = cls.send_messages(messages)

            # Parse XML response
            return cls._parse_response(response)

        except Exception as e:
            log.error(f"Judge failed: {e}")
            return {
                'is_correct': False,
                'reason': f"Judge failed: {str(e)}"
            }

    @classmethod
    def _build_judge_message(cls, original_image: str, rendered_base64: str) -> List[Dict]:
        """Build multimodal message with two images."""
        # Load original image
        if os.path.exists(original_image):
            with open(original_image, 'rb') as f:
                original_base64 = base64.b64encode(f.read()).decode('utf-8')
        else:
            original_base64 = original_image

        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.JUDGE_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{original_base64}"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{rendered_base64}"}
                    }
                ]
            }
        ]

    @classmethod
    def _parse_response(cls, response: str) -> Dict[str, Any]:
        """
        Parse VLM's XML response.

        Expected format:
        <reason>...</reason>
        <answer>true / false</answer>
        """
        try:
            reason_match = re.search(r'<reason>(.*?)</reason>', response, re.DOTALL)
            answer_match = re.search(r'<answer>(.*?)</answer>', response, re.DOTALL)

            reason = reason_match.group(1).strip() if reason_match else response[:500]
            answer_text = answer_match.group(1).strip().lower() if answer_match else ""

            is_correct = "true" in answer_text and "false" not in answer_text

            return {
                'is_correct': is_correct,
                'reason': reason
            }

        except Exception as e:
            log.error(f"Parse failed: {e}")
            return {
                'is_correct': False,
                'reason': response[:500]
            }

    @classmethod
    def _build_result(cls, judge_result: Dict, content: str) -> EvalDetail:
        """Build EvalDetail from judge result."""
        result = EvalDetail(metric=cls.__name__)

        is_correct = judge_result.get('is_correct', False)
        reason = judge_result.get('reason', '')

        result.score = 1.0 if is_correct else 0.0
        result.status = not is_correct  # True if there's an issue

        if is_correct:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [
                "✅ OCR content verified correct",
                "",
                "Judge reason:",
                reason
            ]
        else:
            result.label = ["QUALITY_BAD_OCR.VISUAL_MISMATCH"]
            result.reason = [
                "❌ OCR content has errors",
                "",
                "Judge reason:",
                reason,
                "",
                "OCR content evaluated:",
                content[:300] + "..." if len(content) > 300 else content
            ]

        return result

    @classmethod
    def _text_only_comparison(cls, image: str, content: str) -> EvalDetail:
        """Fallback when render is not available."""
        result = EvalDetail(metric=cls.__name__)
        result.score = 0.5
        result.status = True
        result.label = ["QUALITY_UNKNOWN.RENDER_FAILED"]  # 通过 label 标识渲染失败
        result.reason = [
            "⚠️ Could not render OCR content for visual comparison",
            "Render tool may not be available or content format unsupported",
            "",
            "OCR content:",
            content[:300] + "..." if len(content) > 300 else content
        ]
        return result

    @classmethod
    def _error_result(cls, message: str) -> EvalDetail:
        """Create error result."""
        result = EvalDetail(metric=cls.__name__)
        result.status = True
        result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}EVAL_ERROR"]
        result.reason = [f"❌ {message}"]
        return result

    @classmethod
    def _get_image(cls, input_data: Data) -> Optional[str]:
        """Extract image from input data."""
        if hasattr(input_data, 'image'):
            img = input_data.image
            if isinstance(img, list) and img:
                return img[0]
            return img
        return None

    @classmethod
    def _get_content(cls, input_data: Data) -> Optional[str]:
        """Extract OCR content from input data."""
        if hasattr(input_data, 'content'):
            return input_data.content
        return None

    @classmethod
    def _get_content_type(cls, input_data: Data) -> str:
        """Get content type."""
        if hasattr(input_data, 'content_type') and input_data.content_type:
            return input_data.content_type

        params = cls.dynamic_config.parameters or {}
        return params.get('content_type', 'text')
