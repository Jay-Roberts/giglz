"""Show data extraction from ticket URLs via Jina Reader + LLM."""

import json
import logging
import os

import dotenv
import httpx
import openai

from models import ShowSubmission

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

JINA_READER_PREFIX = "https://r.jina.ai/"

BOT_PROTECTION_MARKERS = (
    "Warning: Target URL returned error 403",
    "Warning: This page maybe requiring CAPTCHA",
)

OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"

# Max characters to send to LLM for extraction (controls token cost)
MAX_EXTRACTION_TEXT_LENGTH = 8000

EXTRACTION_PROMPT = """\
Extract concert/show info from this ticket page.
Return ONLY a raw JSON object — no markdown, no code fences, no explanation.
{"artists": ["..."], "venue": "...", "date": "YYYY-MM-DD"}
- artists: list of all performer/artist names on the bill
- venue: the venue name only (no address)
- date: show date in YYYY-MM-DD format
If a field can't be determined, use null."""


class ShowExtractor:
    """Extracts show data from ticket URLs via Jina Reader and Haiku."""

    def __init__(self) -> None:
        self._http = httpx.Client(timeout=30)
        self._llm: openai.OpenAI | None = None

    def _get_llm(self) -> openai.OpenAI:
        """Lazy-init LLM client (fails only when actually needed)."""
        if self._llm is None:
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set")
            self._llm = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        return self._llm

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from LLM output, tolerating code fences or extra text."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fall back: find the first { to last } and try that
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
            raise

    def _fetch_page_markdown(self, url: str) -> str:
        """Fetch a URL via Jina Reader and return clean markdown.

        Raises:
            ValueError: If the target site blocked access (bot protection/CAPTCHA).
        """
        logger.info("Fetching %s via Jina Reader", url)
        response = self._http.get(JINA_READER_PREFIX + url)
        response.raise_for_status()
        logger.debug("Got %d chars of markdown", len(response.text))

        for marker in BOT_PROTECTION_MARKERS:
            if marker in response.text:
                logger.warning("Bot protection detected for %s", url)
                raise ValueError(f"Site blocked access (bot protection): {url}")

        return response.text

    def _extract_show_info_w_llm(
        self, page_md: str, openrouter_model=OPENROUTER_MODEL
    ) -> dict | None:
        """Send page markdown to Haiku and return parsed JSON.

        Returns the parsed dict, or None if the LLM returns empty.
        """
        logger.info(f"Extracting show info with: {openrouter_model}")
        completion = self._get_llm().chat.completions.create(
            model=openrouter_model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": page_md},
            ],
            response_format={"type": "json_object"},
        )

        raw = completion.choices[0].message.content
        logger.info("LLM raw response: %r", raw)
        if not raw:
            return None
        return self._parse_json(raw)

    def extract_show(self, url: str) -> ShowSubmission | None:
        """Fetch a ticket URL and extract show data.

        Returns ShowSubmission with ticket_url set to the source URL,
        or None if extraction fails.
        """
        page_md = self._fetch_page_markdown(url)
        return self.extract_from_text(page_md, url)

    def extract_from_text(
        self, text: str, url: str | None = None
    ) -> ShowSubmission | None:
        """Extract show data from raw page text.

        Used by browser extension which provides already-fetched page content.
        Bypasses Jina Reader — text comes directly from the DOM.

        Args:
            text: Page text content (e.g., document.body.innerText)
            url: Optional source URL to store as ticket_url

        Returns:
            ShowSubmission with extracted data, or None if extraction fails.
        """
        # Truncate to avoid excessive token usage
        truncated = text[:MAX_EXTRACTION_TEXT_LENGTH]

        data = self._extract_show_info_w_llm(truncated)

        if data is None:
            logger.warning("LLM returned empty response for text extraction")
            return None

        missing = [
            field for field in ("artists", "venue", "date") if not data.get(field)
        ]
        if missing:
            msg = f"Could not extract {', '.join(missing)}"
            if url:
                msg += f" from {url}"
            logger.warning(msg)
            raise ValueError(msg)

        submission = ShowSubmission(
            artists=data["artists"],
            venue=data["venue"],
            date=data["date"],
            ticket_url=url,
        )
        logger.info(
            "Extracted: %s at %s on %s",
            ", ".join(submission.artists),
            submission.venue,
            submission.date,
        )
        return submission
