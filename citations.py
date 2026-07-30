"""
Citation extraction for the Institutional Memory Agent.

The Managed Agents sessions API has no native citation support: a
`document` block accepts no `citations` config, and `agent.message` content is
plain text blocks with no citation metadata (verified against anthropic
0.120.2). So citations are produced at the prompt layer — the agent is
instructed to tag claims with `[[cite: <source>]]` — and parsed back out here
into structured data the front end can render.

Sources are either a document filename from synthetic-data/ or a memory path
under /mnt/memory/, which is what makes the demo legible: you can see which
answers came from new documents and which came from remembered knowledge.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Matches [[cite: onboarding-handbook.md]] and [[cite: /mnt/memory/policies.md]]
CITE_PATTERN = re.compile(r"\[\[\s*cite\s*:\s*([^\]]+?)\s*\]\]", re.IGNORECASE)

CITATION_INSTRUCTIONS = """\
# Citations (mandatory)

Every factual claim in your answer MUST carry an inline citation marker in
exactly this format:

    [[cite: <source>]]

Where `<source>` is either:
  - the document filename you took the fact from, e.g. [[cite: access-policy.md]]
  - the memory file path, e.g. [[cite: /mnt/memory/policies.md]]

Rules:
- Put the marker immediately after the sentence or bullet it supports.
- Cite the memory path when the fact came from memory, and the filename when it
  came from a document provided in this session.
- If a claim is supported by both, emit both markers.
- Never invent a source. If you cannot attribute a claim, say so plainly
  instead of citing.
"""


def _classify(source: str) -> str:
    if source.startswith("/mnt/memory"):
        return "memory"
    if source.lower().endswith(".md"):
        return "document"
    return "other"


def extract_citations(text: str) -> list[dict[str, Any]]:
    """Pull citation markers out of answer text, deduped, in order of appearance."""
    citations: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    for match in CITE_PATTERN.finditer(text or ""):
        source = " ".join(match.group(1).split())
        if not source:
            continue

        existing = seen.get(source)
        if existing is not None:
            existing["count"] += 1
            continue

        citation = {
            "source": source,
            "kind": _classify(source),
            "count": 1,
            "index": len(citations) + 1,
        }
        seen[source] = citation
        citations.append(citation)

    return citations


def strip_markers(text: str) -> str:
    """Remove citation markers, leaving readable prose."""
    cleaned = CITE_PATTERN.sub("", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:])", r"\1", cleaned)
    return "\n".join(line.rstrip() for line in cleaned.splitlines())


def build_payload(text: str) -> dict[str, Any]:
    """Return the citation-aware answer payload consumed by the UI."""
    citations = extract_citations(text)
    return {
        "answer": strip_markers(text),
        "answer_with_markers": text or "",
        "citations": citations,
        "has_citations": bool(citations),
    }


def collect_answer(events: Iterable[Any]) -> str:
    """Concatenate text from `agent.message` events in a session stream."""
    parts: list[str] = []
    for event in events:
        if getattr(event, "type", None) != "agent.message":
            continue
        for block in getattr(event, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
    return "".join(parts)


def format_citation_list(citations: list[dict[str, Any]]) -> str:
    """Render citations as a numbered list for the saved transcript."""
    if not citations:
        return "(none — the agent did not attribute its claims)"
    return "\n".join(
        f"[{item['index']}] {item['source']}  ({item['kind']}, {item['count']}x)"
        for item in citations
    )
