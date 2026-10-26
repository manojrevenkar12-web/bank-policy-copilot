import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";

import { api } from "../../shared/api/client";
import type { Evaluation, ModelInfo, SetSummary } from "../../shared/api/types";
import { formatDate } from "../../shared/lib/format";
import { CLASSIFICATION, motion as m } from "../../shared/theme/tokens";
import { Badge, EmptyState, PageHead, QueryState, SkeletonBlock } from "../../shared/ui";
import styles from "./Evaluation.module.css";

type Row = { label: string; note: string; s: SetSummary };

const pct = (x: number | null | undefined) => (x == null ? "–" : `${(x * 100).toFixed(1)} %`);

function Meter({ value, tone }: { value: number; tone: "good" | "bad" }) {
  return (
    <span className={styles.meter} aria-hidden>
      <motion.span
        className={tone === "good" ? styles.good : styles.bad}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, value * 100)}%` }}
        transition={{ duration: m.slow, ease: m.ease }}
      />
    </span>
  );
}

function rows(e: Evaluation): Row[] {
  const out: Row[] = [];
  const fr = e.first_runs ?? {};
  if (fr["blind"])
    out.push({
      label: "Blindtest v2, erster Lauf",
      note: "von jemandem geschrieben, der den Code nie gesehen hat",
      s: fr["blind"],
    });
  if (fr["regression-v1"])
    out.push({
      label: "Blindtest v1, erster Lauf",
      note: "vor der Auswertung seiner Fehler",
      s: fr["regression-v1"],
    });
  if (e.sets["regression-v1"])
    out.push({
      label: "Blindtest v1, heute",
      note: "jetzt Regressionstest, Fehler ausgewertet",
      s: e.sets["regression-v1"],
    });
  if (e.sets["dev"])
    out.push({
      label: "Entwicklungsfragen",
      note: "aus den Regeln erzeugt, beim Bauen genutzt",
      s: e.sets["dev"],
    });
  return out;
}

export function EvaluationPage() {
  const evaluation = useQuery({
    queryKey: ["evaluation"],
    queryFn: () => api.get<Evaluation>("/api/evaluation"),
    retry: false,
  });
  const registry = useQuery({ queryKey: ["models"], queryFn: () => api.get<ModelInfo[]>("/api/models") });
  return (
    <>
      <PageHead
        title="Qualität"
        lede="Wie oft der Copilot richtig antwortet, wie oft er zu Recht keine Antwort gibt, und ob je etwas nach außen dringt, das die fragende Person nicht lesen darf. Gemessen an einer simulierten Bank, deren richtige Antworten bekannt sind."
      />
      <QueryState
        query={evaluation}
        skeleton={<SkeletonBlock lines={6} label="Auswertung wird geladen" />}
        isEmpty={(e) => Object.keys(e.sets).length === 0}
        empty={
          <EmptyState title="Noch keine Auswertung">
            Die Auswertung entsteht mit „python -m copilot_sim evaluate“.
          </EmptyState>
        }
      >
        {(e) => (
          <>
            <table className={styles.table}>
              <caption>Stand {formatDate(e.generated_at)}</caption>
              <thead>
                <tr>
                  <th>Fragen</th>
                  <th>Richtig beantwortet</th>
                  <th>Antworten, die stimmen</th>
                  <th>Zu Recht keine Antwort</th>
                  <th className="num">Falsche Antworten</th>
                  <th className="num">Datenlecks</th>
                  <th className="num">Antwortzeit (Median)</th>
                </tr>
              </thead>
              <tbody>
                {rows(e).map((r) => (
                  <tr key={r.label}>
                    <th scope="row">
                      {r.label}
                      <small>
                        {r.s.questions} Fragen, {r.note}
                      </small>
                    </th>
                    <td>
                      <span className="num">{pct(r.s.answer_accuracy)}</span>
                      <Meter value={r.s.answer_accuracy} tone="good" />
                    </td>
                    <td>
                      <span className="num">{pct(r.s.answer_precision)}</span>
                      <Meter value={r.s.answer_precision} tone="good" />
                    </td>
                    <td>
                      <span className="num">{pct(r.s.declined_correctly)}</span>
                      <Meter value={r.s.declined_correctly} tone="good" />
                    </td>
                    <td className="num">{r.s.wrong_answers}</td>
                    <td className="num">
                      {r.s.leaks === 0 ? (
                        <Badge tone="inforce">0</Badge>
                      ) : (
                        <Badge tone="alert">{r.s.leaks}</Badge>
                      )}
                    </td>
                    <td className="num">{r.s.latency_ms_p50.toFixed(0)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className={styles.explain}>
              „Richtig beantwortet“: richtiger Wert aus dem richtigen Absatz der Fassung, die am Stichtag
              galt. „Antworten, die stimmen“: Anteil der gegebenen Antworten, die richtig waren; lieber keine
              Antwort als eine falsche Grenze.
            </p>
          </>
        )}
      </QueryState>
      <h2 className={styles.sub}>Welches Modell was sehen darf</h2>
      <QueryState query={registry} skeleton={<SkeletonBlock lines={3} label="Modelle werden geladen" />}>
        {(ms) => (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Modell</th>
                <th>Höchste Einstufung</th>
                <th>Verarbeitung</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {ms.map((x) => (
                <tr key={x.id}>
                  <th scope="row">{x.id}</th>
                  <td>
                    <Badge tone="restricted">{CLASSIFICATION[x.max_classification]}</Badge>
                  </td>
                  <td>{x.processing}</td>
                  <td>
                    {x.enabled ? <Badge tone="inforce">aktiv</Badge> : <Badge>nicht konfiguriert</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </QueryState>
    </>
  );
}
