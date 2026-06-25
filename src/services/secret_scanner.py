import math
import re
from typing import Any

_SKIP_WORDS = {"test", "fake", "example", "placeholder", "dummy", "sample", "mock"}

# Strict patterns match highly-specific formats — no skip filter applied.
_STRICT_PATTERNS: list[tuple[str, str]] = [
    ("aws_key", r"AKIA[0-9A-Z]{16}"),
    ("aws_secret", r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]"),
    ("github_token", r"gh[pso]_[A-Za-z0-9]{36,255}"),
    ("slack_token", r"xox[baprs]-[0-9A-Za-z\-]{10,48}"),
    ("stripe_key", r"sk_(live|test)_[0-9a-zA-Z]{24,}"),
    ("private_key_header", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("jwt_token", r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),
]

# Broad patterns match assignment syntax — skip filter IS applied to reduce FPs.
_BROAD_PATTERNS: list[tuple[str, str]] = [
    ("generic_api_key", r"(?i)(api[_\-]?key|apikey)\s*[:=]\s*['\"][0-9a-zA-Z\-_]{20,}['\"]"),
]


def shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character. English prose ≈3.5; secrets ≈5.5+."""
    if not s:
        return 0.0
    entropy = 0.0
    length = len(s)
    for char in set(s):
        prob = s.count(char) / length
        entropy -= prob * math.log2(prob)
    return entropy


def _should_skip(candidate: str) -> bool:
    lower = candidate.lower()
    return any(word in lower for word in _SKIP_WORDS)


def scan_for_secrets(diff_text: str) -> list[dict[str, Any]]:
    """Scan a diff for secrets using regex patterns + Shannon entropy."""
    findings: list[dict[str, Any]] = []

    # Strict patterns — no skip filter; format is specific enough.
    for secret_type, pattern in _STRICT_PATTERNS:
        for match in re.finditer(pattern, diff_text):
            value = match.group()
            line_num = diff_text[: match.start()].count("\n") + 1
            findings.append({"type": secret_type, "value": value[:60], "line": line_num})

    # Broad patterns — apply skip filter to avoid obvious test fixtures.
    for secret_type, pattern in _BROAD_PATTERNS:
        for match in re.finditer(pattern, diff_text):
            value = match.group()
            if _should_skip(value):
                continue
            line_num = diff_text[: match.start()].count("\n") + 1
            findings.append({"type": secret_type, "value": value[:60], "line": line_num})

    # Entropy-based detection (candidates ≥20 chars, entropy >4.5)
    for line_num, line in enumerate(diff_text.splitlines(), start=1):
        candidates = re.findall(r"[a-zA-Z0-9+/=_\-]{20,}", line)
        for candidate in candidates:
            if _should_skip(candidate):
                continue
            entropy = shannon_entropy(candidate)
            if entropy > 4.5:
                # Skip if already captured by a pattern match on this line
                already_found = any(
                    f["line"] == line_num and candidate[:30] in f["value"] for f in findings
                )
                if not already_found:
                    findings.append(
                        {
                            "type": "high_entropy",
                            "value": candidate[:60],
                            "line": line_num,
                            "entropy": round(entropy, 3),
                        }
                    )

    return findings
