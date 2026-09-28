"""Context assembler.

Assembles authorized resources (the output of the permission filter) into a
single bounded context string for the LLM, with citation markers. Because it
only ever receives already-authorized resources, the assembler cannot leak
restricted content — it is a formatting step, not an authorization step.

The assembler also emits the list of citable resource IDs so a later stage
(the answer agent, M6) can validate that every citation in the generated
answer corresponds to an authorized resource (INV6: NoUnauthorizedCitation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.retrieval.permission_filter import FilteredCandidate

DEFAULT_MAX_CHARS = 8000


@dataclass
class Citation:
    """A citable source included in the assembled context."""

    marker: str          # e.g. "[1]"
    resource_id: str
    source: str
    title: str


@dataclass
class AssembledContext:
    """The LLM-ready context plus citation metadata.

    Attributes:
        text: The concatenated, citation-marked context string.
        citations: Ordered citations, one per included resource.
        included_resource_ids: The resource IDs the LLM may cite.
        truncated: True if the context budget was exhausted and one or more
            authorized resources were omitted.
    """

    text: str
    citations: list[Citation] = field(default_factory=list)
    included_resource_ids: list[str] = field(default_factory=list)
    truncated: bool = False

    def is_authorized_citation(self, resource_id: str) -> bool:
        """Return True iff the resource_id was actually included (INV6)."""
        return resource_id in self.included_resource_ids


class ContextAssembler:
    """Assembles authorized content into a bounded, cited context window."""

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS):
        self._max_chars = max_chars

    def assemble(self, allowed: list[FilteredCandidate]) -> AssembledContext:
        """Assemble allowed candidates into a cited context string.

        Resources are included in the order given (the caller is expected to
        pass them ranked by relevance). Inclusion stops when the character
        budget is exhausted; remaining resources are omitted and `truncated`
        is set. Each included resource gets a numbered citation marker.
        """
        blocks: list[str] = []
        citations: list[Citation] = []
        included_ids: list[str] = []
        used = 0
        truncated = False

        for candidate in allowed:
            resource = candidate.resource
            marker = f"[{len(citations) + 1}]"
            header = f"{marker} {resource.source.value}:{resource.resource_id} — {resource.title}"
            block = f"{header}\n{resource.content}\n"

            if used + len(block) > self._max_chars and blocks:
                # Budget exhausted and we already have at least one block.
                truncated = True
                break

            blocks.append(block)
            used += len(block)
            citations.append(
                Citation(
                    marker=marker,
                    resource_id=resource.resource_id,
                    source=resource.source.value,
                    title=resource.title,
                )
            )
            included_ids.append(resource.resource_id)

        return AssembledContext(
            text="\n".join(blocks),
            citations=citations,
            included_resource_ids=included_ids,
            truncated=truncated,
        )
