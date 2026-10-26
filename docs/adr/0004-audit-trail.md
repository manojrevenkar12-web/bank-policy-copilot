# 4. A hash-chained, append-only audit trail of every question and answer

## Decision

Every question (after redaction), date, answer, model, evidence paragraph ids and citations is a
row in `queries`, linked to the previous row by a SHA-256 hash of its content and the previous
hash. Inserts take an advisory lock so the chain never forks. The app role may insert but not
update or delete. `GET /api/audit/verify` (Internal Audit only) recomputes the chain and names
the first broken link.

## Consequences

`tests/test_api.py` edits a stored answer as the database owner and checks that verification
points at that row. Questions a user may not read never enter the trail as evidence, because they
were never retrieved (ADR 1).
