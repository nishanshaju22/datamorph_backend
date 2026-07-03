import re
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.messages import HumanMessage, SystemMessage
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

# Prompt
SYSTEM_PROMPT = """You are a regex generator. Output ONLY a valid Python regex pattern. Nothing else. No explanation. No markdown. No backticks. No quotes. Just the raw regex pattern on a single line.

Examples:
- find email addresses → [a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}
- replace all values → [\\s\\S]+
- find names starting with J → \\bJ\\w+(?:\\s\\w+)*\\b
- find numbers → \\b\\d+\\b
- find all text → [\\s\\S]+
- find words starting with capital A → \\bA[a-z]+\\b
- find phone numbers → \\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b

Important: use \\w for word characters, not [A-Z] for case-sensitive matching unless specifically asked."""


# Cache key
def _cache_key(prompt: str) -> str:
    digest = hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:16]
    return f"llm:regex:{digest}"

def generate_regex(prompt: str) -> str:
    cache_key = _cache_key(prompt)

    # Cache hit
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Regex cache hit for prompt: '{prompt[:50]}'")
        return cached

    # Call LLM
    logger.info(f"Calling Gemini for prompt: '{prompt[:50]}'")
    pattern = _call_llm(prompt)

    # Validate
    pattern = _validate_regex(pattern)

    # Cache for configured timeout
    cache.set(cache_key, pattern, timeout=settings.LLM_CACHE_TIMEOUT)
    logger.info(f"Cached regex for prompt: '{prompt[:50]}' → {pattern}")

    return pattern

# LLM call
def _call_llm(prompt: str) -> str:
    """Call Llama 3.1 8B via HuggingFace Inference API."""
    
    client = InferenceClient(
        api_key=settings.HUGGINGFACE_API_KEY,
    )
    
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        max_tokens=128,
    )

    pattern = response.choices[0].message.content

    return _clean_response(pattern)

def _clean_response(raw: str) -> str:
    text = raw.strip()
    text = text.strip("`").strip("'\"")

    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    # Handle sed-style output like s/pattern/replace/g
    if text.startswith("s/"):
        parts = text.split("/")
        if len(parts) >= 3:
            text = parts[1]

    # Take only the first non-empty line that looks like a regex
    for line in text.splitlines():
        line = line.strip().strip("`'\"")
        if not line:
            continue
        if any(line.lower().startswith(w) for w in [
            "here", "the", "this", "note", "output", "result",
            "regex:", "pattern:", "s/", "g/"
        ]):
            continue
        return line

    return text.splitlines()[0].strip() if text else text


# Patterns that indicate backtracking risk
_DANGEROUS_PATTERNS = [
    r"\(\.\*\)\+",
    r"\(\.\+\)\+",
    r"\(\.\*\)\*",
    r"\(.*\+.*\)\+",
]

_MAX_PATTERN_LENGTH = 500

def _validate_regex(pattern: str) -> str:
    if not pattern:
        raise ValueError("LLM returned an empty regex pattern.")

    if len(pattern) > _MAX_PATTERN_LENGTH:
        raise ValueError(
            f"LLM returned a suspiciously long pattern ({len(pattern)} chars)."
        )

    for d in _DANGEROUS_PATTERNS:
        if re.search(d, pattern):
            raise ValueError(
                f"LLM returned a pattern with backtracking risk: {pattern}"
            )

    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"LLM returned an invalid regex pattern: {e}") from e

    return pattern