# 3. Hybrid retrieval, a trained decision to answer, and models routed by classification

## Context

German policy texts and the way employees ask about them differ: compounds ("Hotelübernachtung" /
"Übernachtungskosten"), participles, abbreviations, colloquial chat around the question. The
system must answer when the paragraph is there and decline when it is not: in a bank, a wrong
limit is worse than no answer. Some content may not go to an external model at all.

## Decision

- **Retrieval:** two paths under the user's rights and the date filter: German full-text search
  (`to_tsvector('german')`) and nearest neighbours on a local embedding (signed feature hashing of
  character n-grams; no model download, deterministic, matches compounds). Ranks are fused and
  re-scored by how much of the question a paragraph covers (IDF-weighted, Snowball stems,
  compound-aware matching), whether it states the kind of value asked for (amount, deadline,
  time, frequency, role) and whether its document contains the question's rarest noun. A small
  thesaurus maps colloquial terms to policy vocabulary.
- **Deciding to answer:** a logistic model over these features scores each evidence paragraph;
  the best one is used if it clears a threshold. Weights and threshold are trained offline on
  labelled questions (`python -m copilot_sim train-answerability`) and stored in
  `config/answerability.json`; the threshold is the lowest at which wrong answers stay within 2 %
  of questions in cross-validation. Scoring at runtime is a dot product.
- **Answering:** the extractive answerer quotes the paragraph and invents nothing. If a language
  model is configured (Claude, Azure OpenAI), it writes a short answer from the evidence; every
  number in it must appear in the cited paragraph, otherwise the quote is shown instead.
- **Routing:** `config/models.yaml` says which model may see which classification and where it
  runs. The most sensitive evidence paragraph decides; streng vertraulich never leaves the
  process. Personal data (IBAN, e-mail, phone, customer numbers) is removed from the question
  before it is stored or sent anywhere.

## Consequences

- Without any API key the system works fully (and is what the evaluation measures). With a key,
  the same verification guards the model's answer.
- Retrieval recall is high (the right paragraph is among the evidence for 97.5 % of the second
  blind set's answerable questions); most misses are declines, not wrong answers. A language
  model reading the evidence is the obvious next step to close that gap, behind the same verifier.
- The embedding is replaceable (`Embedder` protocol) by a hosted multilingual model when one is
  approved for the data.
