# 2. Every answer is "as of" a date, from the version in force on that date

## Context

Bank policies change: limits go down, deadlines get shorter, supervisory circulars are revised.
An auditor asks what applied in March 2024; a clerk asks what applies today. Retrieval that
ignores validity returns a mix of versions, and a policy's change history repeats old and new
values side by side, which is where a careless system finds the wrong number.

## Decision

- Each document version has `valid_from` (its date of effect, parsed from the header) and
  `valid_to` (the next version's date of effect, recomputed whenever a version arrives, also
  late or out of order). Paragraphs carry the same interval.
- Retrieval filters on `valid_from <= as_of < valid_to` in SQL. Before a policy's first version,
  there is nothing to answer from.
- Paragraphs of a change history are recognised by their section title and rank lower, unless the
  question asks what changed.
- If the cited paragraph reads differently today, the answer says so and quotes the current
  wording ("Heute gilt eine neue Fassung").
- The web app shows the versions of the cited policy as a band on a time axis with the chosen
  date as a marker.

## Consequences

- The evaluation asks half of its questions about past dates and checks the version of the cited
  paragraph, not only the value.
