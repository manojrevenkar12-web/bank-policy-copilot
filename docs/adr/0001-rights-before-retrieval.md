# 1. Access rights are enforced by Postgres before retrieval, not filtered afterwards

## Context

A policy copilot in a bank answers from documents with different classifications (öffentlich to
streng vertraulich) and audiences (one department, several, everyone). The common failure in
retrieval-augmented generation is to retrieve first and filter later: the model has already
read the paragraph, citations and logs leak it, and a bug in the filter leaks silently.

## Decision

- Every paragraph carries its document's classification and read groups (from the document
  management system's permission export, not from the document text). Row-level security on
  `paragraphs`, `documents`, `document_versions`, `queries`, `feedback` and `impact_items` is
  forced for the table owner too.
- Each request runs in a transaction that sets `app.login`, `app.clearance` and `app.groups` with
  `set_config(..., true)` (`copilot/db.py: as_user`). The values come from the `users` table (the
  identity provider's export), never from the token or the request body. A pooled connection
  cannot carry one user's rights into another request.
- Both retrieval paths (full text and vectors) run under these rights, so a paragraph the user may
  not read is never a candidate: not in the evidence, not in a model prompt, not in the trace.
- The app role cannot update or delete the audit trail and cannot bypass row-level security.

## Consequences

- `tests/test_api.py` asks the same question as users with and without access and checks that
  the answer, the citations and the evidence never contain the restricted document. The
  evaluation counts leaks on every question; the release gate fails on any.
- When the header of a document says a stricter classification than the source system, the
  stricter one wins and ingestion records a warning.
- Word statistics used for weighting are computed over all paragraphs (counts only); a
  document's words are only consulted for documents the user could already retrieve.
