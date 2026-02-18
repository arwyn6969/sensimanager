"""LLM-Enhanced Commentary Generator — Pluggable AI flavour for match narration.

Wraps the existing template-based commentary engine and optionally enriches
each line with LLM-generated text. Falls back gracefully when no LLM is
configured, producing identical output to the template engine.

Supports multiple pundit personalities via system prompt templates.

Usage:
    # Template-only (no LLM):
    gen = LLMCommentaryGenerator()
    lines = gen.generate(match_result)

    # With LLM enhancement:
    gen = LLMCommentaryGenerator(
        api_base="http://localhost:11434/v1",   # Ollama
        model="llama3",
        personality="dramatic",
    )
    lines = gen.generate(match_result)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from swos420.engine.commentary import generate_commentary, format_for_stream
from swos420.engine.match_result import MatchResult

logger = logging.getLogger(__name__)


# ── Pundit Personalities ─────────────────────────────────────────────────

PERSONALITIES: dict[str, str] = {
    "dramatic": (
        "You are an excitable football commentator in the style of Martin Tyler. "
        "Use dramatic pauses, emphatic exclamations, and vivid metaphors. "
        "React to goals with legendary catchphrases. Keep each line under 200 characters."
    ),
    "tactical": (
        "You are a tactical football analyst like Gary Neville. "
        "Focus on formations, spacing, pressing triggers, and positioning. "
        "Be precise and insightful. Keep each line under 200 characters."
    ),
    "retro_swos": (
        "You are a 1990s football commentator calling a Sensible World of Soccer match. "
        "Reference pixel-perfect goals, 8-bit glory, top-bins screamers, and classic SWOS moments. "
        "Be nostalgic and playful. Keep each line under 200 characters."
    ),
    "deadpan": (
        "You are a dry, deadpan football commentator — think Peter Drury meets a weather reader. "
        "State facts with minimal emotion but occasional devastating wit. "
        "Keep each line under 200 characters."
    ),
    "hype": (
        "You are a Latin American football commentator — pure energy, passion, extended GOOOOOL calls. "
        "Every goal is the greatest ever. Defence is boring. Only attack matters. "
        "Keep each line under 200 characters."
    ),
}

DEFAULT_PERSONALITY = "dramatic"


# ── LLM Commentary Generator ────────────────────────────────────────────


@dataclass
class LLMCommentaryGenerator:
    """Pluggable LLM-enhanced commentary generator.

    Falls back to template-only commentary when no LLM is configured.

    Attributes:
        api_base: OpenAI-compatible API base URL (e.g. Ollama, vLLM, OpenAI).
        api_key: API key. Defaults to OPENAI_API_KEY env var.
        model: Model name to use for completions.
        personality: Pundit personality key (see PERSONALITIES dict).
        temperature: LLM sampling temperature.
        enabled: Whether LLM enhancement is active (auto-detected from config).
    """

    api_base: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    personality: str = DEFAULT_PERSONALITY
    temperature: float = 0.9
    enabled: bool = field(init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_base:
            self.api_base = os.environ.get(
                "SWOS420_LLM_API_BASE", "https://api.openai.com/v1"
            )
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.info(
                "LLM commentary disabled (no API key). Using template engine only."
            )

    @property
    def system_prompt(self) -> str:
        """Build the system prompt from the selected personality."""
        base = PERSONALITIES.get(self.personality, PERSONALITIES[DEFAULT_PERSONALITY])
        return (
            f"{base}\n\n"
            "You are enhancing existing commentary lines for a football match simulation. "
            "You will receive template-generated lines and should rewrite each one in your style, "
            "preserving all factual content (player names, scores, minutes). "
            "Return ONLY the rewritten lines, one per line, no numbering, no extra explanation."
        )

    def generate(self, result: MatchResult) -> list[str]:
        """Generate commentary for a match result.

        Uses LLM enhancement if configured, otherwise falls back to templates.

        Args:
            result: A completed MatchResult from MatchSimulator.

        Returns:
            List of commentary strings in chronological order.
        """
        template_lines = generate_commentary(result)

        if not self.enabled:
            return template_lines

        return self._enhance_with_llm(template_lines, result)

    def generate_stream(self, result: MatchResult) -> str:
        """Generate stream-formatted commentary.

        Returns:
            Multi-line string suitable for OBS overlay.
        """
        if not self.enabled:
            return format_for_stream(result)
        lines = self.generate(result)
        return "\n".join(lines)

    def _enhance_with_llm(
        self, template_lines: list[str], result: MatchResult
    ) -> list[str]:
        """Call LLM API to enhance template commentary lines.

        Falls back to template lines on any error.
        """
        # Filter out empty separator lines for the LLM prompt
        content_lines = [line for line in template_lines if line.strip()]
        if not content_lines:
            return template_lines

        match_context = (
            f"Match: {result.home_team} vs {result.away_team}. "
            f"Score: {result.home_goals}-{result.away_goals}. "
            f"Weather: {result.weather}."
        )

        user_prompt = (
            f"{match_context}\n\n"
            "Rewrite these commentary lines in your style:\n\n"
            + "\n".join(content_lines)
        )

        try:
            enhanced = self._call_api(user_prompt)
            if enhanced:
                # Re-insert empty lines as separators where they were
                return self._merge_separators(template_lines, enhanced)
            return template_lines
        except Exception as exc:
            logger.warning("LLM enhancement failed, using templates: %s", exc)
            return template_lines

    def _call_api(self, user_prompt: str) -> list[str]:
        """Make an OpenAI-compatible chat completion request.

        Uses stdlib urllib to avoid hard dependency on openai/httpx.
        """
        import urllib.request

        url = f"{self.api_base.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 2000,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        return lines

    @staticmethod
    def _merge_separators(
        original: list[str], enhanced: list[str]
    ) -> list[str]:
        """Re-insert empty-line separators from original into enhanced lines.

        The LLM receives only non-empty lines, so we need to put the
        visual separators back in the right positions.
        """
        result: list[str] = []
        enhanced_iter = iter(enhanced)

        for orig_line in original:
            if not orig_line.strip():
                result.append("")
            else:
                try:
                    result.append(next(enhanced_iter))
                except StopIteration:
                    result.append(orig_line)  # fallback

        # Append any remaining enhanced lines
        for extra in enhanced_iter:
            result.append(extra)

        return result

    def available_personalities(self) -> list[str]:
        """Return list of available personality keys."""
        return list(PERSONALITIES.keys())
