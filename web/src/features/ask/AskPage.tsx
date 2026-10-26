import { AnimatePresence, motion } from "framer-motion";
import { useState, type FormEvent } from "react";

import { formatDate, todayIso } from "../../shared/lib/format";
import { useSession } from "../../shared/lib/session";
import { layout, motion as m } from "../../shared/theme/tokens";
import { Badge, Button, EmptyState, ErrorState, QueryState, Skeleton, SkeletonBlock } from "../../shared/ui";
import { AnswerCard, NoAnswer } from "./AnswerCard";
import styles from "./Ask.module.css";
import { useAsk, useDocuments, useHistory } from "./api";
import { Feedback } from "./Feedback";
import { Trace } from "./Trace";

const EXAMPLES = [
  "Ab welchem Betrag gilt bei Zahlungen das Vier-Augen-Prinzip?",
  "Bis zu welchem Wert darf ich ein Geschenk von einem Kunden annehmen?",
  "Wie viele Tage pro Woche darf ich mobil arbeiten?",
  "Innerhalb welcher Frist muss ein kritisches Sicherheitsupdate eingespielt sein?",
];

export function AskPage() {
  const s = useSession();
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState(todayIso);
  const ask = useAsk();
  const docs = useDocuments();
  const history = useHistory();

  const submit = (q = question, on = asOf) => {
    if (q.trim().length < 3) return;
    setQuestion(q);
    setAsOf(on);
    ask.mutate({ question: q.trim(), as_of: on });
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };
  const result = ask.data;
  const cited = result?.citations[0];

  return (
    <div className={styles.page}>
      <div className={styles.mainCol}>
        <motion.form
          className={styles.askForm}
          onSubmit={onSubmit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: m.slow, ease: m.ease }}
        >
          <label htmlFor="question" className={styles.prompt}>
            Was möchten Sie wissen, {s?.user.name.split(" ")[0]}?
          </label>
          <textarea
            id="question"
            className={styles.question}
            rows={2}
            maxLength={1000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="z. B. Bis wann müssen SEPA-Überweisungen eingehen, damit sie am selben Tag ausgeführt werden?"
          />
          <div className={styles.controls}>
            <label className={styles.dateField}>
              <span>Stichtag</span>
              <input type="date" value={asOf} max="2099-12-31" onChange={(e) => setAsOf(e.target.value)} />
            </label>
            <div className={styles.shortcuts} role="group" aria-label="Stichtag wählen">
              <button type="button" aria-pressed={asOf === todayIso()} onClick={() => setAsOf(todayIso())}>
                heute
              </button>
              {layout.dateShortcuts.map((d) => (
                <button key={d} type="button" aria-pressed={asOf === d} onClick={() => setAsOf(d)}>
                  {formatDate(d)}
                </button>
              ))}
            </div>
            <Button
              type="submit"
              variant="primary"
              busy={ask.isPending}
              disabled={question.trim().length < 3}
            >
              Fragen
            </Button>
          </div>
        </motion.form>

        <section className={styles.result} aria-live="polite">
          {ask.isIdle && (
            <div className={styles.examples}>
              <p>Zum Beispiel:</p>
              <ul>
                {EXAMPLES.map((q) => (
                  <li key={q}>
                    <button type="button" onClick={() => submit(q, asOf)}>
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ask.isPending && (
            <div className={styles.answer} role="status" aria-label="Antwort wird gesucht">
              <Skeleton height="1.5rem" width="40%" />
              <SkeletonBlock lines={3} label="Antwort wird gesucht" />
              <Skeleton height="2.25rem" />
            </div>
          )}
          {ask.isError && (
            <ErrorState
              error={ask.error}
              onRetry={() => submit()}
              title="Die Frage konnte nicht beantwortet werden"
            />
          )}
          <AnimatePresence mode="wait">
            {result && !ask.isPending && (
              <motion.div key={result.query_id} exit={{ opacity: 0 }} transition={{ duration: m.fast }}>
                {result.outcome === "answered" && cited ? (
                  <AnswerCard result={result} doc={docs.data?.find((d) => d.doc_key === cited.doc_key)} />
                ) : (
                  <NoAnswer result={result} />
                )}
                <Feedback key={result.query_id} queryId={result.query_id} />
                <Trace trace={result.trace} citedId={cited?.paragraph_id ?? null} />
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      </div>

      <aside className={styles.side} aria-labelledby="history-title">
        <h2 id="history-title" className={styles.sideTitle}>
          Ihre letzten Fragen
        </h2>
        <QueryState
          query={history}
          skeleton={<SkeletonBlock lines={5} label="Verlauf wird geladen" />}
          isEmpty={(d) => d.length === 0}
          empty={
            <EmptyState title="Noch keine Fragen">Ihre Fragen erscheinen hier, mit dem Stichtag.</EmptyState>
          }
        >
          {(items) => (
            <ol className={styles.history}>
              {items.map((h) => (
                <li key={h.id}>
                  <button type="button" onClick={() => submit(h.question, h.as_of)}>
                    <span>{h.question}</span>
                    <span className={styles.historyMeta}>
                      Stichtag {formatDate(h.as_of)}
                      {h.outcome === "no_answer" ? <Badge>keine Regelung</Badge> : null}
                      {h.helpful === false ? <Badge tone="alert">nicht hilfreich</Badge> : null}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </QueryState>
      </aside>
    </div>
  );
}
