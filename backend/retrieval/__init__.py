"""Permission-aware retrieval pipeline for Tianquan.

Pipeline stages (M3):
    indexer          -> snapshot resources from all connectors
    candidate_search -> keyword/token-overlap candidate retrieval (over-fetch)
    permission_filter-> re-fetch live ACLs, filter through the policy engine
    context_assembler-> assemble authorized content into a bounded context

The critical invariant (INV2): the LLM context contains only content the
asker is authorized to see. Filtering happens before assembly, and the
filter always reads the live ACL from the connector, never a stale snapshot.
"""
