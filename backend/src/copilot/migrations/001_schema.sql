-- Documents, their versions and paragraphs; who may read them; what was asked and answered.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
  login      text PRIMARY KEY,
  name       text NOT NULL,
  title      text NOT NULL DEFAULT '',
  clearance  int  NOT NULL CHECK (clearance BETWEEN 1 AND 4),
  groups     text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id             bigserial PRIMARY KEY,
  doc_key        text NOT NULL UNIQUE,          -- "RL-ZV-01", "AM 2/2024"
  title          text NOT NULL,
  kind           text NOT NULL CHECK (kind IN ('policy', 'circular')),
  source         text NOT NULL,                 -- dms | wiki | regulatory-feed
  classification int  NOT NULL CHECK (classification BETWEEN 1 AND 4),
  read_groups    text[] NOT NULL,
  owner          text,
  references_    text[] NOT NULL DEFAULT '{}',
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE document_versions (
  id          bigserial PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES documents (id),
  version     int  NOT NULL,
  valid_from  date NOT NULL,
  valid_to    date,                             -- set when the next version arrives
  file_name   text NOT NULL,
  file_sha256 text NOT NULL,
  paragraphs  int  NOT NULL,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

CREATE TABLE paragraphs (
  id             bigserial PRIMARY KEY,
  version_id     bigint NOT NULL REFERENCES document_versions (id),
  doc_key        text NOT NULL,
  version        int  NOT NULL,
  tz             text NOT NULL,
  section        text NOT NULL,
  is_history     boolean NOT NULL DEFAULT false,
  text           text NOT NULL,
  text_hash      text NOT NULL,
  -- copied from the document and its version so that retrieval filters in one place
  valid_from     date NOT NULL,
  valid_to       date,
  classification int  NOT NULL,
  read_groups    text[] NOT NULL,
  tsv            tsvector GENERATED ALWAYS AS (
                   setweight(to_tsvector('german', section), 'B') || setweight(to_tsvector('german', text), 'A')
                 ) STORED,
  embedding      vector(384) NOT NULL,
  UNIQUE (version_id, tz)
);
CREATE INDEX paragraphs_tsv ON paragraphs USING gin (tsv);
CREATE INDEX paragraphs_embedding ON paragraphs USING hnsw (embedding vector_cosine_ops);
CREATE INDEX paragraphs_validity ON paragraphs (valid_from, valid_to);
CREATE INDEX paragraphs_doc ON paragraphs (doc_key, version);

-- Every question, the evidence it was answered from, and a hash chain that makes edits visible.
CREATE TABLE queries (
  id           bigserial PRIMARY KEY,
  at           timestamptz NOT NULL DEFAULT now(),
  login        text NOT NULL REFERENCES users (login),
  question     text NOT NULL,                  -- after redaction of personal data
  as_of        date NOT NULL,
  outcome      text NOT NULL CHECK (outcome IN ('answered', 'no_answer')),
  answer       text NOT NULL,
  model        text NOT NULL,
  evidence     bigint[] NOT NULL,              -- paragraph ids the answerer saw
  citations    bigint[] NOT NULL,
  trace        jsonb NOT NULL,                 -- stage timings, scores, router decision, tokens, cost
  prev_hash    text NOT NULL,
  hash         text NOT NULL UNIQUE
);
CREATE INDEX queries_login ON queries (login, at DESC);

CREATE TABLE feedback (
  id          bigserial PRIMARY KEY,
  query_id    bigint NOT NULL REFERENCES queries (id),
  login       text NOT NULL REFERENCES users (login),
  helpful     boolean NOT NULL,
  comment     text NOT NULL DEFAULT '',
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
  resolution  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  UNIQUE (query_id, login)
);

-- A supervisory circular changed: which internal paragraphs implement it and need a look.
CREATE TABLE impact_items (
  id            bigserial PRIMARY KEY,
  circular      text NOT NULL,
  from_version  int  NOT NULL,
  to_version    int  NOT NULL,
  circular_tz   text NOT NULL,
  change        text NOT NULL,                 -- old -> new text of the circular paragraph
  doc_key       text NOT NULL,
  paragraph_id  bigint NOT NULL REFERENCES paragraphs (id),
  reason        text NOT NULL,                 -- explicit reference | similar wording
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
  note          text,
  detected_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (circular, to_version, circular_tz, paragraph_id)
);

CREATE TABLE ingestion_runs (
  id          bigserial PRIMARY KEY,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  files       int NOT NULL DEFAULT 0,
  new_versions int NOT NULL DEFAULT 0,
  unchanged   int NOT NULL DEFAULT 0,
  rejected    jsonb NOT NULL DEFAULT '[]'
);
