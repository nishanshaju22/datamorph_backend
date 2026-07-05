import re
import hashlib
from django.conf import settings
from django.core.cache import cache
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.messages import HumanMessage, SystemMessage
from huggingface_hub import InferenceClient

# Prompt
SYSTEM_PROMPT = """You are a deterministic regex compiler for data transformation in CSV/Excel pipelines.

Your task is to convert a natural language instruction into EXACTLY ONE regex pattern suitable for:
- Python `re`
- Java/Spark `regexp_replace`

---

## OUTPUT RULES (STRICT)

- Return ONLY the regex pattern
- No explanations
- No markdown
- No quotes
- No backticks
- No alternatives or multiple patterns
- Output must be a single line regex

---

## NUMERIC LOGIC RULE (CRITICAL)

If the user requests numeric properties such as:
- odd numbers
- even numbers
- multiples of N
- ranges

You MUST implement the logic using the correct numeric principle:

Odd numbers → last digit is [13579]
Even numbers → last digit is [02468]

Do NOT use empty lookaheads like (?!)
Do NOT generate syntactically valid but logically meaningless patterns

## CORE PRINCIPLE

You are NOT generating a "best guess pattern".

You are translating constraints into a regex.

Every meaningful part of the user request MUST be represented in the output.

If any constraint is missing, the output is INVALID.

---

## FIELD-AWARE MATCHING (IMPORTANT)

The input data may represent structured fields such as:
- email addresses
- URLs
- names
- IDs
- numbers
- free text
- mixed CSV columns

You MUST treat values as structured strings, not generic text.

If a constraint applies to part of a structured value:
apply it ONLY to that part.

Examples:
- "starts with X" → applies to start of the VALUE (or local component if structured)
- "ends with X" → applies to end of the VALUE (or local component if structured)
- "contains X" → must be enforced explicitly
- "exact match" → full anchoring required

---

## CONSTRAINT ENFORCEMENT RULE

You MUST encode ALL constraints from the prompt.

Never ignore or generalise constraints.

If the user specifies:
- starting pattern
- ending pattern
- prefix/suffix
- specific substring requirement

Then the regex MUST reflect it explicitly.

---

## STRUCTURED VALUE RULE

When matching structured formats (emails, URLs, identifiers, etc.):

- Preserve structure
- Do NOT replace structured regex with generic catch-all patterns
- Apply constraints only to the relevant segment of the structure
- Do NOT lose positional meaning (start/end applies to correct segment)

---

## REGEX QUALITY RULES

- Prefer simplest correct regex
- Avoid catastrophic backtracking
- Avoid unnecessary capturing groups
- Use non-capturing groups (?:...) when grouping is needed
- Escape special characters properly
- Ensure compatibility with Java/Spark regex

---

## ANCHORING RULES

Use anchors when implied or explicit:

- "starts with" → must use ^ or equivalent positional constraint
- "ends with" → must use $ or equivalent positional constraint
- word boundaries (\b) only when appropriate
- Do NOT overuse \b if it breaks structural correctness

Anchoring must NEVER be omitted when explicitly required by the instruction.

---

## VALIDATION CHECK (INTERNAL BEFORE OUTPUT)

Before returning a regex:

1. Identify target field (what is being matched)
2. Identify all constraints (start, end, contains, pattern rules)
3. Verify every constraint is represented in regex
4. Reject generic patterns that ignore constraints
5. Ensure regex matches full intended value scope

If validation fails, regenerate before output.

---

## EXAMPLES

User:
find email addresses

Output:
\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b

---

User:
find emails that start with b

Output:
\b[bB][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b

---

User:
find words starting with J

Output:
\bJ\w*\b

---

User:
find values ending with ing

Output:
\b\w*ing\b

---

User:
find IDs that start with ABC and end with 99

Output:
\bABC[A-Za-z0-9]*99\b

---

REMEMBER:
Return exactly one valid regex. Nothing else.
"""


# Cache key
def _cache_key(prompt: str) -> str:
    digest = hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:16]
    return f"llm:regex:{digest}"

def generate_regex(prompt: str) -> str:
    cache_key = _cache_key(prompt)

    # Cache hit
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Call LLM
    pattern = _call_llm(prompt)

    # Validate
    pattern = _validate_regex(pattern)

    # Cache for configured timeout
    cache.set(cache_key, pattern, timeout=settings.LLM_CACHE_TIMEOUT)

    return pattern

# LLM call
def _call_llm(prompt: str) -> str:
    """Call Llm HuggingFace Inference API."""
    client = InferenceClient(
        api_key=settings.HUGGINGFACE_API_KEY,
    )
    
    response = client.chat.completions.create(
        model=settings.MODEL,
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