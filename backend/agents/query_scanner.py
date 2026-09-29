"""Prompt-injection detection — query scanner.

Scans a user's query for common prompt-injection patterns before it enters
the retrieval pipeline. This is a defense-in-depth layer: it does not block
queries (the permission system is the real guard), but it flags suspicious
queries in the audit trail so security teams can review them.

The scanner is deliberately conservative — it looks for explicit injection
patterns, not for "suspicious" queries. False positives are worse than false
negatives here because we're auditing, not blocking.

Pattern categories:
- Instruction override: "ignore previous instructions", "disregard the above"
- Role hijacking: "you are now", "act as", "pretend you are"
- System prompt leakage: "repeat your system prompt", "show your instructions"
- delimiter injection: "system:", "assistant:", "<|im_start|>"
- Data exfiltration: "output all", "list everything", "dump the database"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class InjectionReport:
    """Result of scanning a query for prompt injection.

    Attributes:
        suspicious: True if any injection pattern was detected.
        patterns: The matched patterns that triggered suspicion.
        risk_level: "none", "low", or "high" based on pattern severity.
        query: The original query (for audit context).
    """

    suspicious: bool
    patterns: list[str] = field(default_factory=list)
    risk_level: str = "none"
    query: str = ""


# --- Injection patterns -------------------------------------------------

#: Patterns that attempt to override the LLM's instructions.
_OVERRIDE_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(the\s+)?(above|previous|prior|all)",
    r"forget\s+(your|the)\s+(instructions?|rules?|system)",
    r"override\s+(your|the|all)\s+(instructions?|rules?)",
    r"new\s+instructions?:",
]

#: Patterns that attempt to hijack the LLM's role.
_ROLE_PATTERNS = [
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"act\s+as\s+(a|an|the)\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"roleplay\s+as\s+",
    r"from\s+now\s+on\s+you\s+(are|will)",
]

#: Patterns that attempt to leak the system prompt.
_LEAK_PATTERNS = [
    r"(repeat|show|display|reveal|print)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|guidelines?)",
    r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?|rules?)",
    r"output\s+your\s+(system\s+)?prompt",
]

#: Patterns that inject fake system/assistant messages.
_DELIMITER_PATTERNS = [
    r"\bsystem\s*:",
    r"\bassistant\s*:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[system\]",
    r"\[assistant\]",
]

#: Patterns that attempt data exfiltration.
_EXFIL_PATTERNS = [
    r"(output|list|show|dump|print|reveal)\s+(all|every|everything)",
    r"dump\s+(the\s+)?database",
    r"(show|list)\s+(all\s+)?(restricted|confidential|denied)",
]

#: All patterns compiled for efficiency.
_ALL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("override", re.compile("|".join(_OVERRIDE_PATTERNS), re.IGNORECASE), "high"),
    ("role_hijack", re.compile("|".join(_ROLE_PATTERNS), re.IGNORECASE), "high"),
    ("prompt_leak", re.compile("|".join(_LEAK_PATTERNS), re.IGNORECASE), "high"),
    ("delimiter_injection", re.compile("|".join(_DELIMITER_PATTERNS), re.IGNORECASE), "medium"),
    ("data_exfiltration", re.compile("|".join(_EXFIL_PATTERNS), re.IGNORECASE), "medium"),
]


class QueryScanner:
    """Scans user queries for prompt-injection patterns.

    Usage::

        report = scanner.scan(user_query)
        if report.suspicious:
            # log to audit trail, don't block the query
            audit_reason += f" [injection_suspected:{report.risk_level}]"
    """

    def scan(self, query: str) -> InjectionReport:
        """Scan a query for injection patterns.

        Returns an InjectionReport. Never raises — the scanner is a
        defense-in-depth layer, not a gate. If scanning fails, the report
        is "not suspicious".
        """
        if not query or not query.strip():
            return InjectionReport(suspicious=False, query=query)

        matched_patterns: list[str] = []
        max_risk = "none"

        for name, pattern, risk in _ALL_PATTERNS:
            if pattern.search(query):
                matched_patterns.append(name)
                if risk == "high":
                    max_risk = "high"
                elif risk == "medium" and max_risk != "high":
                    max_risk = "medium"

        return InjectionReport(
            suspicious=len(matched_patterns) > 0,
            patterns=matched_patterns,
            risk_level=max_risk,
            query=query,
        )