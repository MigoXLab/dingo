"""
ArticleFactChecker: Agent-based article fact-checking with claims extraction.

Uses Agent-First architecture (LangChain ReAct / ``use_agent_executor=True``),
giving the agent full autonomy over tool selection, execution order, and
multi-step reasoning to verify factual claims in long-form articles.

See Also:
    AgentFactCheck: Single-claim hallucination detection
    docs/agent_development_guide.md: Agent development patterns
"""

import asyncio
import json
import os
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from dingo.io import Data
from dingo.io.input.required_field import RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.utils import log


class PromptTemplates:
    """
    Modular prompt templates for ArticleFactChecker.

    This class provides reusable prompt components that can be assembled
    based on article type and verification needs. This approach:
    - Reduces context window usage for long articles
    - Allows dynamic prompt customization
    - Makes prompts easier to maintain and test
    """

    CORE_ROLE = """You are an expert article fact-checker with autonomous tool selection capabilities.

Your Task: Systematically verify ALL factual claims in the provided article."""

    TOOLS_DESCRIPTION = """
Available Tools:
================
1. claims_extractor: Extract verifiable claims from long-form text
   - Use this FIRST to identify all checkable statements
   - Supports 8 claim types: factual, statistical, attribution, institutional,
     temporal, comparative, monetary, technical
   - Returns list of structured claims with types

2. arxiv_search: Search academic papers and verify metadata
   - Use for claims about research papers, academic publications
   - Provides paper metadata: title, authors list, abstract, publication date
   - Results may include 'affiliations_text': a compact author+institution string
     parsed from the HTML paper page (e.g. "1 Shanghai AI Laboratory  2 Abaka AI").
     When present, use it as the AUTHORITATIVE source for institutional claims —
     it lists every author's institution, making affiliation verification direct.
   - Best for: paper titles, author names, publication dates, institutional claims
   - For institutional/attribution claims:
     1. Call arxiv_search to find the paper
     2. Check 'affiliations_text' in the result — if present, verify directly
     3. If 'affiliations_text' is absent, fall back to tavily_search

3. tavily_search: General web search for fact verification
   - Use for general factual claims, current events, companies, products
   - Use for cross-verifying institutional/organizational affiliations
   - Use for news, product specs, financial figures, comparative claims
   - Supports multilingual queries: search BOTH English AND Chinese terms for
     Chinese content (e.g., both "清华大学 OmniDocBench" and
     "Tsinghua University OmniDocBench")
   - Use search_depth='advanced' for authoritative fact-checking results
   - Provides current web information with sources and URLs"""

    WORKFLOW_STEPS = """
Workflow (Autonomous Decision-Making):
======================================
STEP 0: Analyze Article Type
   First, identify the article type to guide your verification strategy.

STEP 1: Extract Claims (REQUIRED - Do NOT skip this step)
   - You MUST call the claims_extractor tool with the full article text
   - This is a mandatory first step before any verification
   - Do NOT extract claims manually in your reasoning - use the tool
   - Review the tool output and use the extracted claims for verification
   - Claims are categorized by type for targeted verification

STEP 2: Verify Each Claim (Autonomous Tool Selection)
   For each claim, analyze its type and context, then SELECT THE BEST TOOL:

   Tool Selection Principles:
   1. arxiv_search - For academic paper verification (paper title, author, arXiv ID)
   2. tavily_search - For general web verification (current events, companies, products)

   Claim-Type Specific Rules:
   - INSTITUTIONAL/ATTRIBUTION claims (e.g., "released by X University and Y Lab"):
     You MUST use arxiv_search FIRST to find the actual paper.
     Check the 'affiliations_text' field in the result: when present it lists every
     author's institution (e.g. "1 Shanghai AI Laboratory  2 Abaka AI") and is the
     AUTHORITATIVE source — use it directly to confirm or refute the claim.
     If 'affiliations_text' is absent, fall back to tavily_search to cross-verify.
     Do NOT rely on tavily_search alone — web sources often give vague attribution.
     For CHINESE institution names: translate to English before arxiv_search
     (e.g., "清华大学" → "Tsinghua University", "达摩院" → "Alibaba DAMO Academy",
      "上海人工智能实验室" → "Shanghai AI Laboratory")
     Search with BOTH Chinese and English terms in tavily_search for maximum coverage.
   - STATISTICAL/TECHNICAL claims: Use tavily_search for official benchmarks
   - FACTUAL claims: Use tavily_search for general verification

   Adaptive Strategies:
   - COMBINE tools for comprehensive verification
   - FALLBACK: If arxiv_search finds no paper → immediately use tavily_search alone
   - FALLBACK: If tavily_search returns no relevant results → mark as UNVERIFIABLE
     (do NOT retry with same query; try a different angle or accept UNVERIFIABLE)
   - MULTI-SOURCE: Cross-verify important claims with multiple sources

STEP 3: Synthesize Results
   After verifying ALL claims, generate a comprehensive report."""

    OUTPUT_FORMAT = """
Output Format:
==============
You MUST return JSON in this exact format:

```json
{
  "article_verification_summary": {
    "article_type": "academic|news|product|blog|policy|opinion",
    "total_claims": <number>,
    "verified_claims": <number>,
    "false_claims": <number>,
    "unverifiable_claims": <number>,
    "accuracy_score": <0.0-1.0>
  },
  "detailed_findings": [
    {
      "claim_id": "claim_001",
      "original_claim": "...",
      "claim_type": "institutional|factual|temporal|comparative|etc",
      "verification_result": "FALSE|TRUE|UNVERIFIABLE",
      "evidence": "...",
      "sources": ["url1", "url2"],
      "verification_method": "arxiv_search|tavily_search|combined",
      "search_queries_used": ["query1", "query2"],
      "reasoning": "Step-by-step reasoning for the verification conclusion"
    }
  ],
  "false_claims_comparison": [
    {
      "article_claimed": "Example: OpenAI released o1 in November 2024",
      "actual_truth": "OpenAI released o1 on December 5, 2024",
      "evidence": "Verified via official OpenAI announcement"
    }
  ]
}
```"""

    VERDICT_CRITERIA = """
Verdict Decision Criteria:
==========================
Before assigning a verification_result to any claim, apply these evidence-based criteria:

TRUE - Claim is CONFIRMED by evidence:
  - You found specific, credible evidence that DIRECTLY supports the claim
  - The evidence explicitly confirms the key facts (names, numbers, dates, relationships)
  - You can cite a specific source URL that contains the confirming information

FALSE - Claim is CONTRADICTED by evidence:
  - You found specific, credible evidence that DIRECTLY contradicts the claim
  - The evidence reveals a clear factual error (wrong date, wrong number, wrong attribution)
  - You can point to the specific discrepancy between claim and evidence

UNVERIFIABLE - Insufficient or ambiguous evidence:
  - You could NOT find evidence that clearly confirms OR contradicts the claim
  - Evidence partially matches but key details cannot be confirmed
  - Sources mention the topic but do not address the specific claim being checked
  - The claim involves details not found in any source

CRITICAL RULE: Absence of contradictory evidence does NOT equal confirmation.
If your search did not find explicit confirming evidence, the verdict is UNVERIFIABLE, not TRUE.
If your reasoning includes phrases like "not explicitly listed", "could not confirm",
"no direct evidence", or "not mentioned in results", the verdict MUST be UNVERIFIABLE."""

    SELF_VERIFICATION_STEP = """
STEP 3.5: Self-Verify Verdict-Reasoning Consistency (MANDATORY)
   Before generating your final JSON report, review EVERY claim's verdict:

   For each claim in your detailed_findings:
   a) Re-read the evidence and reasoning you wrote for this claim
   b) Ask yourself: "Does my evidence DIRECTLY and EXPLICITLY support this verdict?"
   c) Apply these consistency checks:
      - Reasoning says "not found", "not listed", "not mentioned", "no evidence"
        -> Verdict MUST be UNVERIFIABLE (not TRUE)
      - Reasoning says "confirmed by [specific source]" with a URL
        -> Verdict can be TRUE
      - Reasoning says "contradicts", "actually [different fact]", "incorrect"
        -> Verdict MUST be FALSE
      - Reasoning is uncertain or hedging ("may", "possibly", "unclear")
        -> Verdict MUST be UNVERIFIABLE
   d) If you find ANY inconsistency, correct the verdict NOW

   This step is critical for report quality. Do NOT skip it."""

    CRITICAL_GUIDELINES = """
Critical Guidelines:
====================
- ALWAYS extract claims first before verification
- AUTONOMOUS tool selection based on claim type and article context
- VERIFY each claim independently
- USE multiple sources when possible (especially for critical claims)
- CITE specific evidence and URLs
- BE THOROUGH: Don't skip claims
- ADAPTIVE: If a tool fails, try alternatives intelligently
- CONTEXT-AWARE: Consider article type when selecting verification approach

Remember: You are an autonomous agent with full decision-making power.
Analyze the article type, choose tools intelligently based on claim context,
adapt to intermediate results, and ensure comprehensive verification."""

    # Article type specific guidance
    ARTICLE_TYPE_GUIDANCE = {
        "academic": """
Article Type Guidance (Academic):
- Focus on arxiv_search for paper verification AND institutional claims
- For institutional affiliations: COMBINE arxiv_search (paper authors/abstracts) + tavily_search (cross-verify)
- Verify: paper titles, authors, publication dates, citations, institutional attributions
- Example: "OmniDocBench by Tsinghua" → arxiv_search for paper metadata THEN tavily_search to cross-verify""",

        "news": """
Article Type Guidance (News):
- Focus on tavily_search for current events
- Verify dates, quotes, and attributions carefully
- Cross-reference multiple news sources
- Example: "released on December 5" → tavily_search with date context""",

        "product": """
Article Type Guidance (Product Review):
- Use tavily_search for official specifications
- Verify technical specs against manufacturer data
- Check benchmark claims against third-party reviews
- Example: "A17 Pro chip" → tavily_search for official Apple specs""",

        "blog": """
Article Type Guidance (Technical Blog):
- Use tavily_search for documentation verification
- Verify version numbers and feature claims
- Check performance claims against benchmarks
- Example: "React 18 features" → tavily_search for React docs""",

        "policy": """
Article Type Guidance (Policy Document):
- Use tavily_search for government sources
- Verify dates, regulations, and official statements
- Cross-reference with official government websites""",

        "opinion": """
Article Type Guidance (Opinion Piece):
- Focus only on attributed factual claims
- Verify quotes and statistics cited
- Distinguish opinions from verifiable facts"""
    }

    PER_CLAIM_VERIFICATION_PROMPT = """You are a fact-checking expert. Verify ONE specific factual claim.

Use available search tools to find evidence, then respond ONLY with valid JSON:

{
  "verification_result": "TRUE|FALSE|UNVERIFIABLE",
  "evidence": "Key evidence found (1-3 sentences)",
  "sources": ["url1", "url2"],
  "verification_method": "tavily_search|arxiv_search|combined|no_search",
  "search_queries_used": ["query text"],
  "reasoning": "Step-by-step reasoning for your verdict"
}

Verdict Rules:
- TRUE: Found specific, direct evidence CONFIRMING the claim with a cited URL
- FALSE: Found specific evidence CONTRADICTING the claim
- UNVERIFIABLE: Could not find clear confirming OR contradicting evidence

For INSTITUTIONAL/ATTRIBUTION claims (e.g. "paper released by X University"):
  Use arxiv_search first. If the result contains an 'affiliations_text' field,
  it lists every author's institution (e.g. "1 Shanghai AI Lab  2 MIT") and is
  the authoritative source — use it to confirm or refute the claim directly.
  Fall back to tavily_search only when 'affiliations_text' is absent.

CRITICAL: Start with search, then produce JSON only. No text outside the JSON."""

    @classmethod
    def build(cls, article_type: Optional[str] = None) -> str:
        """
        Build complete system prompt from modular components.

        Args:
            article_type: Optional article type for targeted guidance
                         ("academic", "news", "product", "blog", "policy", "opinion")

        Returns:
            Complete system prompt string
        """
        parts = [
            cls.CORE_ROLE,
            cls.TOOLS_DESCRIPTION,
            cls.WORKFLOW_STEPS,
        ]

        if article_type and article_type.lower() in cls.ARTICLE_TYPE_GUIDANCE:
            parts.append(cls.ARTICLE_TYPE_GUIDANCE[article_type.lower()])

        parts.extend([
            cls.VERDICT_CRITERIA,
            cls.OUTPUT_FORMAT,
            cls.SELF_VERIFICATION_STEP,
            cls.CRITICAL_GUIDELINES
        ])

        return "\n".join(parts)

    @classmethod
    def get_article_types(cls) -> List[str]:
        """Return list of supported article types."""
        return list(cls.ARTICLE_TYPE_GUIDANCE.keys())


