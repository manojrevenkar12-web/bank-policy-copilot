/** How the answer came about: retrieval, the model the router chose and why, and timings. */
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { Trace as TraceT } from "../../shared/api/types";
import { motion as m } from "../../shared/theme/tokens";
import { Badge } from "../../shared/ui";
import styles from "./Ask.module.css";

const STAGES: Record<string, string> = {
  prepare: "Vorbereitung",
  fulltext: "Volltextsuche",
  vector: "Vektorsuche",
  rerank: "Bewertung",
  answer: "Antwort",
};

export function Trace({ trace, citedId }: { trace: TraceT; citedId: number | null }) {
  const [open, setOpen] = useState(false);
  const total = Math.max(
    1,
    Object.values(trace.timings_ms).reduce((a, b) => a + b, 0),
  );
  return (
    <section className={styles.trace}>
      <button
        type="button"
        className={styles.traceToggle}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        Wie die Antwort entstand <span className="num">({trace.total_ms.toFixed(0)} ms)</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className={styles.traceBody}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: m.base, ease: m.ease }}
          >
            <dl className={styles.facts}>
              <dt>Modell</dt>
              <dd>
                {trace.router.model} ({trace.router.processing})
              </dd>
              <dt>Begründung</dt>
              <dd>{trace.router.reason}</dd>
              {trace.redacted.length > 0 && (
                <>
                  <dt>Entfernt</dt>
                  <dd>{trace.redacted.join(", ")} vor Speicherung und Modellaufruf</dd>
                </>
              )}
              {trace.notes.length > 0 && (
                <>
                  <dt>Hinweise</dt>
                  <dd>{trace.notes.join("; ")}</dd>
                </>
              )}
              <dt>Kosten</dt>
              <dd className="num">
                {trace.tokens.input + trace.tokens.output} Tokens, {trace.cost_eur.toFixed(4)} EUR
              </dd>
            </dl>
            <div className={styles.timing} aria-label="Zeit je Schritt">
              {Object.entries(trace.timings_ms).map(([k, v]) => (
                <span key={k} style={{ flexGrow: v / total }} title={`${STAGES[k] ?? k}: ${v.toFixed(1)} ms`}>
                  {STAGES[k] ?? k}
                </span>
              ))}
            </div>
            <table className={styles.evidence}>
              <caption>
                Geprüfte Absätze (nur aus Richtlinien, die Sie lesen dürfen und die am Stichtag galten)
              </caption>
              <thead>
                <tr>
                  <th>Fundstelle</th>
                  <th className="num">Volltext</th>
                  <th className="num">Vektor</th>
                  <th className="num">Abdeckung</th>
                  <th>Prüfung</th>
                </tr>
              </thead>
              <tbody>
                {trace.candidates.map((c) => (
                  <tr
                    key={c.paragraph_id}
                    className={c.paragraph_id === citedId ? styles.citedRow : undefined}
                  >
                    <td>
                      {c.doc_key} V{c.version} Tz. {c.tz}
                    </td>
                    <td className="num">{c.fts_rank ?? "–"}</td>
                    <td className="num">{c.vec_rank ?? "–"}</td>
                    <td className="num">{Math.round(c.coverage * 100)} %</td>
                    <td>
                      {c.history && <Badge tone="superseded">Änderungshistorie</Badge>}
                      {!c.answers_kind && <Badge>andere Angabe</Badge>}
                      {!c.anchored && <Badge>anderes Thema</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
