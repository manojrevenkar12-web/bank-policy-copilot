import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import type { DocumentSummary } from "../../shared/api/types";
import { formatDate } from "../../shared/lib/format";
import { CLASSIFICATION, motion as m } from "../../shared/theme/tokens";
import { Badge, EmptyState, PageHead, QueryState, SkeletonBlock } from "../../shared/ui";
import { useDocuments } from "./api";
import styles from "./Documents.module.css";

function Row({ d, i }: { d: DocumentSummary; i: number }) {
  const current = d.versions.find((v) => v.version === d.version_on) ?? d.versions.at(-1)!;
  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(i, 12) * m.stagger, duration: m.base, ease: m.ease }}
    >
      <Link className={styles.row} to={`/richtlinien/${encodeURIComponent(d.doc_key)}/${current.version}`}>
        <span className={styles.key}>{d.doc_key}</span>
        <span className={styles.title}>{d.title}</span>
        <span className={styles.meta}>
          <Badge tone="inforce">
            V{current.version} seit {formatDate(current.valid_from)}
          </Badge>
          {d.versions.length > 1 && <Badge tone="superseded">{d.versions.length - 1} frühere</Badge>}
          <Badge tone="restricted">{CLASSIFICATION[d.classification]}</Badge>
        </span>
      </Link>
    </motion.li>
  );
}

export function DocumentsPage() {
  const docs = useDocuments();
  return (
    <>
      <PageHead
        title="Richtlinien"
        lede="Alle Richtlinien und Aufsichtsmitteilungen, die Sie einsehen dürfen, mit ihren Fassungen. Was Sie hier nicht sehen, kann der Copilot Ihnen auch nicht zitieren."
      />
      <QueryState
        query={docs}
        skeleton={<SkeletonBlock lines={8} label="Richtlinien werden geladen" />}
        isEmpty={(d) => d.length === 0}
        empty={
          <EmptyState title="Keine Richtlinien für Sie freigegeben">
            Wenden Sie sich an Ihre Führungskraft, wenn das nicht stimmt.
          </EmptyState>
        }
      >
        {(all) => (
          <>
            {(["policy", "circular"] as const).map((kind) => {
              const list = all.filter((d) => d.kind === kind);
              if (list.length === 0) return null;
              return (
                <section key={kind} className={styles.group}>
                  <h2 className={styles.groupTitle}>
                    {kind === "policy" ? "Interne Richtlinien" : "Aufsichtsmitteilungen"}
                  </h2>
                  <ul className={styles.list}>
                    {list.map((d, i) => (
                      <Row key={d.doc_key} d={d} i={i} />
                    ))}
                  </ul>
                </section>
              );
            })}
          </>
        )}
      </QueryState>
    </>
  );
}
