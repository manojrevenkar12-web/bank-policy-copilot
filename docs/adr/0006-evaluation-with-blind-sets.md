# 6. Measured against a simulated bank, with blind question sets nobody tunes against

## Context

Plausible-looking answers are not evidence. Real bank policies with known correct answers are not
available, and a system tuned on the questions it is tested on looks better than it is.

## Decision

- `copilot_sim` simulates Havelsee Bank AG (invented): 21 policies and 2 supervisory circulars,
  2 to 3 versions each with dates of effect, classifications and audiences, 9 employees with
  different rights; exported as Word, PDF and wiki HTML. The truth (which value each rule had on
  each date, in which paragraph) lives only in `copilot_sim`; a test fails if the platform
  package mentions it.
- **dev questions** are generated from the truth and used while building.
- **Blind sets** are written by an author who reads only `blind/BRIEF.md` and the documents (never
  the code): 120 questions each, including look-alike rules, questions by users without access,
  topics no policy covers, and dates before a policy existed.
- The first run of a blind set is kept in `reports/.../FIRST_RUN.json` and never rewritten. When
  its failures are studied to improve the system, it becomes a regression set and a new blind set
  is written.

## What happened

Blind set v1, first run: 78.3 % of questions handled correctly, 5 wrong answers, 0 leaks. Its
failures (mostly declines on conversational wording) were studied; v1 became a regression set and
trained, with the dev questions, the answerability model. Blind set v2, written afterwards, first
run: 81.7 % handled correctly (76.3 % of answerable questions answered right, 92.5 % of
unanswerable ones declined), 6 wrong answers among 67 given, 0 leaks.
