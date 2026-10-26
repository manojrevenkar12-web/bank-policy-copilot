import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { formatDate } from "../../shared/lib/format";
import { useSession } from "../../shared/lib/session";
import { motion as m } from "../../shared/theme/tokens";
import { Badge, Button, EmptyState, ErrorState, PageHead, QueryState, SkeletonBlock } from "../../shared/ui";
import { useAuditCheck, useImpact, useResolve, useReviewQueue } from "./api";
import styles from "./Review.module.css";

function Resolve({ id, kind, label }: { id: number; kind: "review" | "impact"; label: string }) {
  const [note, setNote] = useState("");
  const resolve = useResolve(kind);
  return (
    <form
      className={styles.resolve}
      onSubmit={(e) => {
        e.preventDefault();
        resolve.mutate({ id, resolution: note });
      }}
    >
      <label className="visually-hidden" htmlFor={`note-${kind}-${id}`}>
        Vermerk
      </label>
      <input
        id={`note-${kind}-${id}`}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Vermerk, z. B. was angepasst wurde"
      />
      <Button type="submit" size="small" busy={resolve.isPending} disabled={note.trim().length < 3}>
        {label}
      </Button>
      {resolve.isError && <span role="alert">{resolve.error.message}</span>}
    </form>
  );
}

function AuditCard() {
  const check = useAuditCheck();
  return (
    <section className={styles.card}>
      <h2 className={styles.cardTitle}>Prüfpfad</h2>
      <p>
        Jede Frage und Antwort ist mit der vorherigen verkettet. Eine nachträgliche Änderung bricht die Kette
        an dieser Stelle.
      </p>
      <Button size="small" onClick={() => check.mutate()} busy={check.isPending}>
        Kette prüfen
      </Button>
      {check.isSuccess &&
        (check.data.ok ? (
          <p className={styles.ok} role="status">
            Unverändert: {check.data.records} Einträge geprüft.
          </p>
        ) : (
          <p className={styles.broken} role="alert">
            Geändert: Die Kette bricht bei Eintrag {check.data.broken_at}.
          </p>
        ))}
      {check.isError && <ErrorState error={check.error} />}
    </section>
  );
}

export function ReviewPage() {
  const s = useSession();
  const queue = useReviewQueue();
  const impact = useImpact();
  return (
    <>
      <PageHead
        title="Prüfung"
        lede="Antworten, die Mitarbeitende als nicht hilfreich markiert haben, und interne Regeln, die eine geänderte Aufsichtsmitteilung umsetzen."
      />
      <div className={styles.grid}>
        <section>
          <h2 className={styles.sectionTitle}>Geänderte Aufsichtsmitteilungen</h2>
          <QueryState
            query={impact}
            skeleton={<SkeletonBlock lines={5} label="Auswirkungen werden geladen" />}
            isEmpty={(d) => d.length === 0}
            empty={
              <EmptyState title="Keine Änderungen zu prüfen">
                Neue Fassungen von Aufsichtsmitteilungen erscheinen hier mit den betroffenen Absätzen.
              </EmptyState>
            }
          >
            {(items) => (
              <ul className={styles.items}>
                <AnimatePresence initial={false}>
                  {items.map((i) => (
                    <motion.li
                      key={i.id}
                      layout
                      className={styles.card}
                      exit={{ opacity: 0 }}
                      transition={{ duration: m.base }}
                      data-testid="impact-item"
                    >
                      <div className={styles.cardHead}>
                        <Badge tone={i.status === "open" ? "alert" : "inforce"}>
                          {i.status === "open" ? "offen" : "umgesetzt"}
                        </Badge>
                        <strong>
                          {i.circular} Tz. {i.circular_tz}
                        </strong>
                        <span>
                          Version {i.from_version} auf {i.to_version}
                        </span>
                      </div>
                      <p className={styles.change}>{i.change}</p>
                      <p>
                        Betrifft {i.title} ({i.doc_key}) Tz. {i.tz}, Version {i.version}:{" "}
                        <em>{i.paragraph}</em>
                      </p>
                      <p className={styles.reason}>Gefunden über: {i.reason}</p>
                      {i.note && <p className={styles.note}>{i.note}</p>}
                      {i.status === "open" && (
                        <Resolve id={i.id} kind="impact" label="Als umgesetzt markieren" />
                      )}
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </QueryState>
        </section>
        <section>
          <h2 className={styles.sectionTitle}>Rückmeldungen</h2>
          <QueryState
            query={queue}
            skeleton={<SkeletonBlock lines={5} label="Rückmeldungen werden geladen" />}
            isEmpty={(d) => d.length === 0}
            empty={
              <EmptyState title="Nichts offen">
                Wenn jemand eine Antwort als nicht hilfreich markiert, erscheint sie hier.
              </EmptyState>
            }
          >
            {(items) => (
              <ul className={styles.items}>
                <AnimatePresence initial={false}>
                  {items.map((i) => (
                    <motion.li
                      key={i.id}
                      layout
                      className={styles.card}
                      exit={{ opacity: 0, x: 24 }}
                      transition={{ duration: m.base }}
                      data-testid="review-item"
                    >
                      <div className={styles.cardHead}>
                        <strong>{i.login}</strong>
                        <span>Stichtag {formatDate(i.as_of)}</span>
                        <Badge>{i.model}</Badge>
                      </div>
                      <p className={styles.q}>{i.question}</p>
                      <p className={styles.a}>{i.answer}</p>
                      {i.comment && <p className={styles.comment}>„{i.comment}“</p>}
                      <Resolve id={i.id} kind="review" label="Erledigt" />
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </QueryState>
          {s?.user.groups?.includes("audit-all") && <AuditCard />}
        </section>
      </div>
    </>
  );
}
