# Working in this repository

Fast feedback:

- `cd backend && ruff check src tests && mypy && pytest -q`. The db tests need PostgreSQL with
  pgvector: set `COPILOT_TEST_ADMIN_URL`, default `postgresql://postgres:postgres@localhost:5432/postgres`.
- `cd web && npm run lint && npm run typecheck && npm test`.
- `python -m copilot_sim seed`, then `python -m copilot_sim evaluate && python -m copilot_sim gate`,
  then Playwright against the running stack.

Invariants (each has a test):

- Rights are enforced by Postgres before retrieval. Request code runs in `as_user`; ingestion,
  evaluation and training run in `as_system`. Never retrieve and filter afterwards, and never
  take rights from the token or the request.
- A paragraph is evidence only if it was in force on the asked date.
- The extractive answerer never writes text that is not in the paragraph. A language model's
  answer is shown only if every number in it is in a cited paragraph.
- No content above a model's `max_classification` (`config/models.yaml`) is sent to it. Personal
  data is redacted before storage and model calls.
- The audit trail is append-only for the app role and hash-chained.
- The platform package `copilot` never imports `copilot_sim`, never reads its questions, and
  never mentions the blind sets (`tests/test_isolation.py`).
- Thresholds, vocabulary and the model registry live in `config/`.

Held-out rule: never change normalisation, retrieval, answering or the answerability model to do
better on `copilot_sim/blind/questions.json`. Its first run is `reports/blind/FIRST_RUN.json` and
is never rewritten. If you study its failures, move it to `copilot_sim/regression/` (as was done
with v1) and have someone who has not seen the code write a new set from `blind/BRIEF.md` only.
The answerability model trains on the dev and regression sets only.
