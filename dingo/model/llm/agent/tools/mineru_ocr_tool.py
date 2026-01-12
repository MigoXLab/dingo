"""
MinerU OCR Tool for Agent-Based Evaluation

This tool calls MinerU API (https://mineru.net/apiManage/docs) for initial OCR recognition.
Used as the first step in the iterative judge-refine workflow.
"""

import base64
import os
import time
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from dingo.model.llm.agent.tools.base_tool import BaseTool
from dingo.model.llm.agent.tools.tool_registry import tool_register
from dingo.utils import log


class MinerUOCRToolConfig(BaseModel):
    """Configuration for MinerU OCR Tool"""
    api_key: Optional[str] = Field(
        default=None,
        description="MinerU API key (from https://mineru.net/apiManage/docs)"
    )
    api_url: str = Field(
        default="https://mineru.net/api/v4/extract/task",
        description="MinerU API endpoint URL"
    )
    timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Timeout for API request in seconds"
    )
    poll_interval: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Interval between status polling in seconds"
    )


@tool_register
class MinerUOCRTool(BaseTool):
    """
    MinerU OCR Tool - Call MinerU API for document parsing.

    MinerU (https://mineru.net) provides high-quality document parsing with support for:
    - Text extraction
    - Formula recognition (LaTeX)
    - Table extraction
    - Layout detection

    API Documentation: https://mineru.net/apiManage/docs

    Configuration:
        api_key: Your MinerU API key
        api_url: API endpoint URL
        timeout: Request timeout in seconds
        poll_interval: Status polling interval

    Returns:
        Dict with:
            - success: bool
            - content: Extracted text/markdown content
            - content_type: Type of content extracted
            - error: Error message if failed
    """

    name = "mineru_ocr_tool"
    description = "Call MinerU API for OCR/document parsing"
    config: MinerUOCRToolConfig = MinerUOCRToolConfig()

    @classmethod
    def execute(
        cls,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        content_type: str = "text",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute MinerU OCR recognition.

        Args:
            image_path: Path to image file
            image_base64: Base64 encoded image (alternative to image_path)
            content_type: Type of content to extract - "text", "formula", "table"

        Returns:
            Dict with OCR results or error
        """
        if not cls.config.api_key:
            return {
                'success': False,
                'error': 'MinerU API key not configured. Get your key from https://mineru.net/apiManage/docs'
            }

        # Get image data
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
        elif image_base64:
            image_data = image_base64
        else:
            return {
                'success': False,
                'error': 'No image provided. Provide either image_path or image_base64.'
            }

        try:
            # Submit extraction task
            result = cls._submit_and_wait(image_data, content_type)
            return result

        except requests.Timeout:
            return {
                'success': False,
                'error': f'MinerU API request timed out after {cls.config.timeout}s'
            }
        except Exception as e:
            log.error(f"MinerU OCR failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @classmethod
    def _submit_and_wait(cls, image_data: str, content_type: str) -> Dict[str, Any]:
        """
        Submit task to MinerU API and wait for result.

        MinerU API is async - we submit a task and poll for completion.
        """
        headers = {
            "Authorization": f"Bearer {cls.config.api_key}",
            "Content-Type": "application/json"
        }

        # Submit task
        submit_payload = {
            "file": f"data:image/png;base64,{image_data}",
            "is_ocr": True,
            "enable_formula": content_type in ["formula", "equation"],
            "enable_table": content_type == "table",
        }

        log.info(f"Submitting MinerU OCR task for {content_type}...")

        response = requests.post(
            cls.config.api_url,
            headers=headers,
            json=submit_payload,
            timeout=30
        )
        response.raise_for_status()

        result = response.json()

        if result.get("code") != 0:
            return {
                'success': False,
                'error': f"MinerU API error: {result.get('msg', 'Unknown error')}"
            }

        task_id = result.get("data", {}).get("task_id")
        if not task_id:
            return {
                'success': False,
                'error': "No task_id returned from MinerU API"
            }

        # Poll for result
        log.info(f"MinerU task submitted, task_id: {task_id}")
        return cls._poll_result(task_id, headers)

    @classmethod
    def _poll_result(cls, task_id: str, headers: Dict) -> Dict[str, Any]:
        """Poll MinerU API for task result."""
        status_url = f"https://mineru.net/api/v4/extract/task/{task_id}"

        start_time = time.time()

        while time.time() - start_time < cls.config.timeout:
            response = requests.get(status_url, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            status = result.get("data", {}).get("status")

            if status == "success":
                # Extract content from result
                content = cls._extract_content(result.get("data", {}))
                return {
                    'success': True,
                    'content': content,
                    'task_id': task_id,
                    'raw_result': result
                }

            elif status == "failed":
                return {
                    'success': False,
                    'error': f"MinerU task failed: {result.get('data', {}).get('msg', 'Unknown error')}"
                }

            # Still processing, wait and retry
            log.debug(f"MinerU task {task_id} status: {status}, waiting...")
            time.sleep(cls.config.poll_interval)

        return {
            'success': False,
            'error': f"MinerU task timed out after {cls.config.timeout}s"
        }

    @classmethod
    def _extract_content(cls, data: Dict) -> str:
        """Extract text content from MinerU result."""
        # Try different result formats
        if "markdown" in data:
            return data["markdown"]
        if "text" in data:
            return data["text"]
        if "content" in data:
            return data["content"]
        if "pages" in data:
            # Multi-page result
            pages = data["pages"]
            contents = []
            for page in pages:
                if isinstance(page, dict):
                    contents.append(page.get("markdown", page.get("text", "")))
                elif isinstance(page, str):
                    contents.append(page)
            return "\n\n".join(contents)

        return str(data)
