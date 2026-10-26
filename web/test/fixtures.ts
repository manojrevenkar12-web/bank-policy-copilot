import type { AskResult } from "../src/shared/api/types";

export const answered: AskResult = {
  query_id: 7,
  outcome: "answered",
  answer: "Zahlungsaufträge ab einem Betrag von 15.000 EUR sind freizugeben.",
  citations: [
    {
      paragraph_id: 11,
      doc_key: "RL-ZV-01",
      title: "Richtlinie Freigabe und Kontrolle im Zahlungsverkehr",
      version: 2,
      tz: "2.1",
      section: "Freigabe von Zahlungen",
      text: "Zahlungsaufträge ab einem Betrag von 15.000 EUR sind freizugeben.",
      valid_from: "2023-07-01",
      valid_to: "2025-04-01",
      classification: 2,
    },
  ],
  newer: {
    version: 3,
    valid_from: "2025-04-01",
    text: "Zahlungsaufträge ab einem Betrag von 10.000 EUR sind freizugeben.",
  },
  model: "extractive",
  as_of: "2024-02-01",
  trace: {
    timings_ms: { fulltext: 2, vector: 3 },
    total_ms: 9,
    redacted: [],
    expanded_question: "",
    asked: ["amount"],
    router: { model: "extractive", processing: "in process", reason: "x" },
    tokens: { input: 0, output: 0 },
    cost_eur: 0,
    notes: [],
    candidates: [],
  },
};