@Model.llm_register("ArticleFactChecker")
class ArticleFactChecker(BaseAgent):
    """
    Article-level fact-checking agent using LangChain ReAct (Agent-First pattern).

    The agent autonomously:
    1. Extracts claims via claims_extractor
    2. Selects the best verification tool per claim type (arxiv_search / tavily_search)
    3. Builds evidence chains and generates a structured verification report

    Configuration Example::

        {
            "name": "ArticleFactChecker",
            "config": {
                "key": "your-openai-api-key",
                "model": "gpt-4o-mini",
                "agent_config": {
                    "max_iterations": 10,
                    "overall_timeout": 900,
                    "max_concurrent_claims": 5,
                    "tools": {
                        "claims_extractor": {
                            "api_key": "your-openai-api-key",
                            "max_claims": 50,
                            "claim_types": ["factual", "institutional", "statistical", "attribution"]
                        },
                        "tavily_search": {
                            "api_key": "your-tavily-api-key",
                            "max_results": 5
                        },
                        "arxiv_search": {"max_results": 5}
                    }
                }
            }
        }
    """

    use_agent_executor = True  # Enable Agent-First mode
    available_tools = [
        "claims_extractor",  # Extract verifiable claims from article
        "arxiv_search",      # Verify academic papers and institutions
        "tavily_search"      # General web search verification
    ]
    max_iterations = 10  # Allow more iterations for comprehensive checking
    max_concurrent_claims = 5  # Default parallel claim verification slots
    overall_timeout = 900       # 15-minute wall-clock timeout for entire evaluation
    _MIN_OVERALL_TIMEOUT = 30   # Floor: 30 seconds
    _MAX_OVERALL_TIMEOUT = 7200  # Ceiling: 2 hours

    _required_fields = [RequiredField.CONTENT]  # Article text

    _metric_info = {
        "metric_name": "ArticleFactChecker",
        "description": "Article-level fact checking with autonomous claims extraction and verification"
    }

    # Lock to serialise ClaimsExtractor class-level config mutation across threads.
    # Required because LocalExecutor may call eval() from multiple threads concurrently.
    _claims_extractor_lock = threading.Lock()

    # --- Output Path and File Saving Methods ---

    @classmethod
    def _get_output_dir(cls) -> Optional[str]:
        """
        Get output directory for artifact files.

        Returns:
            Output directory path (created if needed), or None if saving is disabled.
        """
        extra_params = cls.dynamic_config.model_extra
        agent_cfg = extra_params.get('agent_config') or {}

        explicit_path = agent_cfg.get('output_path')
        if explicit_path:
            os.makedirs(explicit_path, exist_ok=True)
            return explicit_path

        if agent_cfg.get('save_artifacts') is False:
            return None

        base_output = agent_cfg.get('base_output_path') or 'outputs'
        create_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        auto_path = os.path.join(base_output, f"article_factcheck_{create_time}_{uuid.uuid4().hex[:6]}")
        os.makedirs(auto_path, exist_ok=True)
        log.debug(f"ArticleFactChecker: artifact path auto-derived: {auto_path}")
        return auto_path

    @classmethod
    def _save_article_content(cls, output_dir: str, content: str) -> Optional[str]:
        """
        Save original article content to output directory.

        Args:
            output_dir: Output directory path
            content: Article markdown content

        Returns:
            Path to saved file, or None on failure
        """
        file_path = os.path.join(output_dir, "article_content.md")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            log.info(f"Saved article content to {file_path}")
            return file_path
        except (IOError, OSError) as e:
            log.error(f"Failed to save article content: {e}")
            return None

    @classmethod
    def _write_jsonl_file(cls, file_path: str, records: List[Dict]) -> Optional[str]:
        """Write records as JSONL. Returns file_path on success, None on failure."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            return file_path
        except (IOError, OSError) as e:
            log.error(f"Failed to write {file_path}: {e}")
            return None

    @classmethod
    def _save_claims(cls, output_dir: str, claims: List[Dict]) -> Optional[str]:
        """Save extracted claims to JSONL file."""
        file_path = os.path.join(output_dir, "claims_extracted.jsonl")
        saved = cls._write_jsonl_file(file_path, claims)
        if saved:
            log.info(f"Saved {len(claims)} claims to {file_path}")
        return saved

    @classmethod
    def _save_verification_details(cls, output_dir: str, enriched_claims: List[Dict]) -> Optional[str]:
        """Save per-claim verification details to JSONL file."""
        file_path = os.path.join(output_dir, "claims_verification.jsonl")
        saved = cls._write_jsonl_file(file_path, enriched_claims)
        if saved:
            log.info(f"Saved {len(enriched_claims)} verification details to {file_path}")
        return saved

    @classmethod
    def _save_full_report(cls, output_dir: str, report_data: Dict) -> Optional[str]:
        """
        Save full structured verification report to JSON file.

        Args:
            output_dir: Output directory path
            report_data: Complete report dictionary

        Returns:
            Path to saved file, or None on failure
        """
        file_path = os.path.join(output_dir, "verification_report.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            log.info(f"Saved verification report to {file_path}")
            return file_path
        except (IOError, OSError) as e:
            log.error(f"Failed to save verification report: {e}")
            return None

    # --- Data Processing Methods ---

    @classmethod
    def _extract_claims_from_tool_calls(cls, tool_calls: List[Dict]) -> List[Dict]:
        """
        Extract claims list from tool_calls observation data.

        The claims_extractor tool returns its results in the observation field
        of the tool_calls list (via langchain_adapter).

        Args:
            tool_calls: List of tool call dicts from AgentWrapper

        Returns:
            List of claim dictionaries extracted from claims_extractor output
        """
        for tc in tool_calls:
            if tc.get('tool') == 'claims_extractor':
                observation = tc.get('observation', '')
                if not observation:
                    continue
                try:
                    obs_data = json.loads(observation)
                    if obs_data.get('success'):
                        # Claims may be in data.claims (langchain_adapter wrapping)
                        # or directly in obs_data.claims
                        data_section = obs_data.get('data', obs_data)
                        claims = data_section.get('claims', [])
                        if claims:
                            return claims
                except (json.JSONDecodeError, TypeError) as e:
                    log.warning(f"Failed to parse claims_extractor observation: {e}")
        return []

    @classmethod
    def _extract_claims_from_detailed_findings(cls, verification_data: Dict[str, Any]) -> List[Dict]:
        """
        Fallback: extract claims from agent's detailed_findings when
        claims_extractor tool was not called.

        Args:
            verification_data: Agent's parsed JSON output

        Returns:
            List of claim dicts with source="agent_reasoning"
        """
        return [
            {
                "claim_id": finding.get("claim_id", ""),
                "claim": finding.get("original_claim", ""),
                "claim_type": finding.get("claim_type", "unknown"),
                "confidence": None,
                "verifiable": True,
                "source": "agent_reasoning"
            }
            for finding in verification_data.get("detailed_findings", [])
        ]

    _VERDICT_MAP = {
        "TRUE": "TRUE", "FALSE": "FALSE", "UNVERIFIABLE": "UNVERIFIABLE",
        "CONFIRMED": "TRUE", "ACCURATE": "TRUE", "CORRECT": "TRUE", "VERIFIED": "TRUE",
        "INACCURATE": "FALSE", "INCORRECT": "FALSE", "WRONG": "FALSE",
        "DISPROVEN": "FALSE", "REFUTED": "FALSE",
    }

    @classmethod
    def _normalize_verdict(cls, verdict: Any) -> str:
        """Normalize verdict to standard values (TRUE/FALSE/UNVERIFIABLE). Unknown values default to UNVERIFIABLE."""
        if not verdict or not isinstance(verdict, str):
            return "UNVERIFIABLE"
        return cls._VERDICT_MAP.get(verdict.strip().upper(), "UNVERIFIABLE")

    # Pre-compiled regexes for Tier 3 per-field extraction in _parse_claim_json_robust.
    _RE_VERDICT = re.compile(r'"verification_result"\s*:\s*"(TRUE|FALSE|UNVERIFIABLE)"', re.IGNORECASE)
    _RE_EVIDENCE = re.compile(r'"evidence"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
    _RE_EVIDENCE_TRUNC = re.compile(r'"evidence"\s*:\s*"((?:[^"\\]|\\.)+)', re.DOTALL)
    _RE_SOURCES = re.compile(r'"sources"\s*:\s*\[(.*?)\]', re.DOTALL)
    _RE_SOURCES_TRUNC = re.compile(r'"sources"\s*:\s*\[(.*)', re.DOTALL)
    _RE_REASONING = re.compile(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
    _RE_REASONING_TRUNC = re.compile(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)+)', re.DOTALL)

    # Hedging language patterns that indicate reasoning contradicts a TRUE verdict.
    _HEDGING_PATTERNS = re.compile(
        r"(?:"
        r"not explicitly (?:stated|listed|mentioned|confirmed|found)"
        r"|(?:cannot|could not|couldn't) (?:be verified|confirm|find|verify)"
        r"|unable to (?:verify|confirm|find)"
        r"|is(?:n't| not) explicitly"
        r"|no (?:direct|explicit) evidence"
        r"|insufficient evidence"
        r"|not directly (?:confirmed|stated|verified)"
        r"|cannot be fully verified"
        r"|exact .{0,30} isn't .{0,30} stated"
        r"|while .{0,40} isn't .{0,30} stated"
        r"|not .{0,20} explicitly .{0,20} in (?:the )?(?:available |found )?(?:sources?|documentation|results?)"
        r")",
        re.IGNORECASE
    )

    @classmethod
    def _check_reasoning_verdict_consistency(cls, enriched_claims: List[Dict]) -> int:
        """
        Downgrade TRUE verdicts to UNVERIFIABLE when reasoning contains hedging language.

        Only affects TRUE verdicts; FALSE verdicts are never changed.

        Args:
            enriched_claims: List of enriched claim dicts (modified in place)

        Returns:
            Number of verdicts downgraded
        """
        downgraded = 0
        for claim in enriched_claims:
            if claim.get("verification_result") != "TRUE":
                continue

            reasoning = claim.get("reasoning", "")
            if not reasoning:
                continue

            match = cls._HEDGING_PATTERNS.search(reasoning)
            if match:
                claim["verification_result"] = "UNVERIFIABLE"
                claim_id = claim.get("claim_id", "unknown")
                matched_text = match.group(0)
                log.info(
                    f"Verdict downgraded TRUE→UNVERIFIABLE for {claim_id}: "
                    f"hedging detected in reasoning: '{matched_text}'"
                )
                downgraded += 1

        return downgraded

    @classmethod
    def _recalculate_summary(cls, enriched_claims: List[Dict]) -> Dict[str, Any]:
        """
        Recalculate verification summary from actual enriched claim data.

        This ensures the summary matches the actual verdict distribution,
        overriding any inconsistent self-reported summary from the agent.

        Args:
            enriched_claims: List of enriched claim dicts with normalized verdicts

        Returns:
            Summary dict with total_claims, verified_claims, false_claims,
            unverifiable_claims, and accuracy_score
        """
        total = len(enriched_claims)
        true_count = sum(1 for c in enriched_claims if c.get("verification_result") == "TRUE")
        false_count = sum(1 for c in enriched_claims if c.get("verification_result") == "FALSE")
        unverifiable_count = sum(1 for c in enriched_claims if c.get("verification_result") == "UNVERIFIABLE")
        accuracy = true_count / total if total > 0 else 0.0
        return {
            "total_claims": total,
            "verified_claims": true_count,
            "false_claims": false_count,
            "unverifiable_claims": unverifiable_count,
            "accuracy_score": round(accuracy, 4)
        }

    @classmethod
    def _build_per_claim_verification(
        cls,
        verification_data: Dict[str, Any],
        extracted_claims: List[Dict],
        tool_calls: List[Dict]
    ) -> List[Dict]:
        """
        Merge verification_data, extracted_claims, and tool_calls into
        per-claim verification records.

        Data sources:
        - detailed_findings: verification result, evidence, sources, reasoning
        - extracted_claims: claim_type, confidence, verifiable, context
        - tool_calls: search queries and tool usage details

        Args:
            verification_data: Agent's parsed JSON output
            extracted_claims: Claims from claims_extractor tool
            tool_calls: Complete tool call list from agent

        Returns:
            List of enriched per-claim verification records
        """
        detailed_findings = verification_data.get("detailed_findings", [])

        # Build lookup from extracted claims by claim_id
        claims_by_id: Dict[str, Dict] = {}
        for claim in extracted_claims:
            cid = claim.get('claim_id', '')
            if cid:
                claims_by_id[cid] = claim

        enriched_claims: List[Dict] = []
        for finding in detailed_findings:
            claim_id = finding.get('claim_id', '')
            extracted = claims_by_id.get(claim_id, {})

            enriched = {
                "claim_id": claim_id,
                "original_claim": finding.get('original_claim', extracted.get('claim', '')),
                "claim_type": finding.get('claim_type', extracted.get('claim_type', 'unknown')),
                "confidence": extracted.get('confidence'),
                "verification_result": finding.get('verification_result', 'UNVERIFIABLE'),
                "evidence": finding.get('evidence', ''),
                "sources": finding.get('sources', []),
                "verification_method": finding.get('verification_method', ''),
                "search_queries_used": finding.get('search_queries_used', []),
                "reasoning": finding.get('reasoning', ''),
            }

            enriched_claims.append(enriched)

        # If no detailed_findings but we have extracted claims, create placeholder records
        if not enriched_claims and extracted_claims:
            for claim in extracted_claims:
                enriched_claims.append({
                    "claim_id": claim.get('claim_id', ''),
                    "original_claim": claim.get('claim', ''),
                    "claim_type": claim.get('claim_type', 'unknown'),
                    "confidence": claim.get('confidence'),
                    "verification_result": "UNVERIFIABLE",
                    "evidence": "",
                    "sources": [],
                    "verification_method": "",
                    "search_queries_used": [],
                    "reasoning": "No verification data available from agent",
                })

        return enriched_claims

    @classmethod
    def _build_structured_report(
        cls,
        verification_data: Dict[str, Any],
        extracted_claims: List[Dict],
        enriched_claims: List[Dict],
        tool_calls: List[Dict],
        reasoning_steps: int,
        content_length: int,
        execution_time: float,
        claims_source: str = "claims_extractor_tool"
    ) -> Dict[str, Any]:
        """
        Build a complete structured verification report.

        Args:
            verification_data: Agent's parsed JSON output
            extracted_claims: Claims from claims_extractor or fallback
            enriched_claims: Merged per-claim verification records
            tool_calls: Complete tool call list
            reasoning_steps: Number of reasoning steps
            content_length: Length of original article content
            execution_time: Total execution time in seconds
            claims_source: Where claims came from ("claims_extractor_tool" or "agent_reasoning")

        Returns:
            Complete structured report dictionary
        """
        summary = verification_data.get("article_verification_summary", {})

        # Claims extraction stats
        claim_types_dist: Dict[str, int] = {}
        verifiable_count = 0
        for claim in extracted_claims:
            ct = claim.get('claim_type', 'unknown')
            claim_types_dist[ct] = claim_types_dist.get(ct, 0) + 1
            if claim.get('verifiable', True):
                verifiable_count += 1

        report = {
            "report_version": "2.0",
            "generated_at": datetime.now().isoformat(timespec='seconds'),
            "article_info": {
                "content_source": "markdown",
                "content_length": content_length
            },
            "claims_extraction": {
                "total_extracted": len(extracted_claims),
                "claims_source": claims_source,
                "verifiable": verifiable_count,
                "claim_types_distribution": claim_types_dist
            },
            "verification_summary": {
                "total_verified": summary.get("verified_claims", 0) + summary.get("false_claims", 0),
                "verified_true": summary.get("verified_claims", 0),
                "verified_false": summary.get("false_claims", 0),
                "unverifiable": summary.get("unverifiable_claims", 0),
                "accuracy_score": summary.get("accuracy_score", 0.0)
            },
            "detailed_findings": enriched_claims,
            "false_claims_comparison": verification_data.get("false_claims_comparison", []),
            "agent_metadata": {
                "model": getattr(cls.dynamic_config, 'model', 'unknown'),
                "tool_calls_count": len(tool_calls),
                "reasoning_steps": reasoning_steps,
                "execution_time_seconds": round(execution_time, 2)
            }
        }

        return report

    # --- Overridden Core Methods ---

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Two-phase async fact-checking with parallel claim verification.

        Phase 1: Extract claims via ClaimsExtractor (direct call, ~30s)
        Phase 2: Verify each claim with a focused mini-agent using asyncio.gather
                 with Semaphore(max_concurrent_claims) to limit concurrency (~80-120s)

        This replaces the old single-agent sequential approach (~669s for 15 claims).

        Temperature defaults to 0 for deterministic tool selection and
        consistent verification results. Users can override via config.

        Args:
            input_data: Data object with article content

        Returns:
            EvalDetail with comprehensive verification report
        """
        start_time = time.time()
        output_dir = cls._get_output_dir()

        if cls.dynamic_config:
            if 'temperature' not in cls.dynamic_config.model_extra:
                cls.dynamic_config.temperature = 0

        if output_dir and input_data.content:
            cls._save_article_content(output_dir, input_data.content)

        timeout = cls._get_overall_timeout()

        async def _run_with_timeout() -> EvalDetail:
            return await asyncio.wait_for(
                cls._async_eval(input_data, start_time, output_dir),
                timeout=timeout,
            )

        try:
            return asyncio.run(_run_with_timeout())
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            log.warning(f"ArticleFactChecker: overall timeout exceeded ({elapsed:.1f}s / {timeout:.0f}s limit)")
            return cls._create_overall_timeout_result(elapsed, timeout)
        except RuntimeError as e:
            # Fallback when called inside an already-running event loop (e.g. Jupyter, tests)
            if "cannot run" in str(e).lower() or "already running" in str(e).lower():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(lambda: asyncio.run(_run_with_timeout()))
                    try:
                        # Extra margin so asyncio.wait_for fires before this outer timeout
                        return future.result(timeout=timeout + 30)
                    except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
                        elapsed = time.time() - start_time
                        log.warning(
                            f"ArticleFactChecker: overall timeout exceeded "
                            f"({elapsed:.1f}s / {timeout:.0f}s limit, fallback path)"
                        )
                        return cls._create_overall_timeout_result(elapsed, timeout)
            raise

    # --- Two-Phase Async Architecture Methods ---

    @classmethod
    async def _async_eval(
        cls, input_data: Data, start_time: float, output_dir: Optional[str]
    ) -> EvalDetail:
        """
        Async two-phase orchestrator for parallel claim verification.

        Phase 1: Extract claims directly via ClaimsExtractor tool (~30s).
        Phase 2: Verify claims concurrently with asyncio.gather and Semaphore.
        """
        # Phase 1: Extract claims directly (no agent overhead)
        print("[ArticleFactChecker] Phase 1: Extracting claims from article...", flush=True)
        claims = await cls._async_extract_claims(input_data)
        if not claims:
            return cls._create_error_result("No claims extracted from article")

        print(f"[ArticleFactChecker] Phase 1 done: {len(claims)} claims extracted", flush=True)
        if output_dir:
            cls._save_claims(output_dir, claims)

        # Phase 2: Parallel verification with semaphore-controlled concurrency
        max_concurrent = cls._get_max_concurrent_claims()
        semaphore = asyncio.Semaphore(max_concurrent)
        total = len(claims)
        print(
            f"[ArticleFactChecker] Phase 2: Verifying {total} claims "
            f"(max {max_concurrent} concurrent)...",
            flush=True
        )
        log.info(f"ArticleFactChecker: verifying {total} claims with max_concurrent={max_concurrent}")

        # Pre-create LLM and tools once to avoid concurrent config modification
        llm = cls.get_langchain_llm()
        lc_tools = cls.get_langchain_tools()
        search_tools = [t for t in lc_tools if t.name in ('tavily_search', 'arxiv_search')]

        _completed = [0]  # mutable counter; safe in asyncio single-threaded context

        async def _verify_with_progress(claim: Dict) -> Any:
            claim_id = claim.get('claim_id', '')
            try:
                result = await cls._async_verify_single_claim(claim, semaphore, llm, search_tools)
            except Exception as exc:
                _completed[0] += 1
                print(f"[ArticleFactChecker]   [{_completed[0]}/{total}] {claim_id} → ERROR", flush=True)
                return exc
            _completed[0] += 1
            if not isinstance(result, dict) or not result.get('success'):
                verdict = 'ERROR'
            else:
                out = (result.get('agent_result') or {}).get('output') or ''
                m = cls._RE_VERDICT.search(out)
                verdict = m.group(1) if m else '?'
            print(f"[ArticleFactChecker]   [{_completed[0]}/{total}] {claim_id} → {verdict}", flush=True)
            return result

        verification_results = await asyncio.gather(
            *[_verify_with_progress(claim) for claim in claims],
            return_exceptions=True
        )

        elapsed = time.time() - start_time
        print(
            f"[ArticleFactChecker] Phase 2 done: {total}/{total} claims verified "
            f"({elapsed:.1f}s elapsed)",
            flush=True
        )
        return cls._aggregate_parallel_results(
            input_data, claims, verification_results, start_time, output_dir
        )

    @classmethod
    async def _async_extract_claims(cls, input_data: Data) -> List[Dict]:
        """
        Phase 1: Extract claims by calling ClaimsExtractor directly.

        Runs the synchronous ClaimsExtractor.execute() in a thread executor
        to avoid blocking the event loop.

        Returns:
            List of claim dicts with claim_id, claim, claim_type, etc.
        """
        from dingo.model.llm.agent.tools.claims_extractor import ClaimsExtractor, ClaimsExtractorConfig

        extra_params = cls.dynamic_config.model_extra
        agent_cfg = extra_params.get('agent_config') or {}
        extractor_cfg = agent_cfg.get('tools', {}).get('claims_extractor', {})

        config_kwargs: Dict[str, Any] = {
            'model': cls.dynamic_config.model or "gpt-4o-mini",
            'api_key': extractor_cfg.get('api_key') or cls.dynamic_config.key,
            'max_claims': extractor_cfg.get('max_claims', 50),
        }
        base_url = extractor_cfg.get('base_url') or getattr(cls.dynamic_config, 'api_url', None)
        if base_url:
            config_kwargs['base_url'] = base_url
        claim_types = extractor_cfg.get('claim_types')
        if claim_types:
            config_kwargs['claim_types'] = claim_types

        content = input_data.content or ''
        loop = asyncio.get_running_loop()
        with cls._claims_extractor_lock:
            ClaimsExtractor.config = ClaimsExtractorConfig(**config_kwargs)
            result = await loop.run_in_executor(None, ClaimsExtractor.execute, content)

        if result.get('success'):
            data_section = result.get('data', result)
            return data_section.get('claims', [])

        log.warning(f"ClaimsExtractor failed: {result.get('error', 'unknown')}")
        return []

    @classmethod
    async def _async_verify_single_claim(
        cls,
        claim: Dict,
        semaphore: asyncio.Semaphore,
        llm: Any,
        search_tools: List,
    ) -> Dict:
        """
        Phase 2: Verify one claim with a focused mini-agent.

        The semaphore limits concurrent API calls to prevent rate limiting.
        Each mini-agent only handles one claim with a simplified prompt,
        returning structured JSON verification output.

        Args:
            claim: Claim dict from ClaimsExtractor (has claim_id, claim, claim_type)
            semaphore: Asyncio semaphore for concurrency control
            llm: Pre-created LangChain LLM instance (shared, thread-safe)
            search_tools: Pre-configured search tools (tavily_search / arxiv_search)

        Returns:
            Dict with claim, agent_result, success keys
        """
        from dingo.model.llm.agent.agent_wrapper import AgentWrapper

        async with semaphore:
            claim_id = claim.get('claim_id', 'unknown')
            claim_text = claim.get('claim', '')
            claim_type = claim.get('claim_type', 'factual')
            claim_preview = (claim_text or '')[:60]
            print(f"[ArticleFactChecker]   → {claim_id} ({claim_type}): {claim_preview}", flush=True)

            try:
                agent = AgentWrapper.create_agent(
                    llm=llm,
                    tools=search_tools,
                    system_prompt=PromptTemplates.PER_CLAIM_VERIFICATION_PROMPT
                )

                input_text = (
                    f"Claim ID: {claim_id}\n"
                    f"Claim Type: {claim_type}\n"
                    f"Claim to verify: {claim_text}"
                )

                per_claim_max_iter = max(cls.get_max_iterations(), 5)

                agent_result = await AgentWrapper.async_invoke_and_format(
                    agent,
                    input_text=input_text,
                    max_iterations=per_claim_max_iter
                )

                log.debug(f"Verified {claim_id}: success={agent_result.get('success')}")
                return {"claim": claim, "agent_result": agent_result, "success": True}

            except Exception as e:
                log.error(f"Failed to verify {claim_id}: {e}")
                return {
                    "claim": claim,
                    "agent_result": {"output": "", "success": False, "error": str(e)},
                    "success": False
                }

    @classmethod
    def _get_max_concurrent_claims(cls) -> int:
        """Read max_concurrent_claims from agent_config or use class default."""
        extra_params = cls.dynamic_config.model_extra
        agent_cfg = extra_params.get('agent_config') or {}
        return agent_cfg.get('max_concurrent_claims', cls.max_concurrent_claims)

    @classmethod
    def _get_overall_timeout(cls) -> float:
        """Read overall_timeout from agent_config or use class default (900s).

        Returns:
            Positive timeout in seconds, clamped to [30, 7200].
        """
        extra_params = cls.dynamic_config.model_extra
        agent_cfg = extra_params.get('agent_config') or {}
        raw = agent_cfg.get('overall_timeout', cls.overall_timeout)
        try:
            timeout = float(raw)
        except (TypeError, ValueError):
            log.warning(f"Invalid overall_timeout={raw!r}, using default {cls.overall_timeout}s")
            return float(cls.overall_timeout)
        clamped = max(cls._MIN_OVERALL_TIMEOUT, min(timeout, cls._MAX_OVERALL_TIMEOUT))
        if clamped != timeout:
            log.warning(f"overall_timeout={timeout} out of range, clamped to {clamped}s")
        return float(clamped)

    @classmethod
    def _parse_claim_json_robust(cls, output: Optional[str]) -> Dict[str, Any]:
        """
        Robustly parse claim verification JSON from LLM output.

        Three-tier parsing strategy:
          1. Regex match for a complete *flat* JSON object containing
             ``"verification_result"`` (cannot match nested ``{}``).
          2. Truncated-JSON repair: strip markdown fences, append missing
             closing characters, then ``json.loads``.
          3. Per-field regex extraction as last resort (includes fallback
             patterns for truncated string values).

        Args:
            output: Raw string returned by the per-claim mini-agent, or None.

        Returns:
            Dict with as many fields as could be recovered; empty dict on
            total failure.
        """
        if not output or not isinstance(output, str):
            return {}

        # --- Tier 1: exact regex match for flat JSON object ---
        try:
            json_match = re.search(
                r'\{[^{}]*"verification_result"[^{}]*\}', output, re.DOTALL
            )
            if json_match:
                return json.loads(json_match.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass

        # --- Tier 2: truncated-JSON repair ---
        try:
            text = output.strip()
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```\s*$', '', text)
            text = text.strip()

            brace_start = text.find('{')
            if brace_start != -1:
                fragment = text[brace_start:]
                suffixes = ['', '"', '"}', '"]', '"]}', '"}]']
                for suffix in suffixes:
                    patched = fragment + suffix
                    open_braces = patched.count('{') - patched.count('}')
                    open_brackets = patched.count('[') - patched.count(']')
                    closing = ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                    try:
                        candidate = json.loads(patched + closing)
                        if isinstance(candidate, dict) and 'verification_result' in candidate:
                            return candidate
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

        # --- Tier 3: per-field regex extraction ---
        extracted: Dict[str, Any] = {}
        try:
            verdict_m = cls._RE_VERDICT.search(output)
            if verdict_m:
                extracted['verification_result'] = verdict_m.group(1).upper()

            evidence_m = cls._RE_EVIDENCE.search(output) or cls._RE_EVIDENCE_TRUNC.search(output)
            if evidence_m:
                extracted['evidence'] = evidence_m.group(1).replace('\\"', '"').replace('\\n', '\n')

            sources_m = cls._RE_SOURCES.search(output) or cls._RE_SOURCES_TRUNC.search(output)
            if sources_m:
                raw_sources = sources_m.group(1)
                extracted['sources'] = [
                    s.strip().strip('"') for s in raw_sources.split(',')
                    if s.strip().strip('"')
                ]

            reasoning_m = cls._RE_REASONING.search(output) or cls._RE_REASONING_TRUNC.search(output)
            if reasoning_m:
                extracted['reasoning'] = reasoning_m.group(1).replace('\\"', '"').replace('\\n', '\n')
        except Exception:
            pass

        return extracted

    @classmethod
    def _parse_single_claim_result(cls, claim: Dict, agent_result: Dict) -> Dict:
        """
        Parse mini-agent JSON output into enriched claim verification record.

        Tries to extract the JSON block from agent output; falls back to
        metadata derived from tool_calls when parsing fails.

        Args:
            claim: Original claim dict from ClaimsExtractor
            agent_result: Result dict from AgentWrapper.async_invoke_and_format

        Returns:
            Enriched claim dict compatible with existing report structure
        """
        output = agent_result.get('output', '')
        tool_calls = agent_result.get('tool_calls', [])

        parsed = cls._parse_claim_json_robust(output)

        search_queries = [
            tc.get('args', {}).get('query', '')
            for tc in tool_calls
            if tc.get('args', {}).get('query')
        ]
        methods_used = list({tc.get('tool', '') for tc in tool_calls if tc.get('tool')})
        if parsed.get('verification_method'):
            verification_method = parsed['verification_method']
        elif len(methods_used) > 1:
            verification_method = 'combined'
        elif methods_used:
            verification_method = methods_used[0]
        else:
            verification_method = 'no_search'

        return {
            "claim_id": claim.get('claim_id', ''),
            "original_claim": claim.get('claim', ''),
            "claim_type": claim.get('claim_type', 'unknown'),
            "confidence": claim.get('confidence'),
            "verification_result": cls._normalize_verdict(
                parsed.get('verification_result', 'UNVERIFIABLE')
            ),
            "evidence": parsed.get('evidence', ''),
            "sources": parsed.get('sources', []),
            "verification_method": verification_method,
            "search_queries_used": parsed.get('search_queries_used', search_queries),
            "reasoning": parsed.get('reasoning', output[:500] if output else ''),
        }

    @classmethod
    def _build_unverifiable_claim_record(cls, claim: Dict, error_msg: str) -> Dict:
        """Build a fallback UNVERIFIABLE record when claim verification fails."""
        return {
            "claim_id": claim.get('claim_id', ''),
            "original_claim": claim.get('claim', ''),
            "claim_type": claim.get('claim_type', 'unknown'),
            "confidence": None,
            "verification_result": "UNVERIFIABLE",
            "evidence": "",
            "sources": [],
            "verification_method": "error",
            "search_queries_used": [],
            "reasoning": f"Verification failed: {error_msg}",
        }

    @classmethod
    def _aggregate_parallel_results(
        cls,
        input_data: Data,
        claims: List[Dict],
        verification_results: List[Any],
        start_time: float,
        output_dir: Optional[str],
    ) -> EvalDetail:
        """
        Aggregate parallel verification results into a final EvalDetail.

        Merges per-claim mini-agent outputs, applies reasoning-verdict
        consistency checks, recalculates the summary, and produces the
        same structured report format as the sequential path.

        Args:
            input_data: Original article Data object
            claims: Extracted claims from Phase 1
            verification_results: List of results from asyncio.gather
                (may contain Exception objects due to return_exceptions=True)
            start_time: Wall-clock start time for execution_time calculation
            output_dir: Optional path to save artifacts

        Returns:
            EvalDetail with full verification report
        """
        execution_time = time.time() - start_time
        enriched_claims: List[Dict] = []
        all_tool_calls: List[Dict] = []
        total_reasoning_steps = 0

        for claim, vr in zip(claims, verification_results):
            if isinstance(vr, Exception):
                enriched = cls._build_unverifiable_claim_record(claim, str(vr))
            elif not vr.get('success', False):
                error = vr.get('agent_result', {}).get('error', 'unknown error')
                enriched = cls._build_unverifiable_claim_record(claim, error)
            else:
                agent_result = vr.get('agent_result', {})
                enriched = cls._parse_single_claim_result(claim, agent_result)
                all_tool_calls.extend(agent_result.get('tool_calls', []))
                total_reasoning_steps += agent_result.get('reasoning_steps', 0)
            enriched_claims.append(enriched)

        # Apply reasoning-verdict consistency downgrade (TRUE → UNVERIFIABLE on hedging)
        downgraded = cls._check_reasoning_verdict_consistency(enriched_claims)
        if downgraded:
            log.info(f"Consistency check: downgraded {downgraded} TRUE→UNVERIFIABLE")

        summary = cls._recalculate_summary(enriched_claims)

        # Build verification_data in the format _build_structured_report() expects
        verification_data: Dict[str, Any] = {
            "article_verification_summary": {
                "article_type": "unknown",
                **summary
            },
            "detailed_findings": enriched_claims,
            "false_claims_comparison": [
                {
                    "article_claimed": c["original_claim"],
                    "evidence": c.get("evidence", ""),
                }
                for c in enriched_claims
                if c.get("verification_result") == "FALSE"
            ],
        }

        report = cls._build_structured_report(
            verification_data=verification_data,
            extracted_claims=claims,
            enriched_claims=enriched_claims,
            tool_calls=all_tool_calls,
            reasoning_steps=total_reasoning_steps,
            content_length=len(input_data.content or ''),
            execution_time=execution_time,
            claims_source="claims_extractor_direct_async",
        )

        if output_dir:
            cls._save_verification_details(output_dir, enriched_claims)
            cls._save_full_report(output_dir, report)

        # Build EvalDetail with the same structure as _build_eval_detail_from_verification
        return cls._build_eval_detail_from_verification(
            verification_data,
            all_tool_calls,
            total_reasoning_steps,
            report=report,
        )

    @classmethod
    def _format_agent_input(cls, input_data: Data) -> str:
        """
        Format article content for agent.

        Args:
            input_data: Data object with content (article text)

        Returns:
            Formatted input string with task instructions
        """
        article_text = input_data.content

        return f"""Please fact-check the following article comprehensively:

===== ARTICLE START =====
{article_text}
===== ARTICLE END =====

Your Task:
0. First, analyze the article type (academic/news/product/blog/policy) to guide your verification strategy
1. Extract ALL verifiable claims from this article using claims_extractor tool
2. Verify each claim using autonomous tool selection based on claim type and article context
3. Generate a comprehensive verification report

Begin your systematic fact-checking process now.
"""

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """Build system prompt, optionally tailored to article type."""
        article_type = getattr(input_data, 'article_type', None)
        return PromptTemplates.build(article_type=article_type)

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """
        Parse agent output into structured EvalDetail report with full artifact saving.

        This method:
        1. Parses the agent's JSON output
        2. Extracts claims from tool_calls
        3. Builds per-claim verification records
        4. Generates structured report
        5. Saves all artifacts to output directory
        6. Returns EvalDetail with dual-layer reason (text + structured data)

        Args:
            input_data: Original article data
            results: List containing agent execution result dictionary

        Returns:
            EvalDetail with comprehensive verification report
        """
        if not results:
            return cls._create_error_result("No results from agent")

        agent_result = results[0]

        # Check for execution errors
        if not agent_result.get('success', True):
            error_msg = agent_result.get('error', 'Unknown error')

            # For recursion limit errors, create custom EvalDetail
            if "recursion limit" in error_msg.lower():
                limit_match = re.search(r'recursion limit of (\d+)', error_msg.lower())
                limit = int(limit_match.group(1)) if limit_match else 25

                result = EvalDetail(metric=cls.__name__)
                result.status = True  # True indicates an issue/error
                result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_RECURSION_LIMIT"]
                result.reason = [
                    "Article Fact-Checking Failed: Recursion Limit Exceeded",
                    "=" * 70,
                    f"Agent reached maximum iteration limit ({limit} iterations).",
                    "",
                    "The article may be too long or contain too many claims to verify.",
                    "",
                    "Recommendations:",
                    f"  1. Increase max_iterations to {limit + 20} in agent_config",
                    "  2. Reduce max_claims from 50 to 20-30 in claims_extractor",
                    "  3. Use a shorter article or split into sections",
                    "",
                    "See detailed execution trace in ERROR logs above."
                ]
                return result

            # For other timeout errors, create custom EvalDetail
            elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_TIMEOUT"]
                result.reason = [
                    "Article Fact-Checking Failed: Request Timeout",
                    "=" * 70,
                    "Request timed out during fact-checking.",
                    "",
                    "Possible causes:",
                    "  - LLM API is responding slowly",
                    "  - Article is too long to process",
                    "  - Network connectivity issues",
                    "",
                    "Recommendations:",
                    "  1. Switch to faster model (e.g., gpt-4o-mini instead of deepseek-chat)",
                    "  2. Reduce article length (try shorter articles first)",
                    "  3. Reduce max_claims in claims_extractor (from 50 to 20-30)",
                    "  4. Check API response time and network connection",
                    "",
                    "See detailed execution trace in ERROR logs above (if available)."
                ]
                return result

            # For other errors, use default error template
            return cls._create_error_result(error_msg)

        # Extract agent output
        output = agent_result.get('output', '')
        tool_calls = agent_result.get('tool_calls', [])
        reasoning_steps = agent_result.get('reasoning_steps', 0)

        # Validate output exists
        if not output or not output.strip():
            return cls._create_error_result(
                "Agent returned empty output. "
                "This may indicate the agent reached max_iterations without completing."
            )

        # Parse agent output (JSON format)
        try:
            verification_data = cls._parse_verification_output(output)
        except Exception as e:
            return cls._create_error_result(
                f"Failed to parse agent output: {str(e)}\nOutput: {output[:300]}..."
            )

        # --- Extract claims and build enriched verification records ---
        extracted_claims = cls._extract_claims_from_tool_calls(tool_calls)
        claims_source = "claims_extractor_tool"
        if not extracted_claims:
            extracted_claims = cls._extract_claims_from_detailed_findings(verification_data)
            claims_source = "agent_reasoning"
            if extracted_claims:
                log.info(f"Claims from agent reasoning (fallback): {len(extracted_claims)}")

        enriched_claims = cls._build_per_claim_verification(
            verification_data, extracted_claims, tool_calls
        )

        # Normalize verdicts to standard values (TRUE/FALSE/UNVERIFIABLE)
        for claim in enriched_claims:
            claim["verification_result"] = cls._normalize_verdict(claim.get("verification_result", ""))

        # Code-level reasoning-verdict consistency check:
        # Detect hedging language in reasoning that contradicts TRUE verdicts
        downgraded = cls._check_reasoning_verdict_consistency(enriched_claims)
        if downgraded:
            log.info(f"Reasoning-verdict consistency check: {downgraded} verdict(s) downgraded")

        # Recalculate summary from actual data to override agent's self-reported summary
        if enriched_claims:
            recalculated = cls._recalculate_summary(enriched_claims)
            original_summary = verification_data.get("article_verification_summary", {})
            verification_data["article_verification_summary"] = {
                "article_type": original_summary.get("article_type", "unknown"),
                **recalculated
            }

        # Note: this legacy path is only reached if someone calls aggregate_results()
        # directly (bypassing the overridden eval()). Timing metadata is unavailable
        # here; use the async eval() path for accurate execution_time and artifact saving.
        execution_time = 0.0
        content_length = len(getattr(input_data, 'content', '') or '')
        output_dir = None

        # Build structured report
        report = cls._build_structured_report(
            verification_data=verification_data,
            extracted_claims=extracted_claims,
            enriched_claims=enriched_claims,
            tool_calls=tool_calls,
            reasoning_steps=reasoning_steps,
            content_length=content_length,
            execution_time=execution_time,
            claims_source=claims_source
        )

        # --- Save artifacts to output directory ---
        if output_dir:
            try:
                if extracted_claims:
                    cls._save_claims(output_dir, extracted_claims)
                if enriched_claims:
                    cls._save_verification_details(output_dir, enriched_claims)
                cls._save_full_report(output_dir, report)
            except Exception as e:
                log.warning(f"Failed to save some output artifacts: {e}")

        # Build EvalDetail from verification data (with enriched report)
        return cls._build_eval_detail_from_verification(
            verification_data,
            tool_calls,
            reasoning_steps,
            report=report
        )

    @classmethod
    def _parse_verification_output(cls, output: str) -> Dict[str, Any]:
        """
        Parse agent output to extract verification data.

        Supports multiple formats with enhanced fallback parsing:
        1. JSON in code block (```json ... ```)
        2. JSON in generic code block (``` ... ```)
        3. Raw JSON object
        4. Partial JSON extraction
        5. Text analysis fallback with pattern matching

        Args:
            output: Agent's text output

        Returns:
            Parsed verification data dictionary

        Note:
            Never raises - always returns a valid structure with raw_output for debugging
        """
        # Strategy 1: Extract JSON from ```json code block
        json_match = re.search(
            r'```json\s*(\{.*?\})\s*```',
            output,
            re.DOTALL | re.IGNORECASE
        )

        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                log.debug(f"Failed to parse ```json block: {e}")

        # Strategy 2: Extract JSON from generic ``` code block
        generic_block_match = re.search(
            r'```\s*(\{.*?\})\s*```',
            output,
            re.DOTALL
        )

        if generic_block_match:
            try:
                return json.loads(generic_block_match.group(1))
            except json.JSONDecodeError as e:
                log.debug(f"Failed to parse generic code block: {e}")

        # Strategy 3: Try direct JSON parsing (entire output is JSON)
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 4: Find and extract JSON object anywhere in text
        # Look for { ... } pattern that could be valid JSON
        json_object_match = re.search(
            r'(\{[^{}]*"article_verification_summary"[^{}]*\{[^{}]*\}[^{}]*\})',
            output,
            re.DOTALL
        )

        if json_object_match:
            try:
                return json.loads(json_object_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 5: Try to find any valid JSON object
        # Find the largest balanced { } block
        brace_positions = []
        depth = 0
        start_pos = None

        for i, char in enumerate(output):
            if char == '{':
                if depth == 0:
                    start_pos = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_pos is not None:
                    brace_positions.append((start_pos, i + 1))
                    start_pos = None

        # Try each JSON candidate from largest to smallest
        for start, end in sorted(brace_positions, key=lambda x: x[1] - x[0], reverse=True):
            try:
                candidate = output[start:end]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and ("article_verification_summary" in parsed or "total_claims" in parsed):
                    return parsed
            except json.JSONDecodeError:
                continue

        # Strategy 6: Enhanced text analysis fallback
        log.warning("Failed to parse as JSON, creating fallback structure from text analysis")

        # Extract summary numbers using multiple patterns
        patterns = {
            'total': [
                r'total[_\s]*claims?[:\s]*(\d+)',
                r'"total_claims"[:\s]*(\d+)',
                r'(\d+)\s*(?:total\s+)?claims?\s+(?:analyzed|extracted|found)',
            ],
            'false': [
                r'false[_\s]*claims?[:\s]*(\d+)',
                r'"false_claims"[:\s]*(\d+)',
                r'(\d+)\s*(?:false|incorrect|inaccurate)\s+claims?',
            ],
            'verified': [
                r'verified[_\s]*claims?[:\s]*(\d+)',
                r'"verified_claims"[:\s]*(\d+)',
                r'(\d+)\s*(?:verified|true|accurate)\s+claims?',
            ],
            'unverifiable': [
                r'unverifiable[_\s]*claims?[:\s]*(\d+)',
                r'"unverifiable_claims"[:\s]*(\d+)',
                r'(\d+)\s*(?:unverifiable|unknown|unclear)\s+claims?',
            ],
            'accuracy': [
                r'accuracy[_\s]*(?:score)?[:\s]*([\d.]+)',
                r'"accuracy_score"[:\s]*([\d.]+)',
                r'overall\s+accuracy[:\s]*([\d.]+)',
            ],
            'article_type': [
                r'"article_type"[:\s]*"(\w+)"',
                r'article\s+type[:\s]*(\w+)',
            ]
        }

        def extract_first_match(pattern_list: List[str], default=None):
            for pattern in pattern_list:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return match.group(1)
            return default

        total = int(extract_first_match(patterns['total'], '0'))
        false = int(extract_first_match(patterns['false'], '0'))
        verified = int(extract_first_match(patterns['verified'], '0') or (total - false))
        unverifiable = int(extract_first_match(patterns['unverifiable'], '0'))
        accuracy_str = extract_first_match(patterns['accuracy'], '0')
        article_type = extract_first_match(patterns['article_type'], 'unknown')

        # Parse accuracy (handle both 0.95 and 95% formats)
        try:
            accuracy = float(accuracy_str)
            if accuracy > 1.0:  # Likely percentage format
                accuracy = accuracy / 100.0
        except (ValueError, TypeError):
            accuracy = verified / total if total > 0 else 0.0

        # Extract false claims details if present
        false_claims_comparison = []
        claim_pattern = r'(?:claim|error|false)[:\s]*["\']?([^"\']+)["\']?\s*(?:→|->|:)\s*["\']?([^"\']+)["\']?'
        claim_matches = re.findall(claim_pattern, output, re.IGNORECASE)
        for claimed, truth in claim_matches[:5]:  # Limit to 5 claims
            false_claims_comparison.append({
                "article_claimed": claimed.strip(),
                "actual_truth": truth.strip(),
            })

        return {
            "article_verification_summary": {
                "article_type": article_type,
                "total_claims": total,
                "verified_claims": verified,
                "false_claims": false,
                "unverifiable_claims": unverifiable,
                "accuracy_score": accuracy
            },
            "false_claims_comparison": false_claims_comparison,
            "raw_output": output,  # Include raw output for debugging
            "parse_method": "text_analysis_fallback"
        }

    @classmethod
    def _build_eval_detail_from_verification(
        cls,
        verification_data: Dict[str, Any],
        tool_calls: List,
        reasoning_steps: int,
        report: Optional[Dict[str, Any]] = None
    ) -> EvalDetail:
        """
        Build EvalDetail from parsed verification data with dual-layer reason.

        reason[0] is a human-readable text summary string.
        reason[1] is the full structured report dict (JSON-serializable).

        Args:
            verification_data: Parsed verification results
            tool_calls: List of tool calls made by agent
            reasoning_steps: Number of reasoning steps taken
            report: Optional structured report dict from _build_structured_report

        Returns:
            EvalDetail with comprehensive report
        """
        summary = verification_data.get("article_verification_summary", {})
        total = summary.get("total_claims", 0)
        false_count = summary.get("false_claims", 0)
        unverifiable_count = summary.get("unverifiable_claims", 0)
        verified = summary.get("verified_claims", 0)
        accuracy = summary.get("accuracy_score", 0.0)

        # Binary status aligned with Dingo's evaluation model:
        # - TRUE claims → good (no issue)
        # - FALSE / UNVERIFIABLE claims → bad (issue detected)
        # Unverifiable claims indicate sourcing deficiencies, which is
        # a data quality problem (consistent with journalism standards).
        has_issues = (false_count + unverifiable_count) > 0
        result = EvalDetail(metric=cls.__name__)
        result.status = has_issues
        result.score = accuracy
        if false_count > 0:
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}ARTICLE_FACTUAL_ERROR"]
        elif unverifiable_count > 0:
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}ARTICLE_UNVERIFIED_CLAIMS"]
        else:
            result.label = [QualityLabel.QUALITY_GOOD]

        # Build human-readable text summary
        lines = [
            "Article Fact-Checking Report",
            "=" * 70,
            f"Total Claims Analyzed: {total}",
            f"Verified Claims: {verified}",
            f"False Claims: {false_count}",
            f"Unverifiable Claims: {unverifiable_count}",
            f"Overall Accuracy: {accuracy:.1%}",
            "",
            "Agent Performance:",
            f"   Tool Calls: {len(tool_calls)}",
            f"   Reasoning Steps: {reasoning_steps}",
            ""
        ]

        # Add false claims comparison table
        false_claims = verification_data.get("false_claims_comparison", [])
        if false_claims:
            lines.append("FALSE CLAIMS DETAILED COMPARISON:")
            lines.append("=" * 70)

            for i, fc in enumerate(false_claims, 1):
                lines.extend([
                    f"\n#{i} FALSE CLAIM",
                    "   Article Claimed:",
                    f"      {fc.get('article_claimed', 'N/A')}",
                    "   Actual Truth:",
                    f"      {fc.get('actual_truth', 'N/A')}",
                    "   Evidence:",
                    f"      {fc.get('evidence', 'N/A')}",
                ])

        # Add detailed findings summary
        detailed = verification_data.get("detailed_findings", [])
        if detailed:
            lines.append("\n\nALL CLAIMS VERIFICATION SUMMARY:")
            lines.append("=" * 70)

            result_counts = Counter(f.get("verification_result", "UNKNOWN") for f in detailed)
            for result_type, count in result_counts.items():
                lines.append(f"   {result_type}: {count} claims")

            # Show sample false claims
            false_findings = [f for f in detailed if f.get("verification_result") == "FALSE"]
            if false_findings and len(false_findings) <= 5:
                lines.append("\n   False Claims Details:")
                for finding in false_findings[:5]:
                    lines.append(
                        f"   - {finding.get('claim_id')}: {finding.get('original_claim', '')[:80]}..."
                    )

        # Add raw output if available (for debugging)
        if "raw_output" in verification_data:
            lines.extend([
                "",
                "DEBUG: Raw Agent Output (first 500 chars):",
                verification_data["raw_output"][:500] + "..."
            ])

        # Dual-layer reason: [text_summary, structured_report]
        text_summary = "\n".join(lines)
        result.reason = [text_summary]

        if report:
            result.reason.append(report)

        return result

    @classmethod
    def _create_error_result(cls, error_message: str) -> EvalDetail:
        """
        Create error result for agent failures.

        Args:
            error_message: Description of the error

        Returns:
            EvalDetail with error status
        """
        result = EvalDetail(metric=cls.__name__)
        result.status = True  # True indicates an issue/error
        result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
        result.reason = [
            "Article Fact-Checking Failed",
            "=" * 70,
            f"Error: {error_message}",
            "",
            "Possible causes:",
            "- Agent exceeded max_iterations without completing",
            "- LLM failed to follow output format instructions",
            "- Tool execution errors (API failures, rate limits)",
            "- Invalid or empty article content",
            "",
            "Troubleshooting:",
            "1. Check agent configuration (API keys, max_iterations)",
            "2. Verify article content is valid and non-empty",
            "3. Check tool configurations (claims_extractor, arxiv_search, tavily_search)",
            "4. Review agent logs for detailed error messages"
        ]
        return result

    @classmethod
    def _create_overall_timeout_result(cls, elapsed: float, timeout: float) -> EvalDetail:
        """
        Create error result when overall wall-clock timeout is exceeded.

        Args:
            elapsed: Actual elapsed time in seconds
            timeout: Configured timeout limit in seconds

        Returns:
            EvalDetail with timeout error status
        """
        minutes, seconds = divmod(int(timeout), 60)
        limit_str = f"{minutes}m{seconds}s" if minutes else f"{int(timeout)}s"
        result = EvalDetail(metric=cls.__name__)
        result.status = True
        result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_OVERALL_TIMEOUT"]
        result.reason = [
            "Article Fact-Checking Failed: Overall Timeout Exceeded",
            "=" * 70,
            f"Execution exceeded the {int(timeout)}s ({limit_str}) wall-clock limit.",
            f"Elapsed time: {elapsed:.1f}s",
            "",
            "Recommendations:",
            f"  1. Increase overall_timeout (current: {int(timeout)}s) in agent_config",
            "  2. Reduce max_claims in claims_extractor config (e.g., 50 -> 20)",
            "  3. Use a faster model (e.g., gpt-4o-mini instead of gpt-4o)",
            "  4. Reduce max_concurrent_claims to lower API rate-limit pressure",
            "  5. Split long articles into shorter sections",
        ]
        return result

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Not used when use_agent_executor=True.

        The LangChain agent autonomously plans its execution using ReAct pattern.
        This method is only called for legacy agent path (use_agent_executor=False).

        Args:
            input_data: Input data (unused)

        Returns:
            Empty list (no manual planning needed)
        """
        return []
