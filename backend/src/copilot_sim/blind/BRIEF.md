# Writing blind questions for the policy copilot

You are an employee of Havelsee Bank AG (an invented bank) writing test questions for an internal
assistant that answers questions about the bank's policies. You have the bank's policy documents
as Markdown in the folder you are given (every version of every policy, plus two supervisory
circulars). Read the documents. Do not read anything else: no code, no other files.

Each document's header gives its number, version, the date it took effect ("Gültig ab") and its
classification. A version is in force from its "Gültig ab" date until the next version's date.

## Who may read what

| login | role | departments | clearance |
| --- | --- | --- | --- |
| lena.vogt | Sachbearbeiterin Zahlungsverkehr | Zahlungsverkehr | intern |
| tobias.kern | Kreditanalyst | Kreditgeschäft | vertraulich |
| miriam.haas | Compliance-Beauftragte | Compliance | streng vertraulich |
| jan.reuter | IT-Sicherheitsbeauftragter | IT und Informationssicherheit | vertraulich |
| aylin.demir | Kundenberaterin | Vertrieb | intern |
| felix.brandt | Händler Treasury | Treasury | streng vertraulich |
| sophie.lange | Referentin Personal | Personal | intern |
| paul.neumann | Auszubildender | Vertrieb | öffentlich |
| greta.wolf | Prüferin Interne Revision | Interne Revision | streng vertraulich |

A user may read a document only if (a) their clearance is at least the document's classification
(öffentlich < intern < vertraulich < streng vertraulich) and (b) the document applies to all staff
or to one of the user's departments (paragraph 1.2 "Sie gilt für ..." says which). Greta Wolf
(Interne Revision) may read every department's documents, still within her clearance.

## What to write

Write 120 questions in German, as different employees would actually ask them: short and long,
colloquial and formal, with words the documents don't use, with typos now and then. Each question
is asked by one user on one date ("as_of"), and the right answer is what the policy in force on
that date says.

Mix:

- 60 questions with an answer the user may read, spread over all policies; about half asked on a
  past date where an older version was in force, the rest on a date in 2026.
- 15 questions that look alike but belong to different rules or policies (e.g. two different
  amount limits for the same kind of thing), so only the right paragraph answers them.
- 15 questions asked by a user who may NOT read the policy that holds the answer. Expected
  outcome: no answer.
- 15 questions about things no document covers (but that sound like they could be). Expected: no
  answer.
- 10 questions asked on a date before the first version of the policy was in force. Expected: no
  answer.
- 5 questions that only the supervisory circulars answer (anyone may read those).

Do not ask what changed between versions; ask what applied on the date.

## Format

Write a JSON array to the output file you are given, each item:

```json
{
  "id": "b001",
  "user": "lena.vogt",
  "as_of": "2024-02-15",
  "question": "…",
  "expect": "answer",
  "value": "15.000 EUR",
  "doc_no": "RL-ZV-01",
  "version": 2,
  "tz": "2.1",
  "kind": "past"
}
```

- `expect` is `"answer"` or `"no_answer"`. For `no_answer`, leave `value`, `doc_no`, `version` and
  `tz` as null (for the permission cases, give the document that holds the answer in `doc_no` and
  the value in `value`, so the test can check the value does not leak).
- `value` is copied exactly as it appears in the paragraph (e.g. "15.000 EUR", "16:00",
  "3 Kalendertagen", "ein Mitglied der Geschäftsleitung").
- `tz` is the paragraph number without "Tz." (e.g. "2.1"); for circulars, `doc_no` is the circular's
  reference (e.g. "AM 2/2024") and `tz` its number.
- `kind` is one of: current, past, lookalike, no_access, not_covered, before_first, circular.
- Never take the value from the change-history section; take it from the rule's own paragraph.
