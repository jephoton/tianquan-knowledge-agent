# ADR-0008: Match explicit report labels exactly

<!-- Generated decision record. -->

**Status:** Accepted

## Context

“Show me the Q5 report” returned the existing Q3 report because generic
“report” matched while the missing Q5 token contributed no exact score.
This made an absent report look like an accessible result for a different period.

## Decision

Treat tokens of the form `q` followed by digits as explicit report labels.
A candidate must contain at least one requested label as an exact token in
its title or content before normal scoring. Multiple labels support comparison
queries. Unlabelled queries keep the existing search behavior; source names
remain ranking boosts (ADR-0006). Permission checks still run independently.

## Consequences

Q5 never fuzzy-matches Q3 or Q50; no matching label produces the existing
canonical no-access/no-results response, without invoking the answer model.
This checks literal labels, not calendar validity or synonymous date formats.
A document referring to a label only through other wording will not match an
explicit labelled query. Tests cover the Bob/Charlie demo, exact title/content
matches and comparison queries.
