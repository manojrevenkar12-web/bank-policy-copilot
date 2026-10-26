# Research behind the design

Notes from the research done before building, and what each source changed.

- **Temporal correctness.** Recent work shows that retrieval over versioned legal and regulatory
  corpora often cites provisions that were no longer, or not yet, in force:
  - "Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark for French Tax Law"
    (arXiv 2608.09393)
  - TimelyRAG (arXiv 2609.11572)
  - Neo4j's talk on "preventing RAG systems from citing dead regulations"

  This led to validity intervals on every paragraph, the date filter in SQL, and evaluation
  questions about past dates (ADR 2).
- **Access control in vector search.** Post-retrieval filtering lets the model see what the user
  may not. Row-level security with per-request session settings is the pattern for complex
  role-based rules; pooled connections must not carry settings over:
  - tianpan.co, "Vector Store Access Control: The Row-Level Security Problem Most RAG Teams Skip"
  - dev.to, "Permission-aware RAG: what it really costs"

  This led to transaction-local settings and rights taken from the users table (ADR 1).
- **Compliant RAG in German financial institutions.** BAIT and DORA expect tamper-evident audit
  trails, treat external model APIs as third-party ICT providers, and call for an approved model
  registry with data residency (Kiteworks, "Best Practices for Compliant RAG in German Financial
  Institutions"). This led to the hash chain (ADR 4) and the model registry with classification
  ceilings (ADR 3).
- **Structure of German supervisory texts.** MaRisk and its circulars are modular and numbered
  by Textziffer (Tz.), and banks implement them in internal policies that cite them
  (Bundesbank, MaRisk publications). This led to Tz.-level paragraphs and the impact detection
  for changed circulars (ADR 5).
- **What other applicants build.** Public RAG portfolio projects are mostly "chat with your PDFs"
  (LangChain, Chroma or FAISS, Streamlit). They have no dates, no rights, no evaluation against
  known answers, and no deployment.
